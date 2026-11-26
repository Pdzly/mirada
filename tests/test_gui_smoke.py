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
