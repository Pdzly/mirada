"""Diálogo de ajustes."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
)

from .audio import AUDIO_OK, input_devices
from .geometry import CAMERA_PRESETS, top_panel_height
from .prompter import rect_tuple, target_screen


def screen_label(s) -> str:
    g = s.geometry()
    model = " ".join(x for x in (s.manufacturer(), s.model()) if x).strip()
    extra = f" — {model}" if model else ""
    primary = " (principal)" if s is QGuiApplication.primaryScreen() else ""
    return f"{s.name()}{extra} · {g.width()}×{g.height()}{primary}"


class SettingsDialog(QDialog):
    def __init__(self, conf: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustes de Mirada")
        self.conf = conf
        f = QFormLayout(self)

        self.mode = QComboBox()
        self.mode.addItem("Notch (franja bajo la cámara)", "notch")
        self.mode.addItem("Ventana flotante", "floating")
        self.mode.setCurrentIndex(0 if conf["mode"] == "notch" else 1)
        f.addRow("Modo", self.mode)

        # --- pantalla ---
        self.screen_box = QComboBox()
        self.screen_box.addItem("Automática (pantalla principal)", "")
        for s in QGuiApplication.screens():
            self.screen_box.addItem(screen_label(s), s.name())
        idx = self.screen_box.findData(conf["screen"])
        if idx < 0 and conf["screen"]:
            self.screen_box.addItem(f"{conf['screen']} (no conectada)", conf["screen"])
            idx = self.screen_box.count() - 1
        self.screen_box.setCurrentIndex(max(0, idx))
        self.screen_box.currentIndexChanged.connect(self.update_panel_hint)
        f.addRow("Pantalla", self.screen_box)

        # --- posición de la cámara ---
        self.cam_preset = QComboBox()
        for label, key in (("Centro", "center"), ("Izquierda", "left"), ("Derecha", "right"),
                           ("Personalizada", "custom")):
            self.cam_preset.addItem(label, key)
        self.cam_pct = QSpinBox(); self.cam_pct.setRange(0, 100); self.cam_pct.setSuffix(" %")
        self.cam_pct.setValue(conf["camera_x_pct"])
        self.cam_pct.setToolTip("0 % = borde izquierdo, 100 % = borde derecho.\n"
                                "En el prompter también puedes usar ← / →.")
        self._sync_preset(conf["camera_x_pct"])
        self.cam_preset.activated.connect(self._preset_chosen)
        self.cam_pct.valueChanged.connect(self._sync_preset)
        row = QHBoxLayout(); row.addWidget(self.cam_preset); row.addWidget(self.cam_pct)
        f.addRow("Posición de la cámara", row)

        # --- panel superior ---
        self.panel = QComboBox()
        self.panel.addItem("Bajo el panel superior (recomendado)", "below")
        self.panel.addItem("Sobre el panel (si el panel se oculta solo)", "over")
        self.panel.setCurrentIndex(max(0, self.panel.findData(conf["panel_mode"])))
        self.panel_hint = QLabel()
        self.panel_hint.setStyleSheet("color: gray")
        f.addRow("Panel", self.panel)
        f.addRow("", self.panel_hint)
        self.update_panel_hint()

        # --- tamaño ---
        self.nw = QSpinBox(); self.nw.setRange(15, 100); self.nw.setSuffix(" % del ancho")
        self.nw.setValue(conf["notch_width_pct"])
        self.nh = QSpinBox(); self.nh.setRange(60, 800); self.nh.setSuffix(" px de alto")
        self.nh.setValue(conf["notch_height"])
        row = QHBoxLayout(); row.addWidget(self.nw); row.addWidget(self.nh)
        f.addRow("Tamaño del notch", row)

        self.font = QSpinBox(); self.font.setRange(10, 90); self.font.setValue(conf["font_size"])
        f.addRow("Tamaño de letra", self.font)

        self.text_color = conf["text_color"]
        self.btn_color = QPushButton(self.text_color)
        self.btn_color.clicked.connect(self.pick_color)
        f.addRow("Color del texto", self.btn_color)

        self.opacity = QSlider(Qt.Orientation.Horizontal); self.opacity.setRange(80, 255)
        self.opacity.setValue(conf["bg_opacity"])
        f.addRow("Opacidad del fondo", self.opacity)

        self.speed = QSpinBox(); self.speed.setRange(5, 300); self.speed.setValue(conf["speed"])
        self.speed.setSuffix(" px/s")
        f.addRow("Velocidad por defecto", self.speed)

        self.voice = QCheckBox("Avanzar solo mientras hablo")
        self.voice.setChecked(conf["voice"])
        if not AUDIO_OK:
            self.voice.setText("Seguimiento por voz no disponible (falta PortAudio)")
            self.voice.setEnabled(False)
        f.addRow("Voz", self.voice)

        self.sens = QSlider(Qt.Orientation.Horizontal); self.sens.setRange(0, 100)
        self.sens.setValue(conf["sensitivity"])
        f.addRow("Sensibilidad del micrófono", self.sens)

        self.device = QComboBox()
        self.device.addItem("Predeterminado del sistema", "")
        for i, name in input_devices():
            self.device.addItem(f"{i}: {name}", str(i))
        idx = self.device.findData(conf["input_device"])
        self.device.setCurrentIndex(max(0, idx))
        f.addRow("Micrófono", self.device)

        self.countdown = QSpinBox(); self.countdown.setRange(0, 10); self.countdown.setValue(conf["countdown"])
        self.countdown.setSuffix(" s")
        f.addRow("Cuenta regresiva", self.countdown)

        self.hover = QCheckBox("Pausar al pasar el mouse"); self.hover.setChecked(conf["hover_pause"])
        f.addRow("", self.hover)
        self.mirror = QCheckBox("Modo espejo (para teleprompter con cristal)"); self.mirror.setChecked(conf["mirror"])
        f.addRow("", self.mirror)

        self.remote = QCheckBox("Activar control remoto desde el teléfono (misma red Wi-Fi)")
        self.remote.setChecked(conf["remote"])
        f.addRow("Remoto", self.remote)
        self.port = QSpinBox(); self.port.setRange(1024, 65535); self.port.setValue(conf["remote_port"])
        f.addRow("Puerto", self.port)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def _sync_preset(self, pct: int):
        key = next((k for k, v in CAMERA_PRESETS.items() if v == pct), "custom")
        self.cam_preset.setCurrentIndex(self.cam_preset.findData(key))

    def _preset_chosen(self, _i: int):
        key = self.cam_preset.currentData()
        if key in CAMERA_PRESETS:
            self.cam_pct.setValue(CAMERA_PRESETS[key])

    def update_panel_hint(self, *_):
        s = target_screen({"screen": self.screen_box.currentData()})
        h = top_panel_height(rect_tuple(s.geometry()), rect_tuple(s.availableGeometry()))
        self.panel_hint.setText(f"Panel superior detectado: {h} px" if h else
                                "No se detectó un panel en el borde superior de esta pantalla.")

    def pick_color(self):
        col = QColorDialog.getColor(QColor(self.text_color), self)
        if col.isValid():
            self.text_color = col.name()
            self.btn_color.setText(self.text_color)

    def apply(self):
        c = self.conf
        c["mode"] = self.mode.currentData()
        c["notch_width_pct"] = self.nw.value()
        c["screen"] = self.screen_box.currentData()
        c["camera_x_pct"] = self.cam_pct.value()
        c["panel_mode"] = self.panel.currentData()
        c["notch_height"] = self.nh.value()
        c["font_size"] = self.font.value()
        c["text_color"] = self.text_color
        c["bg_opacity"] = self.opacity.value()
        c["speed"] = self.speed.value()
        c["voice"] = self.voice.isChecked()
        c["sensitivity"] = self.sens.value()
        c["input_device"] = self.device.currentData()
        c["countdown"] = self.countdown.value()
        c["hover_pause"] = self.hover.isChecked()
        c["mirror"] = self.mirror.isChecked()
        c["remote"] = self.remote.isChecked()
        c["remote_port"] = self.port.value()
