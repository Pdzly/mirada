"""Configuración persistente, guion de ejemplo y utilidades sin dependencias de Qt."""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

APP = "Mirada"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "mirada"


def config_file() -> Path:
    return config_dir() / "config.json"


def script_file() -> Path:
    return config_dir() / "guion.md"


DEFAULTS: dict = {
    "mode": "notch",            # notch | floating
    "notch_width_pct": 32,      # % del ancho de la pantalla
    "notch_height": 150,
    "screen": "",               # nombre de la pantalla; vacío = principal
    "camera_x_pct": 50,         # posición horizontal de la cámara, 0-100
    "panel_mode": "below",      # below | over (respecto de un panel superior)
    "float_geometry": [200, 200, 760, 300],
    "font_size": 26,
    "text_color": "#f2f2f2",
    "accent_color": "#ff7a59",
    "bg_opacity": 235,
    "speed": 45,                # píxeles por segundo
    "voice": True,
    "sensitivity": 55,          # 0-100
    "input_device": "",         # vacío = por defecto
    "mirror": False,
    "countdown": 3,
    "hover_pause": True,
    "remote": False,
    "remote_port": 8765,
    "remote_token": "",
}

# Rangos válidos para los valores numéricos (se recortan al cargar).
RANGES: dict[str, tuple[int, int]] = {
    "notch_width_pct": (15, 100),
    "camera_x_pct": (0, 100),
    "notch_height": (60, 1200),
    "font_size": (10, 90),
    "bg_opacity": (80, 255),
    "speed": (5, 300),
    "sensitivity": (0, 100),
    "countdown": (0, 10),
    "remote_port": (1024, 65535),
}

MODES = ("notch", "floating")
PANEL_MODES = ("below", "over")

SAMPLE = """# Apertura
Hola a todos, gracias por estar aquí.
Hoy les voy a mostrar cómo funciona Mirada, un teleprompter para Linux.

# Cómo funciona
El texto avanza mientras hablas y se detiene cuando haces una pausa.
Si pasas el mouse por encima, se pausa. Con las flechas cambias la velocidad.

# Cierre
Las líneas que empiezan con # crean secciones. Puedes saltar entre ellas con las teclas 1 a 9.
¡Gracias!
"""


def new_token() -> str:
    return secrets.token_urlsafe(16)


def sanitize(raw: object) -> dict:
    """Combina `raw` con los valores por defecto, descartando claves
    desconocidas y valores de tipo incorrecto o fuera de rango."""
    conf = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
    if not isinstance(raw, dict):
        raw = {}
    for key, default in DEFAULTS.items():
        if key not in raw:
            continue
        val = raw[key]
        if isinstance(default, bool):
            if isinstance(val, bool):
                conf[key] = val
        elif isinstance(default, int):
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                lo, hi = RANGES.get(key, (-(10**9), 10**9))
                conf[key] = max(lo, min(hi, int(val)))
        elif isinstance(default, str):
            if isinstance(val, str):
                conf[key] = val
        elif isinstance(default, list):
            if (isinstance(val, list) and len(val) == len(default)
                    and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in val)):
                conf[key] = [int(x) for x in val]
    if conf["mode"] not in MODES:
        conf["mode"] = DEFAULTS["mode"]
    if conf["panel_mode"] not in PANEL_MODES:
        conf["panel_mode"] = DEFAULTS["panel_mode"]
    # Códigos antiguos (cortos) se reemplazan por uno más largo.
    if len(conf["remote_token"]) < 16:
        conf["remote_token"] = new_token()
    return conf


def load_conf() -> dict:
    try:
        raw = json.loads(config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    return sanitize(raw)


def save_conf(conf: dict) -> None:
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(conf, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def parse_sections(text: str) -> list[tuple[str, int]]:
    """Devuelve [(título, índice_de_línea)] para líneas que empiezan con #."""
    out: list[tuple[str, int]] = []
    for i, line in enumerate(text.splitlines()):
        s = line.strip()
        if s.startswith("#"):
            out.append((s.lstrip("#").strip() or f"Sección {len(out) + 1}", i))
    return out


def reading_minutes(text: str, wpm: int = 140) -> float:
    return len(text.split()) / float(wpm)
