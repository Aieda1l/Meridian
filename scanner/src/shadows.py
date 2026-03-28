"""Neumorphic shadow rendering via QPainter.

Exact replica of Themesberg Neumorphism UI Kit Pro shadow system:

    .shadow-soft  { box-shadow: 6px 6px 12px #b8b9be, -6px -6px 12px #fff; }
    .shadow-sm    { box-shadow: 3px 3px 6px #b8b9be, -3px -3px 6px #fff; }
    .shadow-inset { box-shadow: inset 2px 2px 5px #b8b9be, inset -3px -3px 7px #fff; }
    .border-light { border: 1px solid #D1D9E6; }

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

# Border radius tokens (from Themesberg CSS)
NEO_RADIUS_SM  = 8.8              # 0.55rem ≈ 8.8px — .card, .btn, .form-control
NEO_RADIUS_MD  = 12.0             # 0.75rem ≈ 12px
NEO_RADIUS_LG  = 16.0             # 1rem ≈ 16px  — .neo-card
NEO_RADIUS_XL  = 20.0             # 1.25rem ≈ 20px — .neo-modal
NEO_RADIUS     = NEO_RADIUS_SM    # default radius = .55rem (standard Themesberg)

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
                 border: 1px solid #D1D9E6;

    Uses 4-layer graduated rendering per shadow direction to approximate
    the CSS Gaussian blur spread.
    """
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    layers = 4  # number of graduated layers per shadow

    # --- Dark shadow (bottom-right) — #b8b9be ---
    for i in range(layers):
        frac = (i + 1) / layers
        dark = QColor(NEO_SHADOW_D)
        # Fade alpha from outer (low) to inner (higher)
        dark.setAlpha(int(25 + 65 * frac))
        painter.setBrush(dark)
        offset = distance * frac
        spread = (blur - distance) * (1 - frac * 0.7)
        shadow_rect = rect.adjusted(
            offset - spread * 0.3,
            offset - spread * 0.3,
            offset + spread * 0.3,
            offset + spread * 0.3,
        )
        painter.drawRoundedRect(shadow_rect, radius + 2, radius + 2)

    # --- Light shadow (top-left) — #ffffff ---
    for i in range(layers):
        frac = (i + 1) / layers
        light = QColor(NEO_SHADOW_L)
        light.setAlpha(int(40 + 120 * frac))
        painter.setBrush(light)
        offset = distance * frac
        spread = (blur - distance) * (1 - frac * 0.7)
        shadow_rect = rect.adjusted(
            -offset - spread * 0.3,
            -offset - spread * 0.3,
            -offset + spread * 0.3,
            -offset + spread * 0.3,
        )
        painter.drawRoundedRect(shadow_rect, radius + 2, radius + 2)

    # --- Base fill on top ---
    painter.setBrush(QColor(base))
    # 1px solid #D1D9E6 border (exact Themesberg .border-light)
    painter.setPen(QPen(QColor(NEO_BORDER), 1.0))
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
                 border: 1px solid #D1D9E6;
    """
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    # Base fill first (slightly darker than surface to look recessed)
    fill_color = color_luminance(base, -0.02)
    painter.setBrush(fill_color)
    painter.drawRoundedRect(rect, radius, radius)

    # Inner dark shadow (top-left) — inset 2px 2px 5px #b8b9be
    # Multi-layer for smoother blur approximation
    for i in range(3):
        frac = (i + 1) / 3
        dark = QColor(NEO_SHADOW_D)
        dark.setAlpha(int(30 + 50 * frac))
        painter.setBrush(dark)
        d_off = NEO_INSET_D_OFFSET * frac
        d_spr = NEO_INSET_D_BLUR * (1 - frac * 0.5)
        inner_dark = rect.adjusted(d_off, d_off, -d_spr * 0.5, -d_spr * 0.5)
        painter.drawRoundedRect(inner_dark, radius - 1, radius - 1)

    # Inner light highlight (bottom-right) — inset -3px -3px 7px #fff
    for i in range(3):
        frac = (i + 1) / 3
        light = QColor(NEO_SHADOW_L)
        light.setAlpha(int(40 + 90 * frac))
        painter.setBrush(light)
        l_off = NEO_INSET_L_OFFSET * frac
        l_spr = NEO_INSET_L_BLUR * (1 - frac * 0.5)
        inner_light = rect.adjusted(l_spr * 0.5, l_spr * 0.5, -l_off, -l_off)
        painter.drawRoundedRect(inner_light, radius - 1, radius - 1)

    # Center fill to clean up overlap
    painter.setBrush(fill_color)
    inset = max(NEO_INSET_D_OFFSET, NEO_INSET_L_OFFSET) + 1
    center = rect.adjusted(inset, inset, -inset, -inset)
    painter.drawRoundedRect(center, max(radius - 2, 2), max(radius - 2, 2))

    # 1px solid #D1D9E6 border (exact Themesberg)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(NEO_BORDER), 1.0))
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

    # Subtle dark shadow (3px 3px 6px — shadow-sm style)
    shadow = QColor(NEO_SHADOW_D)
    shadow.setAlpha(60)
    painter.setBrush(shadow)
    painter.drawRoundedRect(rect.adjusted(2, 2, 2, 2), radius, radius)

    # Light shadow
    light = QColor(NEO_SHADOW_L)
    light.setAlpha(80)
    painter.setBrush(light)
    painter.drawRoundedRect(rect.adjusted(-1, -1, -1, -1), radius, radius)

    # Fill
    painter.setBrush(fill_color)
    painter.drawRoundedRect(rect, radius, radius)
