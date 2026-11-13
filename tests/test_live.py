from astra.live import LiveHealth


def _fly(h, t0, t1, lat=60.0, fix=3, sats=12, hacc=1.0):
    t = t0
    while t < t1:
        h.feed(t, fix, lat, 25.0, sats if fix >= 3 else 0, hacc, 5.0, 90.0, 30.0)
        t += 0.2


def test_benign_flight_stays_ok():
    h = LiveHealth()
    _fly(h, 0, 120)
    assert h.state() == "ok" and not h.events


def test_outage_is_jamming_like():
    h = LiveHealth()
    _fly(h, 0, 60)
    _fly(h, 60, 80, fix=1)
    _fly(h, 80, 100)
    assert h.state() == "jamming-like"


def test_capture_jump_after_outage_is_spoofing_like():
    h = LiveHealth()
    _fly(h, 0, 60)
    _fly(h, 60, 80, fix=1)
    _fly(h, 80, 100, lat=62.0)  # ~220 km away after 20 s
    assert h.state() == "spoofing-like"
    assert any("jumped" in e[2] for e in h.events)


def test_short_dropout_is_not_an_alarm():
    h = LiveHealth()
    _fly(h, 0, 60)
    _fly(h, 60, 61, fix=1)
    _fly(h, 61, 100)
    assert h.state() == "ok"


def test_shield_is_not_fooled_by_an_outage():
    import numpy as np
    cal = {"sigma_inv": (np.eye(2) * 100).tolist(), "k": 2.5, "h": 8.0}
    h = LiveHealth(shield_cal=cal)
    def hover(t0, t1, lat=60.0, fix=3):  # consistent: position fixed, velocity 0
        t = t0
        while t < t1:
            h.feed(t, fix, lat, 25.0, 12 if fix >= 3 else 0, 1.0, 0.0, 0.0, 30.0)
            t += 0.2
    hover(0, 60)
    hover(60, 80, fix=1)
    hover(80, 140, lat=60.0005)  # benign 55 m re-acquisition offset after 20 s
    assert not any(e[1] == "spoof" for e in h.events)
