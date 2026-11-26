"""Cálculo de posición del prompter, sin dependencias de Qt (fácil de probar).

Los rectángulos son tuplas (x, y, ancho, alto) en coordenadas lógicas del
escritorio virtual, como las entrega QScreen.geometry().
"""
from __future__ import annotations

Rect = tuple[int, int, int, int]

MIN_NOTCH_WIDTH = 250
MIN_VISIBLE = 80          # px de una ventana flotante que deben quedar visibles

CAMERA_PRESETS = {"left": 15, "center": 50, "right": 85}


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def top_panel_height(screen: Rect, avail: Rect) -> int:
    """Alto del panel superior (0 si el panel está en otro borde o no hay)."""
    return max(0, avail[1] - screen[1])


def notch_rect(screen: Rect, avail: Rect, width_pct: int, height: int,
               camera_pct: int, panel_mode: str = "below") -> Rect:
    """Rectángulo del notch.

    - width_pct: ancho como % del ancho de la pantalla (se adapta a cualquier resolución).
    - camera_pct: dónde está la cámara, 0 = borde izquierdo, 100 = borde derecho.
    - panel_mode: "below" lo pone justo bajo un panel superior; "over" lo pega al
      borde físico (para paneles que se ocultan solos).
    """
    sx, sy, sw, sh = screen
    w = int(round(clamp(sw * width_pct / 100.0, min(MIN_NOTCH_WIDTH, sw), sw)))
    top = sy + top_panel_height(screen, avail) if panel_mode == "below" else sy
    h = int(clamp(height, 40, max(40, sh // 2)))
    cx = sx + sw * clamp(camera_pct, 0, 100) / 100.0
    x = int(round(clamp(cx - w / 2.0, sx, sx + sw - w)))
    return (x, top, w, h)


def intersection_area(a: Rect, b: Rect) -> int:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return max(0, x2 - x1) * max(0, y2 - y1)


def fit_floating(rect: Rect, avails: list[Rect], fallback: Rect) -> Rect:
    """Si la ventana flotante quedó fuera de todas las pantallas (por ejemplo,
    se desconectó el monitor externo), la centra en `fallback`. Si sigue
    visible, la deja donde está pero ajusta su tamaño a la pantalla."""
    x, y, w, h = rect
    visible = any(intersection_area(rect, a) >= MIN_VISIBLE * MIN_VISIBLE for a in avails)
    if visible:
        return rect
    fx, fy, fw, fh = fallback
    w, h = min(w, fw), min(h, fh)
    return (fx + (fw - w) // 2, fy + (fh - h) // 3, w, h)
