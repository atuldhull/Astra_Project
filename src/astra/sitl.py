"""ArduPilot SITL container lifecycle + MAVLink connection.

Each run gets its own container, work directory and host port. The container
runs the unmodified-vehicle SITL binary directly (no MAVProxy). Resources are
capped per container so a batch can't pin the laptop at 100%.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from pymavlink import mavutil

DEFAULT_IMAGE = os.environ.get("ASTRA_SITL_IMAGE", "astra/ardupilot-sitl:copter-4.7.2")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class SitlConfig:
    home: tuple[float, float, float, float]  # lat, lon, alt_m, heading_deg
    workdir: Path
    speedup: int = 5
    extra_params: dict[str, float] = field(default_factory=dict)
    vendor_param_file: Path | None = None
    lua_script: str | None = None
    extra_scripts: dict[str, str] = field(default_factory=dict)  # e.g. onboard monitor under test
    image: str = DEFAULT_IMAGE
    cpus: float = 1.5
    memory: str = "768m"
    model: str = "+"


# Applied last, so they override vendor params. Only simulation, logging,
# scripting and telemetry-rate settings: nothing that changes flight behaviour.
HARNESS_PARAMS: dict[str, float] = {
    "SCR_ENABLE": 1,
    "SCR_HEAP_SIZE": 200000,
    "LOG_BACKEND_TYPE": 1,
    "LOG_DISARMED": 0,
    "SR0_POSITION": 10,
    "SR0_EXTRA1": 4,
    "SR0_EXTRA2": 4,
    "SR0_EXTRA3": 4,
    "SR0_EXT_STAT": 4,
    "SR0_RAW_SENS": 0,
}


def read_params(path: Path) -> dict[str, float]:
    """Parse ArduPilot (NAME VALUE), Mission Planner (NAME,VALUE) or QGroundControl
    (sys<TAB>comp<TAB>NAME<TAB>VALUE<TAB>type) parameter files into {NAME: value}."""
    out: dict[str, float] = {}
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) >= 4 and cols[0].strip().isdigit() and cols[1].strip().isdigit():
            name, val = cols[2].strip(), cols[3].strip()
        else:
            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                continue
            name, val = parts[0], parts[1]
        try:
            out[name] = float(val)
        except ValueError:
            continue
    return out


def write_params(params: dict[str, float], path: Path) -> None:
    path.write_text("".join(f"{k} {v:g}\n" for k, v in params.items()), encoding="ascii")


class Sitl:
    def __init__(self, cfg: SitlConfig):
        self.cfg = cfg
        self.name = f"astra-sitl-{uuid.uuid4().hex[:10]}"
        self.port = free_port()
        self.mav: mavutil.mavfile | None = None

    # ── files ───────────────────────────────────────────────────────────
    def _prepare_workdir(self) -> list[str]:
        wd = self.cfg.workdir
        wd.mkdir(parents=True, exist_ok=True)
        (wd / "logs").mkdir(exist_ok=True)
        defaults = ["/opt/ardupilot/copter.parm"]
        if self.cfg.vendor_param_file:
            write_params(read_params(self.cfg.vendor_param_file), wd / "vendor.parm")
            defaults.append("/work/vendor.parm")
        params = {**HARNESS_PARAMS, "SIM_SPEEDUP": self.cfg.speedup, **self.cfg.extra_params}
        (wd / "astra.parm").write_text(
            "".join(f"{k} {v}\n" for k, v in params.items()), encoding="ascii"
        )
        defaults.append("/work/astra.parm")
        scripts = wd / "scripts"
        if scripts.exists():
            shutil.rmtree(scripts)
        if self.cfg.lua_script or self.cfg.extra_scripts:
            scripts.mkdir()
        if self.cfg.lua_script:
            (scripts / "astra_attack.lua").write_text(self.cfg.lua_script, encoding="ascii", newline="\n")
        for name, body in self.cfg.extra_scripts.items():
            (scripts / name).write_text(body, encoding="ascii", newline="\n")
        return defaults

    # ── lifecycle ───────────────────────────────────────────────────────
    def start(self, timeout_s: float = 60.0) -> mavutil.mavfile:
        defaults = self._prepare_workdir()
        lat, lon, alt, hdg = self.cfg.home
        cmd = [
            "docker", "run", "-d", "--rm", "--name", self.name,
            "--cpus", str(self.cfg.cpus), "--memory", self.cfg.memory,
            "-p", f"127.0.0.1:{self.port}:5760",
            "-v", f"{self.cfg.workdir.resolve()}:/work",
            self.cfg.image,
            "--model", self.cfg.model,
            "--speedup", str(self.cfg.speedup),
            "--defaults", ",".join(defaults),
            "--home", f"{lat},{lon},{alt},{hdg}",
            "-w", "-I0",
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        deadline = time.monotonic() + timeout_s
        last_err: Exception | None = None
        while time.monotonic() < deadline:
            try:
                m = mavutil.mavlink_connection(
                    f"tcp:127.0.0.1:{self.port}", source_system=255, autoreconnect=False
                )
                if m.wait_heartbeat(timeout=5):
                    self.mav = m
                    return m
                m.close()
            except OSError as exc:
                last_err = exc
            time.sleep(0.5)
        self.stop()
        raise TimeoutError(f"SITL did not send a heartbeat within {timeout_s}s ({last_err})")

    def stop(self) -> None:
        try:
            if self.mav is not None:
                self.mav.close()
        finally:
            self.mav = None
            subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def logs(self) -> list[Path]:
        return sorted((self.cfg.workdir / "logs").glob("*.BIN"))
