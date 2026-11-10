from astra.advise import _merge, render


def test_merge_overrides_vendor_values(tmp_path):
    v = tmp_path / "v.parm"
    v.write_text("EK3_POS_I_GATE 500\nWPNAV_SPEED 800\n")
    out = _merge(v, {"EK3_POS_I_GATE": 300}, tmp_path / "m.parm").read_text().split("\n")
    assert "EK3_POS_I_GATE 300" in out and "EK3_POS_I_GATE 500" not in out and "WPNAV_SPEED 800" in out


def test_render_flags_small_samples_and_physics_limit():
    rows = [{"setting": "a", "overlay": {}, "benign_runs": 20, "benign_failed": 0, "benign_nav_alert": 0,
             "naive": "0/12", "consistent": "0/12", "errors": 0}]
    txt = render(rows, 20)
    assert "indicative only" in txt and "witness sensor" in txt and "Zero observed benign cost: a" in txt


def test_read_params_all_three_formats(tmp_path):
    from astra.sitl import read_params
    ap = tmp_path / "a.parm"; ap.write_text("# comment\nEK3_POS_I_GATE 500\nWPNAV_SPEED 800\n")
    mp = tmp_path / "b.param"; mp.write_text("EK3_POS_I_GATE,500\nWPNAV_SPEED,800\n")
    qg = tmp_path / "c.params"; qg.write_text("# Onboard parameters\n1\t1\tEK3_POS_I_GATE\t500\t9\n1\t1\tWPNAV_SPEED\t800\t9\n")
    for f in (ap, mp, qg):
        assert read_params(f) == {"EK3_POS_I_GATE": 500.0, "WPNAV_SPEED": 800.0}, f.name
