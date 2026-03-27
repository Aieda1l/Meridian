"""Neumorphic shadow rendering via QPainter.

Qt only supports ONE QGraphicsEffect per widget, which makes the classic
dual-shadow neumorphism impossible via QGraphicsDropShadowEffect alone.

Instead, we paint the shadows ourselves in paintEvent overrides by drawing
rounded rectangles with blurred, offset fills — one light (top-left) and
one dark (bottom-right) — exactly like the CSS:

    box-shadow:  6px  6px 12px <dark_color>,
                -6px -6px 12px <light_color>;

The color math matches https://github.com/adamgiebl/neumorphism:
    dark  = colorLuminance(base, -intensity)
    light = colorLuminance(base, +intensity)
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen


# ---------------------------------------------------------------------------
# Color math (from neumorphism repo)
# ---------------------------------------------------------------------------

def color_luminance(hex_color: str, lum: float) -> QColor:
    """Shift each RGB channel by ``channel + channel * lum``.

    Positive *lum* brightens, negative darkens.  Matches the JS
    ``colorLuminance`` utility in the neumorphism project.
    """
    c = QColor(hex_color)
    r = max(0, min(255, int(c.red()   + c.red()   * lum)))
    g = max(0, min(255, int(c.green() + c.green() * lum)))
    b = max(0, min(255, int(c.blue()  + c.blue()  * lum)))
    return QColor(r, g, b)


# Default neumorphism parameters
NEO_BASE       = "#E0E5EC"
NEO_INTENSITY  = 0.18          # ±18 % brightness shift
NEO_DISTANCE   = 8             # px offset
NEO_BLUR       = 16            # px blur radius
NEO_RADIUS     = 20            # px corner radius

DARK_SHADOW  = color_luminance(NEO_BASE, -NEO_INTENSITY)  # ~#B8BEC7
LIGHT_SHADOW = color_luminance(NEO_BASE, +NEO_INTENSITY)   # ~#FFFFFF


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
    """Draw a raised neumorphic surface (two offset rounded rects + fill)."""
    dark  = color_luminance(base, -intensity)
    light = color_luminance(base, +intensity)

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    # Dark shadow (bottom-right)
    dark.setAlpha(110)
    painter.setBrush(dark)
    shadow_rect = rect.adjusted(distance, distance, distance, distance)
    painter.drawRoundedRect(shadow_rect, radius + 2, radius + 2)

    # Light shadow (top-left)
    light.setAlpha(180)
    painter.setBrush(light)
    shadow_rect = rect.adjusted(-distance, -distance, -distance, -distance)
    painter.drawRoundedRect(shadow_rect, radius + 2, radius + 2)

    # Base fill on top
    painter.setBrush(QColor(base))
    painter.drawRoundedRect(rect, radius, radius)


def paint_neo_inset(
    painter: QPainter,
    rect: QRectF,
    *,
    radius: float = NEO_RADIUS,
    distance: int = 4,
    base: str = NEO_BASE,
    intensity: float = NEO_INTENSITY,
) -> None:
    """Draw an inset / pressed neumorphic surface."""
    dark  = color_luminance(base, -intensity)
    light = color_luminance(base, +intensity)

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    # Base fill first
    fill_color = color_luminance(base, -0.03)
    painter.setBrush(fill_color)
    painter.drawRoundedRect(rect, radius, radius)

    # Inner dark shadow (top-left — light comes from top-left so inset darkens there)
    dark.setAlpha(80)
    painter.setBrush(dark)
    inner_dark = rect.adjusted(1, 1, -distance, -distance)
    painter.drawRoundedRect(inner_dark, radius - 1, radius - 1)

    # Inner light highlight (bottom-right)
    light.setAlpha(140)
    painter.setBrush(light)
    inner_light = rect.adjusted(distance, distance, -1, -1)
    painter.drawRoundedRect(inner_light, radius - 1, radius - 1)

    # Slightly darker center fill to clean up
    painter.setBrush(fill_color)
    center = rect.adjusted(distance - 1, distance - 1, -(distance - 1), -(distance - 1))
    painter.drawRoundedRect(center, radius - 2, radius - 2)


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
    shadow = QColor(0, 0, 0, 35)
    painter.setBrush(shadow)
    painter.drawRoundedRect(rect.adjusted(2, 2, 2, 2), radius, radius)

    # Fill
    painter.setBrush(fill_color)
    painter.drawRoundedRect(rect, radius, radius)
