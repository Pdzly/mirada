from mirada.audio import HOLD_SECONDS, VoiceMeter, calibrate, rms_to_level, sensitivity_for_threshold, threshold_for


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


def test_sensitivity_threshold_roundtrip():
    for s in (0, 25, 55, 100):
        assert sensitivity_for_threshold(threshold_for(s)) == s


def test_calibrate_quiet_room_is_sensitive():
    sens, noise, too_noisy = calibrate([0.02, 0.03, 0.05] * 30)
    assert not too_noisy and noise < 0.1
    assert sens >= 85


def test_calibrate_fan_noise_lowers_sensitivity():
    quiet = calibrate([0.05] * 50)[0]
    fan = calibrate([0.35, 0.38, 0.40] * 30)[0]
    assert fan < quiet
    # el umbral queda sobre el ruido, y la voz normal (~0.7) lo supera
    assert 0.40 < threshold_for(fan) < 0.7


def test_calibrate_ignores_single_click():
    levels = [0.05] * 95 + [0.95] * 2
    assert calibrate(levels)[1] < 0.1


def test_calibrate_too_noisy():
    sens, _, too_noisy = calibrate([0.75] * 40)
    assert too_noisy and sens == 0


def test_capture_collects_levels():
    v = VoiceMeter()
    v.begin_capture()
    for x in (0.1, 0.2, 0.3):
        v.feed(x, now=1.0)
    assert v.end_capture() == [0.1, 0.2, 0.3]
    v.feed(0.4, now=2.0)
    assert v.end_capture() == []
