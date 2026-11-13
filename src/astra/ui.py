"""`astra ui`: one local web app for the three ways to use ASTRA.

    astra ui                 -> http://127.0.0.1:8787

  Analyse   drop a flight log (.ulg / .bin / .npz) -> verdict + full report. The log is deleted after analysis.
  Live      connect a drone, simulator or ground-station forward over MAVLink (USB/serial or UDP), or replay a log,
            and watch GNSS health with alarms (astra.live).
  Simulate  fly an attack scenario pack in the bundled simulators (needs Docker and the ASTRA SITL images).

Standard library only (http.server). Binds to 127.0.0.1 by default; `--host 0.0.0.0` exposes it on the network
(no login - use only on a trusted network).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_UPLOAD = 2_000_000_000
ALLOWED = (".ulg", ".bin", ".npz")
EXAMPLES = next((p for p in (Path(__file__).resolve().parent / "examples", Path(__file__).resolve().parents[2] / "examples")
                 if p.exists()), Path("examples"))

_reports: dict[str, str] = {}
_live = {"session": None}
_sim = {"proc": None, "out": None, "log": [], "pack": None, "html": None}
_lock = threading.Lock()


def _analyse(data: bytes, filename: str, takeoff: str | None) -> dict:
    from astra.forensics import diagnose
    from astra.forensics_html import _kind, render
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED:
        raise ValueError(f"unsupported file type {suffix!r}: use .ulg (PX4), .bin (ArduPilot) or .npz")
    tmp = Path(tempfile.mkdtemp(prefix="astra_ui_"))
    try:
        log = tmp / f"upload{suffix}"
        log.write_bytes(data)
        tk = None
        if takeoff:
            parts = [float(x) for x in takeoff.split(",")]
            tk = tuple(parts[:3])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rep = diagnose(log, takeoff=tk)
            rep["log"] = str(log)
            page = render(rep, tmp / "report.html").read_text(encoding="utf-8")
        rid = uuid.uuid4().hex[:12]
        page = page.replace(str(log), filename)
        with _lock:
            _reports[rid] = page
            while len(_reports) > 20:
                _reports.pop(next(iter(_reports)))
        return {"verdict": rep["verdict"], "kind": _kind(rep["verdict"]), "report": f"/report/{rid}",
                "evidence": rep["evidence"], "receiver": {k: rep["receiver"].get(k) for k in
                                                         ("min_sats_in_fix", "max_reported_hacc_m", "outage_jumps")}}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # the uploaded log never stays on disk


def _docker_ok() -> tuple[bool, list[str]]:
    try:
        r = subprocess.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True,
                           text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False, []
    if r.returncode != 0:
        return False, []
    return True, [x for x in r.stdout.split() if x.startswith("astra/")]


def _sim_start(pack: str, only: str, autopilot: str) -> dict:
    from astra.packs import PACKS
    if pack not in PACKS:
        raise ValueError(f"unknown pack {pack!r}")
    with _lock:
        if _sim["proc"] is not None and _sim["proc"].poll() is None:
            raise RuntimeError("a simulation is already running")
        out = Path("runs") / "ui" / time.strftime("%Y%m%d-%H%M%S")
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-m", "astra.cli", "run", pack, "--out", str(out), "--seeds", "1",
               "--parallel", "1", "--autopilot", autopilot]
        if only:
            cmd += ["--only", only]
        import os
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                                encoding="utf-8", errors="replace", env=env)
        _sim.update(proc=proc, out=out, log=[" ".join(cmd[2:])], pack=pack, html=None)

    def pump():
        for line in proc.stdout:
            _sim["log"].append(line.rstrip())
            del _sim["log"][:-200]
        proc.wait()
        if proc.returncode == 0:
            try:
                from astra.html_report import render
                _sim["html"] = str(render(out))
            except Exception as exc:  # noqa: BLE001
                _sim["log"].append(f"report failed: {exc}")
    threading.Thread(target=pump, daemon=True).start()
    return {"started": True, "out": str(out)}


def _sim_status() -> dict:
    p = _sim["proc"]
    return {"running": p is not None and p.poll() is None, "returncode": None if p is None else p.poll(),
            "pack": _sim["pack"], "log": _sim["log"][-40:], "report": "/sim/report" if _sim["html"] else None}


class Handler(BaseHTTPRequestHandler):
    server_version = "ASTRA-UI"

    def log_message(self, fmt, *args):  # quiet
        pass

    def _send(self, code: int, body, ctype="application/json"):
        if not isinstance(body, (bytes, str)):
            body = json.dumps(body, default=str)
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("text", "application/json")) else ""))
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/index.html"):
                return self._send(200, PAGE, "text/html")
            if path.startswith("/report/"):
                page = _reports.get(path.rsplit("/", 1)[1])
                return self._send(200, page, "text/html") if page else self._send(404, {"error": "report expired"})
            if path == "/api/info":
                from astra.packs import PACKS
                ok, images = _docker_ok()
                ex = sorted(p.name for p in EXAMPLES.glob("*.npz")) if EXAMPLES.exists() else []
                return self._send(200, {"packs": {k: len(v()) for k, v in PACKS.items()}, "docker": ok,
                                        "images": images, "examples": ex})
            if path == "/api/live/status":
                s = _live["session"]
                return self._send(200, s.status() if s else {"state": "idle"})
            if path == "/api/sim/status":
                return self._send(200, _sim_status())
            if path == "/sim/report" and _sim["html"]:
                return self._send(200, Path(_sim["html"]).read_text(encoding="utf-8"), "text/html")
            return self._send(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            if path == "/api/analyse":
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > MAX_UPLOAD:
                    return self._send(400, {"error": "empty or too large (limit 2 GB)"})
                data = self.rfile.read(n)
                name = Path(self.headers.get("X-Filename") or "log.ulg").name
                return self._send(200, _analyse(data, name, self.headers.get("X-Takeoff") or None))
            if path == "/api/live/start":
                req = self._json()
                src = (req.get("source") or "").strip()
                if req.get("example"):
                    ex = EXAMPLES / Path(req["example"]).name
                    if not ex.exists():
                        return self._send(400, {"error": "unknown example"})
                    src = f"replay:{ex}"
                if not src:
                    return self._send(400, {"error": "give a connection, e.g. udp:0.0.0.0:14550 or COM5"})
                from astra.live import LiveSession
                if _live["session"]:
                    _live["session"].stop()
                cal = json.loads(req["shield_cal"]) if req.get("shield_cal") else None
                _live["session"] = LiveSession(src, shield_cal=cal, replay_speed=float(req.get("speed") or 10))
                return self._send(200, {"started": True})
            if path == "/api/live/stop":
                if _live["session"]:
                    _live["session"].stop()
                return self._send(200, {"stopped": True})
            if path == "/api/sim/start":
                req = self._json()
                return self._send(200, _sim_start(req.get("pack", ""), req.get("only", ""), req.get("autopilot", "ardupilot")))
            if path == "/api/sim/stop":
                if _sim["proc"] is not None and _sim["proc"].poll() is None:
                    _sim["proc"].terminate()
                return self._send(200, {"stopped": True})
            return self._send(404, {"error": "not found"})
        except (ValueError, RuntimeError) as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": f"{type(exc).__name__}: {exc}"})


def serve(host: str = "127.0.0.1", port: int = 8787, open_browser: bool = True) -> None:
    srv = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{port}"
    print(f"ASTRA UI on {url}  (Ctrl+C to stop)", flush=True)
    if host not in ("127.0.0.1", "localhost"):
        print("warning: reachable from the network and has no login; use only on a trusted network", flush=True)
    if open_browser:
        import webbrowser
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


PAGE = (Path(__file__).with_name("ui_page.html")).read_text(encoding="utf-8") if \
    Path(__file__).with_name("ui_page.html").exists() else "<h1>ui_page.html missing</h1>"
