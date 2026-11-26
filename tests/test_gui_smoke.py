"""Arranca la interfaz sin pantalla (QT_QPA_PLATFORM=offscreen)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_main_window_and_prompter(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from mirada.app import MainWindow
    from mirada.settings import SettingsDialog

    w = MainWindow()
    w.conf["voice"] = False
    w.start_prompter()
    p = w.prompter
    assert p is not None and len(p.section_y) == 3
    p.jump_section(2)
    assert p.current_section() == 2
    p.toggle_mode()
    assert w.conf["mode"] == "floating"
    p.grab()                                   # ejecuta paintEvent
    SettingsDialog(w.conf, w).apply()
    w.stop_prompter()
    w.close()
    assert (tmp_path / "mirada" / "config.json").exists()


def test_camera_keys_and_battery_timer(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QGuiApplication, QKeyEvent

    from mirada.app import MainWindow
    from mirada.prompter import FPS_IDLE, FPS_MOVING

    w = MainWindow()
    w.conf.update(voice=False, mode="notch", camera_x_pct=50, countdown=0)
    w.start_prompter()
    p = w.prompter
    scr = QGuiApplication.primaryScreen().geometry()
    center = p.geometry().center().x()
    assert abs(center - scr.center().x()) <= 2

    def key(k, mod=Qt.KeyboardModifier.NoModifier):
        p.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, k, mod))

    key(Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert w.conf["camera_x_pct"] == 55
    assert p.geometry().center().x() > center
    key(Qt.Key.Key_Left)
    assert w.conf["camera_x_pct"] == 54

    # en pausa y sin voz, el temporizador baja de frecuencia
    p.paused = True
    p.countdown_end = 0
    p.tick()
    assert p.timer.interval() == FPS_IDLE
    key(Qt.Key.Key_Space)            # reanudar
    p.tick()
    assert p.timer.interval() == FPS_MOVING

    # el ajuste muestra la pantalla y no rompe al aplicar
    from mirada.settings import SettingsDialog
    d = SettingsDialog(w.conf, w)
    assert d.screen_box.count() >= 2
    d.cam_preset.setCurrentIndex(d.cam_preset.findData("right"))
    d._preset_chosen(0)
    d.apply()
    assert w.conf["camera_x_pct"] == 85
    w.stop_prompter()
    w.close()
