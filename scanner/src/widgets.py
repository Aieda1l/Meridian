"""Custom neumorphic widgets — all depth rendered via QPainter, not QGraphicsEffect.

Widget              CSS reference
─────────────────   ───────────────────────────────────
NeoCard             .neo-card  { border-radius: 1rem; box-shadow: shadow-soft; }
NeoButton           .neo-btn   { border-radius: 0.55rem; box-shadow: shadow-sm; }
StatusPill          .neo-badge { border-radius: 9999px; }
NeoInput            .neo-input { border-radius: 0.55rem; box-shadow: shadow-inset; }
EventLogWidget      (custom — inset rows with accent bars)
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import styles
from .shadows import (
    NEO_BASE,
    NEO_DISTANCE,
    NEO_DISTANCE_SM,
    NEO_INTENSITY,
    NEO_RADIUS,
    NEO_RADIUS_SM,
    NEO_RADIUS_LG,
    NEO_RADIUS_XL,
    paint_neo_inset,
    paint_neo_pill,
    paint_neo_raised,
)


# ───────────────────────────────────────────────────────────────────────
# NeoCard — raised neumorphic container
# CSS: .neo-card { border-radius: var(--neo-radius-lg); /* 1rem = 16px */
#                  box-shadow: var(--neo-shadow-soft);
#                  border: 1px solid var(--neo-border-light);
#                  padding: 1.5rem; }
# ───────────────────────────────────────────────────────────────────────

class NeoCard(QWidget):
    """A raised neumorphic card drawn entirely via QPainter.

    The ``_shadow_spread`` property is animatable for the breathing effect.
    Default radius = NEO_RADIUS_LG (16px) matching .neo-card CSS.
    """

    def __init__(self, parent: QWidget | None = None, radius: float = NEO_RADIUS_LG) -> None:
        super().__init__(parent)
        self._radius = radius
        self._shadow_spread: float = float(NEO_DISTANCE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    # Animatable property — drives the breathing animation
    def _get_shadow_spread(self) -> float:
        return self._shadow_spread

    def _set_shadow_spread(self, v: float) -> None:
        self._shadow_spread = v
        self.update()

    shadow_spread = pyqtProperty(float, _get_shadow_spread, _set_shadow_spread)

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        margin = int(self._shadow_spread) + 4
        content = QRectF(margin, margin,
                         self.width() - 2 * margin,
                         self.height() - 2 * margin)
        paint_neo_raised(p, content, radius=self._radius,
                         distance=self._shadow_spread, blur=self._shadow_spread + 2.0)
        p.end()


# ───────────────────────────────────────────────────────────────────────
# NeoButton — raised button with press → inset animation
# CSS: .neo-btn { border-radius: 0.55rem; /* 8.8px */
#                 box-shadow: 3px 3px 6px (shadow-sm);
#                 font-weight: 600; font-size: 0.875rem; /* 14px */
#                 padding: 0.625rem 1.25rem;
#                 border: 1px solid var(--neo-border-light); }
#      .neo-btn:hover { box-shadow: shadow-soft; }
#      .neo-btn:active { box-shadow: shadow-inset; }
# ───────────────────────────────────────────────────────────────────────

class NeoButton(QWidget):
    """Neumorphic push-button.  Switches from raised to inset on press."""

    clicked = pyqtSignal()

    def __init__(self, text: str = "", icon_text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._icon_text = icon_text      # e.g. an emoji or single char
        self._pressed = False
        self._radius = NEO_RADIUS_SM     # 0.55rem ≈ 8.8px (exact Themesberg)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(42)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    # -- painting --

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        margin = NEO_DISTANCE + 2
        rect = QRectF(margin, margin,
                       self.width() - 2 * margin,
                       self.height() - 2 * margin)

        if self._pressed:
            # Active: inset 2px 2px 5px #b8b9be, inset -3px -3px 7px #fff
            paint_neo_inset(p, rect, radius=self._radius)
        else:
            # Default: 3px 3px 6px #b8b9be, -3px -3px 6px #fff (shadow-sm)
            paint_neo_raised(p, rect, radius=self._radius, distance=NEO_DISTANCE_SM, blur=6)

        # Text — Nunito Sans, weight 600, 14px (matching .neo-btn CSS)
        p.setPen(QColor(styles.TEXT_PRIMARY))
        font = QFont("Nunito Sans", 11)
        font.setWeight(QFont.Weight.DemiBold)  # weight 600
        p.setFont(font)

        if self._icon_text:
            icon_font = QFont("Segoe UI Emoji", 14)
            p.setFont(icon_font)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._icon_text)
        else:
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)

        p.end()

    # -- interaction --

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._pressed = True
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._pressed = False
        self.update()
        if self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def sizeHint(self) -> QSize:
        return QSize(120, 44)


# ───────────────────────────────────────────────────────────────────────
# StatusPill — painted colored pill with icon + label
# CSS: .neo-badge { border-radius: 9999px; font-size: 0.75rem;
#                   font-weight: 600; }
# ───────────────────────────────────────────────────────────────────────

_STATE_COLORS = {
    "active":   QColor(styles.ACCENT_GREEN),
    "inactive": QColor(styles.TEXT_SECONDARY),
    "error":    QColor(styles.ACCENT_RED),
    "warning":  QColor(styles.ACCENT_AMBER),
}

class StatusPill(QWidget):
    """Colored pill indicator drawn via QPainter — no QGraphicsEffect needed."""

    def __init__(self, label: str = "", icon: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._icon = icon
        self._state = "inactive"
        self._color = _STATE_COLORS["inactive"]
        self.setFixedHeight(30)
        self.setMinimumWidth(80)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        margin = 4
        rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)
        # 3D Neumorphism style instead of flat colored fill
        paint_neo_raised(p, rect, radius=rect.height() / 2, distance=3.0, blur=6.0)

        # Dot indicator using the state color
        dot_x = rect.left() + 14
        dot_y = rect.center().y()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(int(dot_x) - 3, int(dot_y) - 3, 6, 6)

        # Label text using the state color for clarity against the surface background
        p.setPen(self._color)
        font = QFont("Nunito Sans", 9)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        text_rect = rect.adjusted(24, 0, -8, 0)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)

        p.end()

    def set_active(self, text: str | None = None) -> None:
        if text:
            self._label = text
        self._state = "active"
        self._color = _STATE_COLORS["active"]
        self.update()

    def set_inactive(self, text: str | None = None) -> None:
        if text:
            self._label = text
        self._state = "inactive"
        self._color = _STATE_COLORS["inactive"]
        self.update()

    def set_error(self, text: str | None = None) -> None:
        if text:
            self._label = text
        self._state = "error"
        self._color = _STATE_COLORS["error"]
        self.update()


# ───────────────────────────────────────────────────────────────────────
# NeoInput — inset text field
# CSS: .neo-input { border-radius: 0.55rem; /* 8.8px */
#                   box-shadow: inset 2px 2px 5px #b8b9be,
#                               inset -3px -3px 7px #fff;
#                   border: 0.0625rem solid #D1D9E6;
#                   font-size: 0.875rem; font-weight: 400;
#                   padding: 0.625rem 1rem; }
# ───────────────────────────────────────────────────────────────────────

class NeoInput(QWidget):
    """Neumorphic inset text field wrapping a plain QLineEdit."""

    def __init__(self, placeholder: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius = NEO_RADIUS_SM     # 0.55rem ≈ 8.8px (exact Themesberg)
        self.setFixedHeight(44)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText(placeholder)
        self._edit.setStyleSheet(styles.INPUT_STYLE)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(NEO_DISTANCE + 4, 4, NEO_DISTANCE + 4, 4)
        lay.addWidget(self._edit)

    def text(self) -> str:
        return self._edit.text()

    def setText(self, t: str) -> None:
        self._edit.setText(t)

    def setEchoMode(self, mode) -> None:
        self._edit.setEchoMode(mode)

    def setPlaceholderText(self, t: str) -> None:
        self._edit.setPlaceholderText(t)

    @property
    def EchoMode(self):
        return QLineEdit.EchoMode

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        margin = NEO_DISTANCE
        rect = QRectF(margin, 2, self.width() - 2 * margin, self.height() - 4)
        # Deeply sunk in per Neumorphism UI Pro 
        paint_neo_inset(p, rect, radius=self._radius, distance=4.5, blur=9.0)
        p.end()


# ───────────────────────────────────────────────────────────────────────
# EventLogWidget — last N events with slide-up animation
# ───────────────────────────────────────────────────────────────────────

class _EventRow(QWidget):
    """Single event row painted with a subtle left-accent bar."""

    def __init__(self, text: str, color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._color = color
        self.setFixedHeight(52)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        margin = 4
        rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)

        # Subtle inset background
        paint_neo_inset(p, rect, radius=NEO_RADIUS_SM, distance=2,
                        intensity=0.08)

        # Left accent bar
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        bar_rect = QRectF(rect.left() + 3, rect.top() + 6, 4, rect.height() - 12)
        p.drawRoundedRect(bar_rect, 2, 2)

        # Text — Nunito Sans, 14px, weight 300 (body text)
        p.setPen(QColor(styles.TEXT_PRIMARY))
        font = QFont("Nunito Sans", 10)
        font.setWeight(QFont.Weight.Light)
        p.setFont(font)
        text_rect = rect.adjusted(16, 0, -8, 0)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._text)
        p.end()


class EventLogWidget(QWidget):
    """Shows the last 3 scan events with slide-up entrance animations."""

    MAX_ROWS = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)
        self._layout.addStretch()
        self._rows: list[_EventRow] = []

    def add_event(self, text: str, success: bool = True) -> None:
        color = QColor(styles.ACCENT_GREEN) if success else QColor(styles.ACCENT_RED)
        row = _EventRow(text, color, self)

        if len(self._rows) >= self.MAX_ROWS:
            old = self._rows.pop(0)
            self._layout.removeWidget(old)
            old.deleteLater()

        self._rows.append(row)
        self._layout.addWidget(row)

        # Slide-up entrance
        start_geom = row.geometry()
        start_geom.moveTop(start_geom.top() + 30)
        anim = QPropertyAnimation(row, b"geometry", row)
        anim.setDuration(200)
        anim.setStartValue(start_geom)
        anim.setEndValue(row.geometry())
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
