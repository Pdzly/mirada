"""Ventana del prompter: franja bajo la cámara (notch) o ventana flotante."""
from __future__ import annotations

import html
import math
import time

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPainterPath, QTextDocument, QTextOption
from PySide6.QtWidgets import QMenu, QSizeGrip, QWidget

from .audio import VoiceMeter
from .config import APP, parse_sections


class Prompter(QWidget):
    closed = Signal()

    def __init__(self, conf: dict, text: str, voice: VoiceMeter):
        super().__init__(None)
        self.conf = conf
        self.voice = voice
        self.text = text
        self.sections = parse_sections(text)
        self.offset = 0.0
        self.paused = False
        self.hovering = False
        self.countdown_end = 0.0
        self._drag: QPoint | None = None
        self._last = time.monotonic()

        self.setWindowTitle(f"{APP} — prompter")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.grip = QSizeGrip(self)
        self.grip.resize(18, 18)

        self.doc = QTextDocument()
        self.doc.setDocumentMargin(0)
        self.build_doc()
        self.apply_mode()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        self.restart()

    # ---------- documento ----------
    def build_doc(self):
        c = self.conf
        f = QFont()
        f.setPointSize(int(c["font_size"]))
        f.setWeight(QFont.Weight.Medium)
        self.doc.setDefaultFont(f)
        opt = QTextOption()
        opt.setWrapMode(QTextOption.WrapMode.WordWrap)
        self.doc.setDefaultTextOption(opt)
        parts = []
        for line in self.text.splitlines():
            s = line.strip()
            if s.startswith("#"):
                t = html.escape(s.lstrip("#").strip())
                parts.append(f'<p style="color:{c["accent_color"]};font-weight:700;'
                             f'font-size:{int(c["font_size"] * 0.8)}pt;margin-top:14px">{t}</p>')
            elif s:
                parts.append(f'<p style="color:{c["text_color"]};margin-bottom:6px">'
                             f'{html.escape(s)}</p>')
            else:
                parts.append('<p style="margin:0">&nbsp;</p>')
        self.doc.setHtml("".join(parts))
        self.relayout()

    def text_rect(self) -> QRectF:
        pad_x = 28
        top = 26 if self.conf["mode"] == "notch" else 22
        return QRectF(pad_x, top, max(100, self.width() - 2 * pad_x), max(40, self.height() - top - 14))

    def relayout(self):
        # recordar la posición de lectura relativa a la sección actual
        old_h = self.doc.size().height()
        anchor = None
        if getattr(self, "section_y", None) and self.offset > 0:
            cur = self.current_section()
            if cur >= 0:
                anchor = (cur, self.offset - (self.section_y[cur] - 4))
        self.doc.setTextWidth(self.text_rect().width())
        new_h = self.doc.size().height()
        heading_idx = {idx for _, idx in self.sections}
        self.section_y = []
        block = self.doc.begin()
        i = 0
        lay = self.doc.documentLayout()
        while block.isValid():
            if i in heading_idx:
                self.section_y.append(lay.blockBoundingRect(block).top())
            block = block.next()
            i += 1
        scale = new_h / old_h if old_h > 0 else 1.0
        if anchor and anchor[0] < len(self.section_y):
            self.offset = max(0.0, self.section_y[anchor[0]] - 4 + anchor[1] * scale)
        elif self.offset > 0:
            self.offset *= scale

    # ---------- modo / geometría ----------
    def apply_mode(self):
        c = self.conf
        scr = self.screen() or QGuiApplication.primaryScreen()
        g = scr.geometry()
        if c["mode"] == "notch":
            w, h = int(c["notch_width"]), int(c["notch_height"])
            self.setGeometry(g.x() + (g.width() - w) // 2, g.y(), w, h)
            self.grip.hide()
        else:
            x, y, w, h = c["float_geometry"]
            self.setGeometry(int(x), int(y), int(w), int(h))
            self.grip.show()
        self.relayout()

    def resizeEvent(self, e):
        self.grip.move(self.width() - self.grip.width() - 4, self.height() - self.grip.height() - 4)
        self.relayout()
        super().resizeEvent(e)

    def moveEvent(self, e):
        super().moveEvent(e)

    def remember_geometry(self):
        if self.conf["mode"] == "floating":
            g = self.geometry()
            self.conf["float_geometry"] = [g.x(), g.y(), g.width(), g.height()]

    # ---------- control ----------
    def restart(self):
        self.offset = 0.0
        self.paused = False
        self.countdown_end = time.monotonic() + int(self.conf["countdown"])

    def toggle_pause(self):
        self.paused = not self.paused

    def toggle_mode(self):
        self.remember_geometry()
        self.conf["mode"] = "floating" if self.conf["mode"] == "notch" else "notch"
        self.apply_mode()

    def jump_section(self, i: int):
        if 0 <= i < len(self.section_y):
            self.offset = max(0.0, self.section_y[i] - 4)

    def current_section(self) -> int:
        cur = -1
        for i, y in enumerate(self.section_y):
            if y - 4 <= self.offset + 2:
                cur = i
        return cur

    def next_section(self, step: int):
        cur = self.current_section()
        self.jump_section(max(0, min(len(self.section_y) - 1, cur + step)))

    def change_speed(self, d: int):
        self.conf["speed"] = max(5, min(300, int(self.conf["speed"]) + d))

    def change_font(self, d: int):
        self.conf["font_size"] = max(10, min(90, int(self.conf["font_size"]) + d))
        self.build_doc()

    def handle_remote(self, cmd: str, i: int):
        if cmd == "toggle":
            self.toggle_pause()
        elif cmd == "next":
            self.next_section(1)
        elif cmd == "prev":
            self.next_section(-1)
        elif cmd == "faster":
            self.change_speed(10)
        elif cmd == "slower":
            self.change_speed(-10)
        elif cmd == "fwd":
            self.offset += self.text_rect().height() * 0.5
        elif cmd == "back":
            self.offset = max(0.0, self.offset - self.text_rect().height() * 0.5)
        elif cmd == "restart":
            self.restart()
        elif cmd == "section":
            self.jump_section(i)

    def moving(self) -> bool:
        if self.paused or time.monotonic() < self.countdown_end:
            return False
        if self.hovering and self.conf["hover_pause"]:
            return False
        if self.conf["voice"] and self.voice.stream is not None:
            return self.voice.speaking
        return True

    def tick(self):
        now = time.monotonic()
        dt = min(0.1, now - self._last)
        self._last = now
        if self.moving():
            max_off = max(0.0, self.doc.size().height() - self.text_rect().height() * 0.3)
            self.offset = min(max_off, self.offset + float(self.conf["speed"]) * dt)
        self.update()

    # ---------- eventos ----------
    def keyPressEvent(self, e):
        k = e.key()
        K = Qt.Key
        if k == K.Key_Space:
            self.toggle_pause()
        elif k == K.Key_Up:
            self.change_speed(5)
        elif k == K.Key_Down:
            self.change_speed(-5)
        elif k == K.Key_PageDown:
            self.next_section(1)
        elif k == K.Key_PageUp:
            self.next_section(-1)
        elif k == K.Key_Home:
            self.restart()
        elif k == K.Key_V:
            self.conf["voice"] = not self.conf["voice"]
            if self.conf["voice"] and self.voice.stream is None:
                self.voice.start(self.conf["input_device"])
        elif k == K.Key_M:
            self.conf["mirror"] = not self.conf["mirror"]
        elif k == K.Key_N:
            self.toggle_mode()
        elif k in (K.Key_Plus, K.Key_Equal):
            self.change_font(2)
        elif k == K.Key_Minus:
            self.change_font(-2)
        elif K.Key_1 <= k <= K.Key_9:
            self.jump_section(k - K.Key_1)
        elif k == K.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        self.offset = max(0.0, self.offset - e.angleDelta().y() * 0.4)

    def enterEvent(self, e):
        self.hovering = True
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hovering = False
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.activateWindow()
            self.setFocus()
            # botón de pausa (esquina superior derecha)
            if self.pause_rect().contains(e.position()):
                self.toggle_pause()
                return
            if self.conf["mode"] == "floating":
                self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.addAction("Pausar / reanudar (Espacio)", self.toggle_pause)
        m.addAction("Desde el inicio (Inicio)", self.restart)
        if self.sections:
            sm = m.addMenu("Ir a sección")
            for i, (name, _) in enumerate(self.sections):
                sm.addAction(f"{i + 1}. {name}", lambda i=i: self.jump_section(i))
        m.addSeparator()
        m.addAction("Cambiar modo notch / flotante (N)", self.toggle_mode)
        m.addAction("Espejo (M)", lambda: self.conf.__setitem__("mirror", not self.conf["mirror"]))
        m.addAction("Cerrar (Esc)", self.close)
        m.exec(e.globalPos())

    def closeEvent(self, e):
        self.remember_geometry()
        self.timer.stop()
        self.closed.emit()
        super().closeEvent(e)

    # ---------- dibujo ----------
    def pause_rect(self) -> QRectF:
        return QRectF(self.width() - 34, 6, 26, 18)

    def paintEvent(self, e):
        c = self.conf
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # fondo: en modo notch, esquinas inferiores redondeadas pegado al borde superior
        path = QPainterPath()
        r = 22.0
        if c["mode"] == "notch":
            path.moveTo(0, 0)
            path.lineTo(w, 0)
            path.lineTo(w, h - r)
            path.quadTo(w, h, w - r, h)
            path.lineTo(r, h)
            path.quadTo(0, h, 0, h - r)
            path.closeSubpath()
        else:
            path.addRoundedRect(QRectF(0, 0, w, h), 16, 16)
        bg = QColor(8, 8, 10, int(c["bg_opacity"]))
        p.fillPath(path, bg)

        # haz de voz (barra superior que responde al volumen)
        if c["voice"] and self.voice.stream is not None:
            lvl = self.voice.level
            bw = w * (0.08 + 0.84 * lvl)
            col = QColor(c["accent_color"])
            col.setAlpha(230 if self.voice.speaking else 90)
            p.fillRect(QRectF((w - bw) / 2, 0 if c["mode"] == "notch" else 6, bw, 3), col)

        # texto
        tr = self.text_rect()
        p.save()
        p.setClipRect(tr)
        if c["mirror"]:
            p.translate(w, 0)
            p.scale(-1, 1)
            tr2 = QRectF(w - tr.right(), tr.top(), tr.width(), tr.height())
        else:
            tr2 = tr
        p.translate(tr2.left(), tr2.top() - self.offset)
        self.doc.drawContents(p, QRectF(0, self.offset, tr.width(), tr.height()))
        p.restore()

        # degradado inferior para suavizar el corte
        grad_h = min(30, tr.height() / 3)
        for i in range(int(grad_h)):
            a = int(c["bg_opacity"] * (i / grad_h))
            p.fillRect(QRectF(0, tr.bottom() - grad_h + i, w, 1), QColor(8, 8, 10, a))

        # icono de pausa / reproducción
        pr = self.pause_rect()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 140 if self.hovering else 70))
        if self.paused:
            tri = QPainterPath()
            tri.moveTo(pr.left() + 8, pr.top() + 2)
            tri.lineTo(pr.left() + 20, pr.center().y())
            tri.lineTo(pr.left() + 8, pr.bottom() - 2)
            tri.closeSubpath()
            p.drawPath(tri)
        else:
            p.drawRect(QRectF(pr.left() + 7, pr.top() + 2, 4, pr.height() - 4))
            p.drawRect(QRectF(pr.left() + 15, pr.top() + 2, 4, pr.height() - 4))

        # velocidad / estado pequeño
        p.setPen(QColor(255, 255, 255, 110))
        f = QFont()
        f.setPointSize(8)
        p.setFont(f)
        status = f"{int(c['speed'])} px/s"
        if c["voice"]:
            status += " · voz" if self.voice.stream is not None else " · sin micrófono"
        if self.hovering and c["hover_pause"]:
            status += " · pausa (mouse)"
        p.drawText(QRectF(10, 4, w / 2, 16), Qt.AlignmentFlag.AlignLeft, status)

        # cuenta regresiva
        left = self.countdown_end - time.monotonic()
        if left > 0:
            p.fillPath(path, QColor(8, 8, 10, 200))
            f2 = QFont()
            f2.setPointSize(max(18, int(h * 0.35)))
            f2.setBold(True)
            p.setFont(f2)
            p.setPen(QColor(c["accent_color"]))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, str(math.ceil(left)))
        p.end()
