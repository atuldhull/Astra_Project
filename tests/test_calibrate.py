from pathlib import Path

from astra.calibrate import _collect


def test_collect_prefers_npz_and_ignores_eeprom(tmp_path: Path):
    run = tmp_path / "r1"
    (run / "logs").mkdir(parents=True)
    (run / "eeprom.bin").write_bytes(b"x")
    (run / "logs" / "00000001.BIN").write_bytes(b"x")
    (run / "flight.npz").write_bytes(b"x")
    raw = tmp_path / "r2" / "logs"
    raw.mkdir(parents=True)
    (raw / "00000002.BIN").write_bytes(b"x")
    (tmp_path / "r2" / "eeprom.bin").write_bytes(b"x")
    got = {p.relative_to(tmp_path).as_posix() for p in _collect([tmp_path])}
    assert "r1/flight.npz" in got
    assert "r2/logs/00000002.BIN" in got
    assert not any("eeprom" in g for g in got)
