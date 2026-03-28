"""Neumorphic shadow rendering via QPainter.

Exact replica of Themesberg Neumorphism UI Kit Pro shadow system:

    .shadow-soft  { box-shadow: 6px 6px 12px #b8b9be, -6px -6px 12px #fff; }
    .shadow-inset { box-shadow: inset 2px 2px 5px #b8b9be, inset -3px -3px 7px #fff; }

Qt only supports ONE QGraphicsEffect per widget, so we paint shadows
ourselves in paintEvent overrides using layered rounded rectangles.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen


# ---------------------------------------------------------------------------
# Design tokens — matching Themesberg Neumorphism UI + shared/design-tokens.json
# ---------------------------------------------------------------------------

NEO_BASE       = "#e6e7ee"        # --neo-primary / --neo-surface
NEO_BORDER     = "#D1D9E6"        # --neo-border-light
NEO_SHADOW_D   = "#b8b9be"        # dark shadow color (exact Themesberg)
NEO_SHADOW_L   = "#ffffff"        # light shadow color (exact Themesberg)

# Soft / raised: 6px 6px 12px #b8b9be, -6px -6px 12px #fff
NEO_DISTANCE   = 6                # px offset  (Themesberg uses 6)
NEO_BLUR       = 12               # px blur    (Themesberg uses 12)
NEO_RADIUS     = 16               # px corner  (~1rem = 0.55rem-1rem range)

# Small shadow: 3px 3px 6px
NEO_DISTANCE_SM = 3

# Inset: inset 2px 2px 5px #b8b9be, inset -3px -3px 7px #fff
NEO_INSET_D_OFFSET = 2
NEO_INSET_D_BLUR   = 5
NEO_INSET_L_OFFSET = 3
NEO_INSET_L_BLUR   = 7

# Legacy aliases (for existing widget code)
NEO_INTENSITY  = 0.18


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def color_luminance(hex_color: str, lum: float) -> QColor:
    """Shift each RGB channel by ``channel + channel * lum``.

    Positive *lum* brightens, negative darkens.
    """
    c = QColor(hex_color)
    r = max(0, min(255, int(c.red()   + c.red()   * lum)))
    g = max(0, min(255, int(c.green() + c.green() * lum)))
    b = max(0, min(255, int(c.blue()  + c.blue()  * lum)))
    return QColor(r, g, b)


# Pre-computed shadow colors (exact hex from Themesberg CSS)
DARK_SHADOW  = QColor(NEO_SHADOW_D)   # #b8b9be
LIGHT_SHADOW = QColor(NEO_SHADOW_L)   # #ffffff


# ---------------------------------------------------------------------------
# Paint helpers
# ---------------------------------------------------------------------------

def paint_neo_raised(
    painter: QPainter,
    rect: QRectF,
    *,
    radius: float = NEO_RADIUS,
    distance: int = NEO_DISTANCE,
    blur: int = NEO_BLUR,
    base: str = NEO_BASE,
    intensity: float = NEO_INTENSITY,
) -> None:
    """Draw a raised neumorphic surface.

    Replicates:  box-shadow: 6px 6px 12px #b8b9be, -6px -6px 12px #fff;
    """
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    # Dark shadow (bottom-right) — #b8b9be with alpha
    dark = QColor(NEO_SHADOW_D)
    dark.setAlpha(120)
    painter.setBrush(dark)
    shadow_rect = rect.adjusted(distance, distance, distance, distance)
    painter.drawRoundedRect(shadow_rect, radius + 2, radius + 2)

    # Light shadow (top-left) — #ffffff with alpha
    light = QColor(NEO_SHADOW_L)
    light.setAlpha(200)
    painter.setBrush(light)
    shadow_rect = rect.adjusted(-distance, -distance, -distance, -distance)
    painter.drawRoundedRect(shadow_rect, radius + 2, radius + 2)

    # Base fill on top
    painter.setBrush(QColor(base))
    # Subtle border matching --neo-border-light
    painter.setPen(QPen(QColor(NEO_BORDER), 0.5))
    painter.drawRoundedRect(rect, radius, radius)
    painter.setPen(Qt.PenStyle.NoPen)


def paint_neo_inset(
    painter: QPainter,
    rect: QRectF,
    *,
    radius: float = NEO_RADIUS,
    distance: int = 4,
    base: str = NEO_BASE,
    intensity: float = NEO_INTENSITY,
) -> None:
    """Draw an inset neumorphic surface.

    Replicates:  box-shadow: inset 2px 2px 5px #b8b9be, inset -3px -3px 7px #fff;
    """
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    # Base fill first (slightly darker than surface)
    fill_color = color_luminance(base, -0.02)
    painter.setBrush(fill_color)
    painter.drawRoundedRect(rect, radius, radius)

    # Inner dark shadow (top-left) — inset 2px 2px 5px #b8b9be
    dark = QColor(NEO_SHADOW_D)
    dark.setAlpha(90)
    painter.setBrush(dark)
    inner_dark = rect.adjusted(1, 1, -distance, -distance)
    painter.drawRoundedRect(inner_dark, radius - 1, radius - 1)

    # Inner light highlight (bottom-right) — inset -3px -3px 7px #fff
    light = QColor(NEO_SHADOW_L)
    light.setAlpha(160)
    painter.setBrush(light)
    inner_light = rect.adjusted(distance, distance, -1, -1)
    painter.drawRoundedRect(inner_light, radius - 1, radius - 1)

    # Center fill to clean up
    painter.setBrush(fill_color)
    center = rect.adjusted(distance - 1, distance - 1, -(distance - 1), -(distance - 1))
    painter.drawRoundedRect(center, radius - 2, radius - 2)

    # Subtle border
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(NEO_BORDER), 0.5))
    painter.drawRoundedRect(rect, radius, radius)
    painter.setPen(Qt.PenStyle.NoPen)


def paint_neo_pill(
    painter: QPainter,
    rect: QRectF,
    fill_color: QColor,
    *,
    radius: float = 0,
) -> None:
    """Draw a colored pill with a subtle outer shadow for depth."""
    if radius <= 0:
        radius = rect.height() / 2

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    # Subtle dark shadow
    shadow = QColor(NEO_SHADOW_D)
    shadow.setAlpha(60)
    painter.setBrush(shadow)
    painter.drawRoundedRect(rect.adjusted(2, 2, 2, 2), radius, radius)

    # Fill
    painter.setBrush(fill_color)
    painter.drawRoundedRect(rect, radius, radius)
