"""Diálogo de ajustes."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
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

from .audio import AUDIO_OK, CALIBRATION_SECONDS, VoiceMeter, calibrate, input_devices
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
        self.calib_btn = QPushButton("Calibrar con 3 s de silencio")
        self.calib_btn.setToolTip("Mide el ruido de fondo (ventilador, teclado, calle) y ajusta la sensibilidad.")
        self.calib_btn.clicked.connect(self.start_calibration)
        self.calib_btn.setEnabled(AUDIO_OK)
        row = QHBoxLayout(); row.addWidget(self.sens, 1); row.addWidget(self.calib_btn)
        f.addRow("Sensibilidad del micrófono", row)
        self.calib_msg = QLabel()
        self.calib_msg.setStyleSheet("color: gray")
        self.calib_msg.setWordWrap(True)
        self.calib_msg.hide()
        f.addRow("", self.calib_msg)
        self._calib_meter: VoiceMeter | None = None
        self._calib_left = 0

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

    # ---------- calibración ----------
    def start_calibration(self):
        meter = VoiceMeter()
        if not meter.start(self.device.currentData() or ""):
            self.show_calib(f"No se pudo abrir el micrófono: {meter.error}")
            return
        self._calib_meter = meter
        meter.begin_capture()
        self._calib_left = int(CALIBRATION_SECONDS)
        self.calib_btn.setEnabled(False)
        self.show_calib("Silencio, por favor: midiendo el ruido de fondo…")
        self._calib_tick()

    def _calib_tick(self):
        if self._calib_meter is None:       # se cerró el diálogo a mitad de la medición
            return
        if self._calib_left > 0:
            self.calib_btn.setText(f"Midiendo… {self._calib_left}")
            self._calib_left -= 1
            QTimer.singleShot(1000, self._calib_tick)
            return
        meter, self._calib_meter = self._calib_meter, None
        levels = meter.end_capture()
        meter.stop()
        self.calib_btn.setText("Calibrar con 3 s de silencio")
        self.calib_btn.setEnabled(True)
        if not levels:
            self.show_calib("No llegó audio del micrófono. Revisa que esté conectado y sin silenciar.")
            return
        sens, noise, too_noisy = calibrate(levels)
        self.sens.setValue(sens)
        if too_noisy:
            self.show_calib("Hay mucho ruido de fondo: dejé la sensibilidad al mínimo. Usa audífonos con "
                            "micrófono o desactiva la voz (V) y avanza a velocidad fija.")
        else:
            self.show_calib(f"Listo: ruido de fondo {round(noise * 100)} %, sensibilidad ajustada a {sens}. "
                            "Pulsa Aceptar para guardar.")

    def show_calib(self, msg: str):
        self.calib_msg.setText(msg)
        self.calib_msg.show()

    def done(self, r):
        if self._calib_meter is not None:
            self._calib_meter.stop()
            self._calib_meter = None
        super().done(r)

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
