from mirada.audio import HOLD_SECONDS, VoiceMeter, rms_to_level, threshold_for


def test_threshold_monotonic_and_clamped():
    assert threshold_for(0) > threshold_for(50) > threshold_for(100)
    assert threshold_for(-5) == threshold_for(0)
    assert threshold_for(500) == threshold_for(100)


def test_rms_to_level():
    assert rms_to_level(0.0) == 0.0
    assert rms_to_level(1.0) == 1.0
    assert 0.0 < rms_to_level(0.01) < 1.0


def test_speaking_hold():
    v = VoiceMeter()
    v.set_sensitivity(50)
    v.feed(0.95, now=10.0)
    assert v.speaking
    v.feed(0.0, now=10.0 + HOLD_SECONDS / 2)
    assert v.speaking               # todavía dentro del margen
    v.feed(0.0, now=10.0 + HOLD_SECONDS + 0.01)
    assert not v.speaking


def test_quiet_never_speaks():
    v = VoiceMeter()
    v.set_sensitivity(50)
    for i in range(20):
        v.feed(0.05, now=100.0 + i * 0.1)
    assert not v.speaking
