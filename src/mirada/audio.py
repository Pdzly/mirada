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


def sensitivity_for_threshold(threshold: float) -> int:
    """Inversa de threshold_for: qué sensibilidad (0-100) da ese umbral."""
    return int(round(max(0.0, min(100.0, (0.78 - threshold) / 0.006))))


# Cuánto por encima del ruido de fondo tiene que estar la voz.
CALIBRATION_MARGIN = 0.12
CALIBRATION_SECONDS = 3.0


def calibrate(levels: list[float], margin: float = CALIBRATION_MARGIN) -> tuple[int, float, bool]:
    """A partir de niveles medidos en silencio, propone una sensibilidad.

    Usa el percentil 90 del ruido (ignora un clic aislado) más un margen.
    Devuelve (sensibilidad, nivel_de_ruido, demasiado_ruido).
    """
    if not levels:
        raise ValueError("no hay muestras de audio")
    s = sorted(levels)
    noise = s[min(len(s) - 1, int(len(s) * 0.9))]
    threshold = noise + margin
    too_noisy = threshold > threshold_for(0)
    return sensitivity_for_threshold(max(threshold_for(100), threshold)), noise, too_noisy


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
        self._samples: list[float] | None = None

    def begin_capture(self):
        """Empieza a guardar los niveles crudos (para calibrar)."""
        self._samples = []

    def end_capture(self) -> list[float]:
        out, self._samples = self._samples or [], None
        return out

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
        if self._samples is not None:
            self._samples.append(lvl)
        # ataque rápido, caída lenta
        self.level = lvl if lvl > self.level else self.level * 0.85 + lvl * 0.15
        if lvl >= self.threshold:
            self._last_loud = now
        self.speaking = (now - self._last_loud) < HOLD_SECONDS

    def _cb(self, indata, frames, t, status):
        rms = float(np.sqrt(np.mean(np.square(indata))))
        self.feed(rms_to_level(rms))
