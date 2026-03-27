"""Neumorphic shadow effect helpers for Qt widgets."""

from PyQt6.QtWidgets import QWidget, QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor


def apply_raised_shadow(widget: QWidget) -> QGraphicsDropShadowEffect:
    """Apply a dark drop-shadow for a raised neumorphic look.

    Qt only supports one QGraphicsEffect per widget, so we apply the
    dark (bottom-right) shadow and rely on the CSS border-color for
    the light (top-left) highlight.
    """
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(12)
    effect.setOffset(6, 6)
    effect.setColor(QColor(163, 177, 198, 178))
    widget.setGraphicsEffect(effect)
    return effect


def apply_inset_shadow(widget: QWidget) -> QGraphicsDropShadowEffect:
    """Apply a smaller, tighter shadow suggesting an inset surface."""
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(8)
    effect.setOffset(3, 3)
    effect.setColor(QColor(163, 177, 198, 178))
    widget.setGraphicsEffect(effect)
    return effect
