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
    QScrollArea,
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
# EventLogWidget — scrollable event log inside a raised neumorphic card
#
# Structure:
#   EventLogWidget  (painted raised card)
#     └─ QVBoxLayout
#          ├─ header QLabel  ("Recent Activity")
#          └─ QScrollArea    (clips + scrolls)
#               └─ _scroll_content QWidget
#                    └─ QVBoxLayout  (rows live here)
# ───────────────────────────────────────────────────────────────────────

class _EventRow(QFrame):
    """Single event row with left accent bar.

    Uses QFrame + QSS border-left for the accent and a QLabel that
    word-wraps so long text never clips.  Minimum height 40 px but
    grows taller when text wraps.
    """

    def __init__(self, text: str, color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(40)

        # Accent color as a CSS border-left on the frame
        hex_color = color.name()
        self.setStyleSheet(
            f"_EventRow {{"
            f"  background-color: {styles.SURFACE_DARK};"
            f"  border-left: 4px solid {hex_color};"
            f"  border-radius: 6px;"
            f"}}"
        )

        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            f"font-size: 12px; font-weight: 400; color: {styles.TEXT_PRIMARY}; "
            f"background: transparent; "
            f"font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
            f"padding: 0px;"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 10, 8)
        lay.addWidget(self._label)


class EventLogWidget(QWidget):
    """Raised neumorphic card containing a scrollable list of event rows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Shadow margin — must match paintEvent
        _m = NEO_DISTANCE + 4

        outer = QVBoxLayout(self)
        outer.setContentsMargins(_m, _m, _m, _m)
        outer.setSpacing(0)

        # Header — inside the card, below the top shadow margin
        header = QLabel("  Recent Activity")
        header.setFixedHeight(28)
        header.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {styles.TEXT_PRIMARY}; "
            f"background: transparent; "
            f"font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
        )
        outer.addWidget(header)

        # Scroll area — fills the rest of the card
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
            f"QScrollBar:vertical {{"
            f"  background: transparent; width: 6px; margin: 2px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {styles.BORDER_LIGHT}; border-radius: 3px; min-height: 20px;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
            f"  height: 0px;"
            f"}}"
        )

        # Content widget inside scroll area
        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._rows_layout = QVBoxLayout(self._scroll_content)
        self._rows_layout.setContentsMargins(4, 4, 4, 4)
        self._rows_layout.setSpacing(6)
        self._rows_layout.addStretch()

        self._scroll.setWidget(self._scroll_content)
        outer.addWidget(self._scroll, stretch=1)

        self._rows: list[_EventRow] = []

    # -- Paint the raised neumorphic card behind everything ---------------

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        _m = NEO_DISTANCE + 2
        card = QRectF(_m, _m, self.width() - 2 * _m, self.height() - 2 * _m)
        paint_neo_raised(p, card, radius=NEO_RADIUS_LG, distance=NEO_DISTANCE, blur=12)
        p.end()

    # -- Public API -------------------------------------------------------

    def add_event(self, text: str, success: bool = True) -> None:
        color = QColor(styles.ACCENT_GREEN) if success else QColor(styles.ACCENT_RED)
        row = _EventRow(text, color)

        self._rows.append(row)
        # Insert before the stretch so rows stack top-down
        self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)

        # Auto-scroll to the newest entry
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))
