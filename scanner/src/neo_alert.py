"""Neumorphic toast/alert popup — matches Themesberg Neumorphism UI alerts.

Uses a frameless QDialog (same base as every other scanner popup) so it
renders correctly on Windows with painted shadows and transparency.

The dialog is non-modal, auto-positions near the top-center of the screen,
auto-scales to content, fades in, then fades out and closes itself.

Usage:
    NeoAlertPopup.success(parent, "Connected successfully!")
    NeoAlertPopup.error(parent, "Connection failed.", title="Error")
    NeoAlertPopup.warning(parent, "Session will expire soon.")
    NeoAlertPopup.info(parent, "Sync complete.", duration_ms=2000)
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QWidget

from . import styles
from .shadows import NEO_RADIUS_SM, paint_neo_raised


# ── Variant definitions ──────────────────────────────────────────────

_VARIANTS = {
    "success": {
        "color": styles.ACCENT_GREEN,
        "icon": "\u2714",
        "default_title": "Success",
    },
    "error": {
        "color": styles.ACCENT_RED,
        "icon": "\u2716",
        "default_title": "Error",
    },
    "warning": {
        "color": styles.ACCENT_AMBER,
        "icon": "\u26A0",
        "default_title": "Warning",
    },
    "info": {
        "color": styles.ACCENT_INFO,
        "icon": "\u2139",
        "default_title": "Info",
    },
}

# Layout constants
_SHADOW = 16            # painted shadow margin
_PAD_H = 22            # horizontal content padding
_PAD_V = 16            # vertical content padding
_BAR_W = 5             # left accent bar width
_ICON_D = 28           # icon circle diameter
_GAP = 10              # gap between elements
_MAX_TEXT_W = 300       # max text column width


class NeoAlertPopup(QDialog):
    """Non-modal neumorphic toast alert rendered as a frameless QDialog.

    Matches the pattern used by AdminLoginDialog / SettingsDialog /
    SimulatorDialog so it renders correctly on Windows.
    """

    # ── Custom animated opacity property (0.0-1.0) painted manually ──
    # windowOpacity works on QDialog, so we use that directly.

    def __init__(
        self,
        parent: QWidget | None,
        message: str,
        *,
        variant: str = "info",
        title: str | None = None,
        duration_ms: int = 3500,
    ) -> None:
        super().__init__(parent)
        # Frameless, non-modal, stays on top — same flags the other
        # scanner dialogs use, plus Tool to avoid a taskbar entry.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setModal(False)
        self.setStyleSheet(styles.GLOBAL_STYLE)

        v = _VARIANTS.get(variant, _VARIANTS["info"])
        self._accent = QColor(v["color"])
        self._icon_char = v["icon"]
        self._title_text = title or v["default_title"]
        self._message_text = message

        self._build_labels()
        self._size_to_content()
        self._position_on_screen()

        # Show and animate
        self.show()
        self._fade_in()

        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self._fade_out)

    # ── Label creation ────────────────────────────────────────────────

    def _build_labels(self) -> None:
        self._title_label = QLabel(self._title_text, self)
        self._title_label.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {styles.TEXT_PRIMARY}; "
            f"background: transparent; "
            f"font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
        )
        self._title_label.setWordWrap(True)

        self._msg_label = QLabel(self._message_text, self)
        self._msg_label.setStyleSheet(
            f"font-size: 12px; font-weight: 400; color: {styles.TEXT_SECONDARY}; "
            f"background: transparent; "
            f"font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
        )
        self._msg_label.setWordWrap(True)

    # ── Sizing ────────────────────────────────────────────────────────

    def _size_to_content(self) -> None:
        """Compute dialog size so text is never clipped."""
        self._title_label.setFixedWidth(_MAX_TEXT_W)
        self._msg_label.setFixedWidth(_MAX_TEXT_W)
        self._title_label.adjustSize()
        self._msg_label.adjustSize()

        title_h = self._title_label.sizeHint().height()
        msg_h = self._msg_label.sizeHint().height()

        # Card interior height
        content_h = title_h + 4 + msg_h
        card_h = max(content_h + 2 * _PAD_V, 52)

        # Card width
        card_w = _PAD_H + _BAR_W + _GAP + _ICON_D + _GAP + _MAX_TEXT_W + _PAD_H

        self._card_w = card_w
        self._card_h = card_h

        # Dialog includes shadow margin on all sides
        self.setFixedSize(card_w + 2 * _SHADOW, card_h + 2 * _SHADOW)

        # Place labels at absolute positions inside the dialog
        text_x = _SHADOW + _PAD_H + _BAR_W + _GAP + _ICON_D + _GAP
        text_y = _SHADOW + _PAD_V
        self._title_label.move(text_x, text_y)
        self._msg_label.move(text_x, text_y + title_h + 4)

    # ── Positioning ───────────────────────────────────────────────────

    def _position_on_screen(self) -> None:
        """Centre horizontally above the parent, or at screen top-centre."""
        p = self.parent()
        if p is not None and isinstance(p, QWidget):
            # Map parent centre-top to global
            pg = p.mapToGlobal(p.rect().topRight())
            x = pg.x() - self.width() - 8
            y = pg.y() + 24
        else:
            screen = QApplication.primaryScreen()
            if screen:
                sg = screen.availableGeometry()
                x = sg.x() + (sg.width() - self.width()) // 2
                y = sg.y() + 40
            else:
                x, y = 200, 40

        self.move(max(x, 0), max(y, 0))

    # ── Painting ──────────────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        card = QRectF(_SHADOW, _SHADOW, self._card_w, self._card_h)

        # Raised neumorphic background
        paint_neo_raised(p, card, radius=NEO_RADIUS_SM, distance=6, blur=14)

        # Left accent bar
        bar = QRectF(
            card.left() + _PAD_H,
            card.top() + _PAD_V,
            _BAR_W,
            card.height() - 2 * _PAD_V,
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._accent)
        p.drawRoundedRect(bar, 2.5, 2.5)

        # Icon — tinted circle background
        cx = bar.right() + _GAP
        cy = card.top() + _PAD_V
        circle = QRectF(cx, cy, _ICON_D, _ICON_D)
        bg = QColor(self._accent)
        bg.setAlpha(30)
        p.setBrush(bg)
        p.drawEllipse(circle)

        # Icon glyph
        p.setPen(self._accent)
        font = QFont("Segoe UI Symbol", 13)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(circle, Qt.AlignmentFlag.AlignCenter, self._icon_char)

        p.end()

    # ── Animations (windowOpacity works on QDialog) ───────────────────

    def _fade_in(self) -> None:
        self.setWindowOpacity(0.0)
        self._anim_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim_in.setDuration(250)
        self._anim_in.setStartValue(0.0)
        self._anim_in.setEndValue(1.0)
        self._anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_in.start()

    def _fade_out(self) -> None:
        self._anim_out = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim_out.setDuration(400)
        self._anim_out.setStartValue(self.windowOpacity())
        self._anim_out.setEndValue(0.0)
        self._anim_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim_out.finished.connect(self.close)
        self._anim_out.start()

    # ── Convenience class methods ─────────────────────────────────────

    @classmethod
    def success(cls, parent: QWidget | None, message: str, **kw) -> NeoAlertPopup:
        return cls(parent, message, variant="success", **kw)

    @classmethod
    def error(cls, parent: QWidget | None, message: str, **kw) -> NeoAlertPopup:
        return cls(parent, message, variant="error", **kw)

    @classmethod
    def warning(cls, parent: QWidget | None, message: str, **kw) -> NeoAlertPopup:
        return cls(parent, message, variant="warning", **kw)

    @classmethod
    def info(cls, parent: QWidget | None, message: str, **kw) -> NeoAlertPopup:
        return cls(parent, message, variant="info", **kw)
