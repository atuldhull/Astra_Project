"""Regenerates sim/px4/astra-px4-gps.patch from a pristine PX4 v1.17.0 checkout.

usage: python sim/px4/make_patch.py <PX4-Autopilot checkout>   (then: git -C <checkout> diff > sim/px4/astra-px4-gps.patch)

Simulator-only: touches src/modules/simulation/sensor_gps_sim (the simulated GPS sensor), never the
flight stack. Everything is off by default (ASTRA_ATK_MODEL=0, ASTRA_GPS_PNSE=0).
"""
import sys
from pathlib import Path

d = Path(sys.argv[1]) / "src/modules/simulation/sensor_gps_sim"


def rw(name, fn):
    p = d / name
    s = p.read_text(encoding="utf-8")
    s2 = fn(s)
    assert s2 != s, f"no change applied to {name}"
    p.write_text(s2, encoding="utf-8", newline="\n")


def hpp(h):
    h = h.replace("#include <uORB/topics/vehicle_local_position.h>\n",
                  "#include <uORB/topics/vehicle_local_position.h>\n#include <uORB/topics/vehicle_status.h>\n")
    h = h.replace("\tuORB::PublicationMulti<sensor_gps_s> _sensor_gps_pub{ORB_ID(sensor_gps)};\n",
                  "\tuORB::PublicationMulti<sensor_gps_s> _sensor_gps_pub{ORB_ID(sensor_gps)};\n\n"
                  "\t// ASTRA test-harness extension (simulator only): attack timeline + receiver noise\n"
                  "\tuORB::Subscription _vehicle_status_sub{ORB_ID(vehicle_status)};\n"
                  "\thrt_abstime _astra_armed_at{0};\n\thrt_abstime _astra_gm_last{0};\n"
                  "\tfloat _astra_gm_n{0.f};\n\tfloat _astra_gm_e{0.f};\n\tbool _astra_gm_init{false};\n"
                  "\tstruct AstraHist { hrt_abstime t; double lat; double lon; double alt; float vn; float ve; float vd; };\n"
                  "\tstatic constexpr int ASTRA_HIST_N = 512;\n"
                  "\tAstraHist _astra_hist[ASTRA_HIST_N] {};\n\tint _astra_hist_head{0};\n\tint _astra_hist_count{0};\n"
                  "\thrt_abstime _astra_chaos_next{0};\n\tint _astra_chaos_sats{10};\n\tbool _astra_chaos_lock{true};\n"
                  "\tdouble _astra_chaos_dn{0.0};\n\tdouble _astra_chaos_de{0.0};\n\tfloat _astra_chaos_vn{0.f};\n"
                  "\tfloat _astra_chaos_ve{0.f};\n\thrt_abstime _astra_chaos_start{0};\n")
    names = [("Int", "ASTRA_ATK_MODEL", "_astra_model"), ("Float", "ASTRA_ATK_ARM_S", "_astra_arm_s"),
             ("Float", "ASTRA_ATK_DUR", "_astra_dur"), ("Float", "ASTRA_ATK_RATE", "_astra_rate"),
             ("Float", "ASTRA_ATK_BRG", "_astra_brg"), ("Float", "ASTRA_ATK_RAMP", "_astra_ramp"),
             ("Int", "ASTRA_ATK_CONS", "_astra_cons"), ("Float", "ASTRA_ATK_JN", "_astra_jn"),
             ("Float", "ASTRA_ATK_JE", "_astra_je"), ("Float", "ASTRA_ATK_PER", "_astra_per"),
             ("Float", "ASTRA_ATK_DUTY", "_astra_duty"), ("Float", "ASTRA_GPS_PNSE", "_astra_pnse"),
             ("Float", "ASTRA_GPS_PTAU", "_astra_ptau"), ("Int", "ASTRA_ATK_DLY_MS", "_astra_delay_ms")]
    extra = "".join(f",\n\t\t(Param{k}<px4::params::{n}>) {m}" for k, n, m in names)
    return h.replace("\t\t(ParamInt<px4::params::SIM_GPS_USED>) _sim_gps_used\n",
                     "\t\t(ParamInt<px4::params::SIM_GPS_USED>) _sim_gps_used" + extra + "\n")


