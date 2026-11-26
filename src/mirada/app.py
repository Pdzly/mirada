"""Ventana principal (editor de guion) y punto de entrada."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QPlainTextEdit, QStatusBar, QToolBar

from . import __version__
from .audio import AUDIO_OK, VoiceMeter
from .config import APP, SAMPLE, load_conf, parse_sections, reading_minutes, save_conf, script_file
from .prompter import Prompter
from .remote import RemoteBridge
from .settings import SettingsDialog

HELP = """Atajos en el prompter:
  Espacio        pausar / reanudar
  ↑ / ↓          más rápido / más lento
  RePág / AvPág  sección anterior / siguiente
  1-9            saltar a la sección N
  Inicio         volver al principio (con cuenta regresiva)
  V              activar / desactivar seguimiento por voz
  M              modo espejo
  + / -          tamaño de letra
  N              alternar modo notch / flotante
  ← / →          mover el notch para alinearlo con la cámara (Shift: más rápido)
  Esc            cerrar prompter
Rueda del mouse: desplazamiento manual. Pasar el mouse encima: pausa."""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.conf = load_conf()
        self.voice = VoiceMeter()
        self.voice.set_sensitivity(self.conf["sensitivity"])
        self.prompter: Prompter | None = None
        self.path: Path | None = None
        self.remote = RemoteBridge()
        self.remote.command.connect(self.on_remote)
        self.remote_url = ""

        self.setWindowTitle(APP)
        self.resize(900, 640)
        self.editor = QPlainTextEdit()
        f = QFont("monospace")
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPointSize(12)
        self.editor.setFont(f)
        self.editor.setPlaceholderText("Escribe o pega tu guion aquí. Usa # Título para crear secciones.")
        try:
            self.editor.setPlainText(script_file().read_text(encoding="utf-8"))
        except Exception:
            self.editor.setPlainText(SAMPLE)
        self.setCentralWidget(self.editor)

        tb = QToolBar("Principal")
        tb.setMovable(False)
        self.addToolBar(tb)

        def act(label, slot, shortcut=None):
            a = QAction(label, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            tb.addAction(a)
            return a

        act("▶ Iniciar prompter", self.start_prompter, "Ctrl+Return")
        act("■ Detener", self.stop_prompter, "Ctrl+.")
        tb.addSeparator()
        act("Abrir…", self.open_file, "Ctrl+O")
        act("Guardar", self.save_file, "Ctrl+S")
        act("Guardar como…", self.save_as)
        tb.addSeparator()
        act("Ajustes", self.open_settings, "Ctrl+,")
        act("Ayuda", self.show_help, "F1")

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.editor.textChanged.connect(self.update_status)
        self.update_status()
        self.apply_remote()

        self.autosave = QTimer(self)
        self.autosave.timeout.connect(self.save_internal)
        self.autosave.start(5000)

        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self.push_state)
        self.state_timer.start(500)

    # ---------- archivos ----------
    def save_internal(self):
        try:
            path = script_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.editor.toPlainText(), encoding="utf-8")
        except OSError:
            pass

    def open_file(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Abrir guion", str(Path.home()),
                                            "Texto (*.txt *.md);;Todos (*)")
        if fn:
            self.path = Path(fn)
            self.editor.setPlainText(self.path.read_text(encoding="utf-8", errors="replace"))
            self.setWindowTitle(f"{APP} — {self.path.name}")

    def save_file(self):
        if self.path is None:
            return self.save_as()
        self.path.write_text(self.editor.toPlainText(), encoding="utf-8")
        self.status.showMessage(f"Guardado en {self.path}", 3000)

    def save_as(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Guardar guion", str(Path.home() / "guion.md"),
                                            "Markdown (*.md);;Texto (*.txt)")
        if fn:
            self.path = Path(fn)
            self.save_file()
            self.setWindowTitle(f"{APP} — {self.path.name}")

    # ---------- prompter ----------
    def start_prompter(self):
        self.stop_prompter()
        self.save_internal()
        self.voice.set_sensitivity(self.conf["sensitivity"])
        if self.conf["voice"]:
            if not self.voice.start(self.conf["input_device"]):
                self.status.showMessage(f"Micrófono no disponible, avance a velocidad fija: {self.voice.error}", 8000)
        self.prompter = Prompter(self.conf, self.editor.toPlainText(), self.voice)
        self.prompter.closed.connect(self.on_prompter_closed)
        self.prompter.show()
        self.prompter.raise_()
        self.prompter.activateWindow()
        self.prompter.setFocus()

    def stop_prompter(self):
        if self.prompter is not None:
            self.prompter.close()

    def on_prompter_closed(self):
        self.prompter = None
        self.voice.stop()
        save_conf(self.conf)

    # ---------- remoto ----------
    def apply_remote(self):
        if self.conf["remote"]:
            self.remote_url = self.remote.start(int(self.conf["remote_port"]), self.conf["remote_token"])
        else:
            self.remote.stop()
            self.remote_url = ""
        self.update_status()

    def on_remote(self, cmd: str, i: int):
        if self.prompter is None:
            if cmd in ("toggle", "restart"):
                self.start_prompter()
            return
        self.prompter.handle_remote(cmd, i)

    def push_state(self):
        p = self.prompter
        self.remote.state = {
            "open": p is not None,
            "paused": bool(p.paused) if p else True,
            "speed": int(self.conf["speed"]),
            "sections": [n for n, _ in parse_sections(self.editor.toPlainText())],
        }

    # ---------- ajustes / ayuda ----------
    def open_settings(self):
        d = SettingsDialog(self.conf, self)
        if d.exec():
            d.apply()
            save_conf(self.conf)
            self.voice.set_sensitivity(self.conf["sensitivity"])
            self.apply_remote()
            if self.prompter is not None:
                self.prompter.build_doc()
                self.prompter.apply_mode()

    def show_help(self):
        txt = f"{APP} {__version__}\n\n{HELP}"
        if self.remote_url:
            txt += f"\n\nControl remoto: abre en tu teléfono\n{self.remote_url}"
        QMessageBox.information(self, "Ayuda de Mirada", txt)

    def update_status(self):
        n = len(parse_sections(self.editor.toPlainText()))
        words = len(self.editor.toPlainText().split())
        mins = reading_minutes(self.editor.toPlainText())
        msg = f"{words} palabras · ~{mins:.1f} min a 140 ppm · {n} secciones"
        if self.remote_url:
            msg += f" · Remoto: {self.remote_url}"
        if not AUDIO_OK:
            msg += " · Sin audio (instala PortAudio)"
        self.status.showMessage(msg)

    def closeEvent(self, e):
        self.save_internal()
        self.stop_prompter()
        self.remote.stop()
        save_conf(self.conf)
        super().closeEvent(e)


def app_icon() -> QIcon:
    bundled = Path(__file__).with_name("mirada.svg")
    icon = QIcon.fromTheme("mirada")
    if icon.isNull() and bundled.exists():
        icon = QIcon(str(bundled))
    return icon if not icon.isNull() else QIcon.fromTheme("accessories-text-editor")


def setup_platform() -> None:
    """En Wayland, Qt no puede posicionar ventanas ni mantenerlas encima;
    XWayland (xcb) sí, así que se usa por defecto."""
    if (os.environ.get("WAYLAND_DISPLAY") and "QT_QPA_PLATFORM" not in os.environ
            and os.environ.get("MIRADA_WAYLAND") != "1"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def main():
    if "--version" in sys.argv:
        print(f"mirada {__version__}")
        return
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Uso: mirada [--start] [--version]\n  --start   abre el prompter directamente")
        return
    setup_platform()
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setDesktopFileName("mirada")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())
    w = MainWindow()
    w.show()
    if "--start" in sys.argv:
        QTimer.singleShot(300, w.start_prompter)
    sys.exit(app.exec())

