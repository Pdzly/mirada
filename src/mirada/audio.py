"""Detección de voz por volumen del micrófono (sin reconocimiento de palabras)."""
from __future__ import annotations

import math
import time

try:
    import numpy as np
    import sounddevice as sd
    AUDIO_OK = True
    AUDIO_ERR = ""
except Exception as e:  # PortAudio ausente, etc.
    np = None
    sd = None
    AUDIO_OK = False
    AUDIO_ERR = str(e)

# Tiempo que se sigue considerando "hablando" tras el último sonido,
# para no cortar entre palabras.
HOLD_SECONDS = 0.45


def threshold_for(sensitivity: int) -> float:
    """Más sensibilidad = umbral más bajo. Devuelve un nivel 0..1."""
    s = max(0, min(100, int(sensitivity)))
    return 0.78 - (s / 100.0) * 0.6


def rms_to_level(rms: float) -> float:
    """Convierte RMS lineal a un nivel 0..1 en una escala de -60..0 dBFS."""
    db = 20.0 * math.log10(max(0.0, rms) + 1e-9)
    return max(0.0, min(1.0, (db + 60.0) / 60.0))


def input_devices() -> list[tuple[int, str]]:
    if not AUDIO_OK:
        return []
    try:
        return [(i, d["name"]) for i, d in enumerate(sd.query_devices())
                if d.get("max_input_channels", 0) > 0]
    except Exception:
        return []


class VoiceMeter:
    def __init__(self):
        self.level = 0.0          # 0..1 suavizado
        self.speaking = False
        self._last_loud = 0.0
        self.threshold = threshold_for(55)
        self.stream = None
        self.error = ""

    def set_sensitivity(self, sens: int):
        self.threshold = threshold_for(sens)

    def start(self, device: str = "") -> bool:
        self.stop()
        if not AUDIO_OK:
            self.error = AUDIO_ERR
            return False
        try:
            dev = None
            if device:
                dev = int(device) if device.isdigit() else device
            self.stream = sd.InputStream(device=dev, channels=1, blocksize=1024,
                                         dtype="float32", callback=self._cb)
            self.stream.start()
            self.error = ""
            return True
        except Exception as e:
            self.error = str(e)
            self.stream = None
            return False

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
        self.stream = None
        self.level = 0.0
        self.speaking = False

    def feed(self, lvl: float, now: float | None = None):
        """Actualiza el estado con un nivel 0..1 (separado para poder probarlo)."""
        if now is None:
            now = time.monotonic()
        # ataque rápido, caída lenta
        self.level = lvl if lvl > self.level else self.level * 0.85 + lvl * 0.15
        if lvl >= self.threshold:
            self._last_loud = now
        self.speaking = (now - self._last_loud) < HOLD_SECONDS

    def _cb(self, indata, frames, t, status):
        rms = float(np.sqrt(np.mean(np.square(indata))))
        self.feed(rms_to_level(rms))
