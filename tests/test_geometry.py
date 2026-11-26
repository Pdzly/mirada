from mirada.geometry import fit_floating, notch_rect, top_panel_height

FHD = (0, 0, 1920, 1080)
KDE_TOP_PANEL = (0, 32, 1920, 1048)        # panel de 32 px arriba (caso real)
BOTTOM_PANEL = (0, 0, 1920, 1040)          # panel abajo: no afecta al notch


def test_top_panel_height():
    assert top_panel_height(FHD, KDE_TOP_PANEL) == 32
    assert top_panel_height(FHD, BOTTOM_PANEL) == 0
    assert top_panel_height(FHD, FHD) == 0


def test_notch_below_top_panel():
    x, y, w, h = notch_rect(FHD, KDE_TOP_PANEL, 32, 150, 50, "below")
    assert y == 32
    assert (w, h) == (614, 150)
    assert x == 653                                  # centrado: (1920 - 614) / 2


def test_notch_over_panel_sticks_to_edge():
    assert notch_rect(FHD, KDE_TOP_PANEL, 32, 150, 50, "over")[1] == 0


def test_bottom_panel_does_not_move_notch():
    assert notch_rect(FHD, BOTTOM_PANEL, 32, 150, 50, "below")[1] == 0


def test_second_monitor_with_offset():
    # monitor externo a la derecha de un notebook de 1366 px
    ext = (1366, 0, 2560, 1440)
    x, y, w, h = notch_rect(ext, (1366, 40, 2560, 1400), 30, 160, 50)
    assert y == 40
    assert 1366 <= x and x + w <= 1366 + 2560
    assert abs((x + w / 2) - (1366 + 1280)) <= 1


def test_width_is_relative_to_screen():
    small = notch_rect((0, 0, 1366, 768), (0, 0, 1366, 768), 32, 150, 50)[2]
    big = notch_rect((0, 0, 3840, 2160), (0, 0, 3840, 2160), 32, 150, 50)[2]
    assert small == 437 and big == 1229


def test_width_has_minimum_and_maximum():
    assert notch_rect(FHD, FHD, 1, 150, 50)[2] == 250
    assert notch_rect((0, 0, 200, 300), (0, 0, 200, 300), 100, 150, 50)[2] == 200


def test_camera_position_clamped_inside_screen():
    x, _, w, _ = notch_rect(FHD, FHD, 32, 150, 0)
    assert x == 0
    x, _, w, _ = notch_rect(FHD, FHD, 32, 150, 100)
    assert x + w == 1920
    x, _, w, _ = notch_rect(FHD, FHD, 32, 150, 75)
    assert abs((x + w / 2) - 1440) <= 1          # centrado en la cámara
    x, _, w, _ = notch_rect(FHD, FHD, 32, 150, 85)
    assert x + w == 1920                         # no cabe centrado: se pega al borde


def test_height_limited_to_half_screen():
    assert notch_rect(FHD, FHD, 32, 5000, 50)[3] == 540


def test_floating_kept_when_visible():
    r = (100, 100, 760, 300)
    assert fit_floating(r, [KDE_TOP_PANEL], KDE_TOP_PANEL) == r


def test_floating_recovered_when_monitor_unplugged():
    # estaba en un monitor externo que ya no existe
    r = (2500, 200, 760, 300)
    x, y, w, h = fit_floating(r, [KDE_TOP_PANEL], KDE_TOP_PANEL)
    assert (w, h) == (760, 300)
    assert 0 <= x and x + w <= 1920 and 32 <= y and y + h <= 1080


def test_floating_shrunk_to_small_screen():
    r = (5000, 0, 3000, 2000)
    small = (0, 0, 1366, 768)
    x, y, w, h = fit_floating(r, [small], small)
    assert w <= 1366 and h <= 768
