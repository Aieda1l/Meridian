"""Custom neumorphic widgets for the scanner UI."""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import styles
from .shadows import apply_raised_shadow


# -------------------------------------------------------------------
# NeoCard
# -------------------------------------------------------------------

class NeoCard(QFrame):
    """Raised neumorphic card container."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(styles.CARD_RAISED)
        apply_raised_shadow(self)


# -------------------------------------------------------------------
# NeoButton
# -------------------------------------------------------------------

class NeoButton(QPushButton):
    """Neumorphic push button with press animation."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(styles.BUTTON_NEO)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._shadow = apply_raised_shadow(self)

    def mousePressEvent(self, event):
        # Quick inset
        self._shadow.setOffset(2, 2)
        self._shadow.setBlurRadius(6)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # Restore raised
        self._shadow.setOffset(6, 6)
        self._shadow.setBlurRadius(12)
        super().mouseReleaseEvent(event)


# -------------------------------------------------------------------
# StatusPill
# -------------------------------------------------------------------

class StatusPill(QLabel):
    """Small pill label that crossfades between active / inactive / error."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(24)
        self.setMinimumWidth(70)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self.set_inactive()

    def _animate_opacity(self) -> None:
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        anim.setDuration(300)
        anim.setStartValue(0.4)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def set_active(self, text: str | None = None) -> None:
        if text:
            self.setText(text)
        self.setStyleSheet(styles.STATUS_PILL_ACTIVE)
        self._animate_opacity()

    def set_inactive(self, text: str | None = None) -> None:
        if text:
            self.setText(text)
        self.setStyleSheet(styles.STATUS_PILL_INACTIVE)
        self._animate_opacity()

    def set_error(self, text: str | None = None) -> None:
        if text:
            self.setText(text)
        self.setStyleSheet(styles.STATUS_PILL_ERROR)
        self._animate_opacity()


# -------------------------------------------------------------------
# NeoInput
# -------------------------------------------------------------------

class NeoInput(QLineEdit):
    """Neumorphic text input."""

    def __init__(self, placeholder: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setStyleSheet(styles.INPUT_NEO)


# -------------------------------------------------------------------
# EventLogWidget
# -------------------------------------------------------------------

class _EventRow(QFrame):
    """Single row in the event log."""

    def __init__(self, text: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(
            f"QFrame {{ background: {styles.SURFACE}; border-radius: 8px; "
            f"border-left: 4px solid {color}; padding: 4px 8px; }}"
        )
        lbl = QLabel(text, self)
        lbl.setStyleSheet(f"color: {styles.TEXT_PRIMARY}; font-size: 13px;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.addWidget(lbl)


class EventLogWidget(QWidget):
    """Shows the last 3 scan events with slide-up entrance animations."""

    MAX_ROWS = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._layout.addStretch()
        self._rows: list[_EventRow] = []

    def add_event(self, text: str, success: bool = True) -> None:
        color = styles.ACCENT_GREEN if success else styles.ACCENT_RED
        row = _EventRow(text, color, self)

        # Remove oldest if at capacity
        if len(self._rows) >= self.MAX_ROWS:
            old = self._rows.pop(0)
            self._layout.removeWidget(old)
            old.deleteLater()

        self._rows.append(row)
        self._layout.addWidget(row)

        # Slide-up entrance animation
        start_geom = row.geometry()
        start_geom.moveTop(start_geom.top() + 30)
        anim = QPropertyAnimation(row, b"geometry", row)
        anim.setDuration(180)
        anim.setStartValue(start_geom)
        anim.setEndValue(row.geometry())
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
