"""Flight controller for PX4 SITL, run INSIDE the PX4 container (MAVLink over localhost).

Why inside: Docker Desktop's UDP port forwarding doesn't reliably carry PX4's MAVLink replies back
to the host. Inside the container, localhost works on every platform.

usage (in container): python3 px4_control.py /work/mission.json /work/control.json
mission.json: {"items": [[cmd, lat, lon, alt], ...], "wall_limit_s": float}
control.json: {"ok": bool, "error": str|null, "finished": bool, "texts": [...], "modes": [...]}
"""
import json
import sys
import time

from pymavlink import mavutil

ML = mavutil.mavlink


def main(mission_path, out_path):
    spec = json.load(open(mission_path))
    out = {"ok": False, "error": None, "finished": False, "texts": [], "modes": []}
    t0 = time.monotonic()

    def stamp():
        return round(time.monotonic() - t0, 2)

    try:
        m = mavutil.mavlink_connection("udpout:127.0.0.1:18570", source_system=255)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            m.mav.heartbeat_send(ML.MAV_TYPE_GCS, ML.MAV_AUTOPILOT_INVALID, 0, 0, 0)
            hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
            if hb and hb.get_srcSystem() == 1:
                break
        else:
            raise TimeoutError("no heartbeat from PX4")
        m.target_system, m.target_component = 1, 1

        items = spec["items"]
        for attempt in range(5):
            m.mav.mission_count_send(1, 1, len(items), ML.MAV_MISSION_TYPE_MISSION)
            done, dl = False, time.monotonic() + 20
            while time.monotonic() < dl:
                msg = m.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"], blocking=True, timeout=2)
                if msg is None:
                    continue
                if msg.get_type() == "MISSION_ACK":
                    done = msg.type == ML.MAV_MISSION_ACCEPTED
                    break
                cmd, lat, lon, alt = items[msg.seq]
                m.mav.mission_item_int_send(1, 1, msg.seq, ML.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, cmd, 0, 1,
                                            0, 0, 0, float("nan"), int(lat * 1e7), int(lon * 1e7), alt,
                                            ML.MAV_MISSION_TYPE_MISSION)
            if done:
                break
            time.sleep(1)
        else:
            raise RuntimeError("mission upload failed")

        armed = False
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and not armed:
            try:
                m.set_mode("MISSION")
            except Exception:  # noqa: BLE001 - mode map may not be ready yet
                pass
            m.mav.command_long_send(1, 1, ML.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)
            t_end = time.monotonic() + 3
            while time.monotonic() < t_end:
                msg = m.recv_match(blocking=True, timeout=1)
                if msg is None:
                    continue
                if msg.get_type() == "STATUSTEXT":
                    out["texts"].append([stamp(), msg.text])
                if msg.get_type() == "HEARTBEAT" and msg.get_srcSystem() == 1 and msg.base_mode & ML.MAV_MODE_FLAG_SAFETY_ARMED:
                    armed = True
                    break
            if not armed:
                time.sleep(1)
        if not armed:
            raise TimeoutError("PX4 never armed (pre-arm checks)")

        last_mode = None
        t_end = time.monotonic() + float(spec["wall_limit_s"])
        while time.monotonic() < t_end:
            msg = m.recv_match(blocking=True, timeout=1)
            if msg is None:
                continue
            typ = msg.get_type()
            if typ == "HEARTBEAT" and msg.get_srcSystem() == 1:
                mode = mavutil.mode_string_v10(msg)
                if mode != last_mode:
                    out["modes"].append([stamp(), mode])
                    last_mode = mode
                if not (msg.base_mode & ML.MAV_MODE_FLAG_SAFETY_ARMED):
                    out["finished"] = True
                    break
            elif typ == "STATUSTEXT":
                out["texts"].append([stamp(), msg.text])
        out["ok"] = True
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
    time.sleep(2)  # let the logger close the ULog after disarm
    json.dump(out, open(out_path, "w"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