BLOCK = """
		// ---- ASTRA test-harness extension (simulator only; all off by default) ----
		const hrt_abstime astra_now = hrt_absolute_time();

		if (_vehicle_status_sub.updated()) {
			vehicle_status_s vs{};
			_vehicle_status_sub.copy(&vs);

			if (vs.arming_state == vehicle_status_s::ARMING_STATE_ARMED && _astra_armed_at == 0) {
				_astra_armed_at = astra_now;
			}
		}

		const double astra_m_per_deg = math::radians(1.0) * (double)CONSTANTS_RADIUS_OF_EARTH;
		const double astra_cos_lat = cos(math::radians(gpos.lat));

		if (_astra_pnse.get() > 0.f) {
			// first-order Gauss-Markov horizontal position error (receiver multipath/atmosphere)
			const float sigma = _astra_pnse.get();

			if (!_astra_gm_init) {
				_astra_gm_n = sigma * generate_wgn();
				_astra_gm_e = sigma * generate_wgn();
				_astra_gm_last = astra_now;
				_astra_gm_init = true;
			}

			const float dt = (astra_now - _astra_gm_last) * 1e-6f;
			_astra_gm_last = astra_now;
			const float a = expf(-dt / fmaxf(1.f, _astra_ptau.get()));
			const float q = sigma * sqrtf(fmaxf(0.f, 1.f - a * a));
			_astra_gm_n = a * _astra_gm_n + q * generate_wgn();
			_astra_gm_e = a * _astra_gm_e + q * generate_wgn();
			latitude += (double)_astra_gm_n / astra_m_per_deg;
			longitude += (double)_astra_gm_e / (astra_m_per_deg * astra_cos_lat);
		}

		// history of the un-attacked fix (for meaconing), at most every 20 ms => ~10 s of history
		const int astra_last = (_astra_hist_head - 1 + ASTRA_HIST_N) % ASTRA_HIST_N;

		if (_astra_hist_count == 0 || astra_now - _astra_hist[astra_last].t >= 20000) {
			_astra_hist[_astra_hist_head] = AstraHist{astra_now, latitude, longitude, altitude, gps_vel(0), gps_vel(1), gps_vel(2)};
			_astra_hist_head = (_astra_hist_head + 1) % ASTRA_HIST_N;

			if (_astra_hist_count < ASTRA_HIST_N) { _astra_hist_count++; }
		}

		bool astra_deny = false;
		int astra_sats = _sim_gps_used.get();
		float astra_eph = -1.f;

		if (_astra_model.get() > 0 && _astra_armed_at > 0) {
			const float t = (astra_now - _astra_armed_at) * 1e-6f - _astra_arm_s.get();

			if (t >= 0.f && t < _astra_dur.get()) {
				switch (_astra_model.get()) {
				case 1: // jam_denial
					astra_deny = true;
					break;

				case 2: { // jam_intermittent
						const float per = fmaxf(0.2f, _astra_per.get());

						if (fmodf(t, per) / per < _astra_duty.get()) { astra_deny = true; }

						break;
					}

				case 3: // spoof_jump
					latitude += (double)_astra_jn.get() / astra_m_per_deg;
					longitude += (double)_astra_je.get() / (astra_m_per_deg * astra_cos_lat);
					break;

				case 4: { // spoof_drag (ramp-in; consistent => velocity biased too)
						const float R = _astra_ramp.get();
						const float rate = _astra_rate.get();
						float dist;
						float vel;

						if (R > 0.f && t < R) {
							dist = rate * t * t / (2.f * R);
							vel = rate * t / R;

						} else {
							dist = rate * (t - R / 2.f);
							vel = rate;
						}

						const float brg = math::radians(_astra_brg.get());
						latitude += (double)(dist * cosf(brg)) / astra_m_per_deg;
						longitude += (double)(dist * sinf(brg)) / (astra_m_per_deg * astra_cos_lat);

						if (_astra_cons.get() == 1) {
							gps_vel(0) += vel * cosf(brg);
							gps_vel(1) += vel * sinf(brg);
						}

						break;
					}

				case 5: { // meaconing: report where the vehicle was delay_ms ago
						const hrt_abstime want = astra_now - (hrt_abstime)_astra_delay_ms.get() * 1000;

						for (int i = 1; i <= _astra_hist_count; i++) {
							const AstraHist &h = _astra_hist[(_astra_hist_head - i + ASTRA_HIST_N) % ASTRA_HIST_N];

							if (h.t <= want) {
								latitude = h.lat;
								longitude = h.lon;
								altitude = h.alt;
								gps_vel = Vector3f{h.vn, h.ve, h.vd};
								break;
							}
						}

						break;
					}

				case 7: { // jam_chaotic (modelled on ArduPilot SITL's jamming model)
						if (_astra_chaos_start == 0) {
							_astra_chaos_start = astra_now;
							_astra_chaos_dn = _astra_chaos_de = 0.0;
						}

						const float since = (astra_now - _astra_chaos_start) * 1e-6f;

						if (since < 1.f + 2.5f * fabsf(generate_wgn())) {
							astra_deny = true;  // total loss of signal at the start is common

						} else {
							if (astra_now >= _astra_chaos_next) {
								_astra_chaos_next = astra_now + (hrt_abstime)(1e6f * (0.3f + 0.7f * fabsf(generate_wgn())));
								_astra_chaos_sats = 2 + (int)(fabsf(generate_wgn()) * 6.f) % 15;
								_astra_chaos_lock = _astra_chaos_sats >= 4 && generate_wgn() > 0.f;
								_astra_chaos_dn += 60.0 * (double)generate_wgn();
								_astra_chaos_de += 60.0 * (double)generate_wgn();
								_astra_chaos_vn = 8.f * generate_wgn();
								_astra_chaos_ve = 8.f * generate_wgn();
							}

							astra_sats = _astra_chaos_sats;
							astra_deny = !_astra_chaos_lock;
							astra_eph = 2.f + 20.f * fabsf(generate_wgn());
							latitude += _astra_chaos_dn / astra_m_per_deg;
							longitude += _astra_chaos_de / (astra_m_per_deg * astra_cos_lat);
							gps_vel(0) += _astra_chaos_vn;
							gps_vel(1) += _astra_chaos_ve;
						}

						break;
					}

				case 6: // jam_degrade
					astra_sats = 5;
					astra_eph = 8.f;
					break;

				default:
					break;
				}
			}
		}
"""


def cpp(c):
    anchor = "\t\tVector3f gps_vel = Vector3f{lpos.vx, lpos.vy, lpos.vz} + noiseGauss3f(0.06f, 0.077f, 0.158f);\n"
    assert anchor in c
    c = c.replace(anchor, anchor + BLOCK)
    c = c.replace("\t\tif (_sim_gps_used.get() >= 4) {\n", "\t\tif (!astra_deny && astra_sats >= 4) {\n")
    c = c.replace("\t\t\tsensor_gps.eph = 0.9f;\n", "\t\t\tsensor_gps.eph = astra_eph > 0.f ? astra_eph : 0.9f;\n")
    c = c.replace("\t\tsensor_gps.satellites_used = _sim_gps_used.get();\n",
                  "\t\tsensor_gps.satellites_used = astra_deny ? 0 : astra_sats;\n")
    return c


def P(name, kind, default, desc, unit=None):
    u = f"\n * @unit {unit}" if unit else ""
    return (f"\n/**\n * ASTRA: {desc}\n *\n * Test-harness extension (simulator only).{u}\n * @group Simulator\n */\n"
            f"PARAM_DEFINE_{kind}({name}, {default});\n")


def params(s):
    return s + "".join([
        P("ASTRA_ATK_MODEL", "INT32", 0, "attack model (0 none, 1 denial, 2 intermittent, 3 jump, 4 drag, 5 meaconing, 6 degrade, 7 chaotic)"),
        P("ASTRA_ATK_DLY_MS", "INT32", 0, "meaconing replay delay", "ms"),
        P("ASTRA_ATK_ARM_S", "FLOAT", "0.0f", "attack start, seconds after arming", "s"),
        P("ASTRA_ATK_DUR", "FLOAT", "0.0f", "attack duration", "s"),
        P("ASTRA_ATK_RATE", "FLOAT", "0.0f", "drag-off rate", "m/s"),
        P("ASTRA_ATK_BRG", "FLOAT", "0.0f", "drag-off bearing", "deg"),
        P("ASTRA_ATK_RAMP", "FLOAT", "0.0f", "drag-off ramp-in time", "s"),
        P("ASTRA_ATK_CONS", "INT32", 1, "drag-off velocity-consistent (1) or naive (0)"),
        P("ASTRA_ATK_JN", "FLOAT", "0.0f", "jump offset north", "m"),
        P("ASTRA_ATK_JE", "FLOAT", "0.0f", "jump offset east", "m"),
        P("ASTRA_ATK_PER", "FLOAT", "4.0f", "intermittent jamming period", "s"),
        P("ASTRA_ATK_DUTY", "FLOAT", "0.5f", "intermittent jamming fraction without fix"),
        P("ASTRA_GPS_PNSE", "FLOAT", "0.0f", "1-sigma Gauss-Markov horizontal position error", "m"),
        P("ASTRA_GPS_PTAU", "FLOAT", "30.0f", "position error correlation time", "s"),
    ])


rw("SensorGpsSim.hpp", hpp)
rw("SensorGpsSim.cpp", cpp)
rw("parameters.c", params)
print("patched", d)

# Guard against silent no-match edits: every expected token must be present after patching.
_REQUIRED = {"SensorGpsSim.hpp": ["struct AstraHist", "_astra_hist_head", "_astra_chaos_start", "ASTRA_ATK_DLY_MS"],
             "SensorGpsSim.cpp": ["at most every 20 ms", "case 5:", "case 7:", "astra_deny ? 0 : astra_sats"],
             "parameters.c": ["ASTRA_ATK_DLY_MS", "ASTRA_GPS_PTAU"]}
for _f, _toks in _REQUIRED.items():
    _txt = (d / _f).read_text(encoding="utf-8")
    _missing = [t for t in _toks if t not in _txt]
    assert not _missing, f"{_f}: missing {_missing}"
print("all required edits present")
