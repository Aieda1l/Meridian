"""Neumorphic palette and minimal QSS constants.

Tokens match Themesberg Neumorphism UI Kit Pro and shared/design-tokens.json.
Heavy lifting (shadows, depth) is handled by QPainter in shadows.py.
QSS here is only for typography, colors, and basic element resets.
"""

# ── Palette (matching Themesberg / --neo-* CSS vars) ─────────────────
SURFACE        = "#e6e7ee"        # --neo-surface / --primary
SURFACE_DARK   = "#D1D9E6"        # --neo-surface-dark / --light
WHITE          = "#ECF0F3"        # --neo-white
BLACK          = "#262833"        # --neo-black
BORDER_LIGHT   = "#D1D9E6"        # --neo-border-light

# Accent colors
ACCENT_BLUE    = "#2D4CC8"        # --neo-secondary
ACCENT_GREEN   = "#18634B"        # --neo-success
ACCENT_RED     = "#A91E2C"        # --neo-danger
ACCENT_AMBER   = "#F0B400"        # --neo-warning
ACCENT_INFO    = "#0056B3"        # --neo-info

# Text
TEXT_PRIMARY    = "#31344b"        # --neo-text / --dark
TEXT_SECONDARY  = "#44476A"        # --neo-text-secondary / --gray
TEXT_MUTED     = "#93a5be"         # --neo-text-muted / --gray-muted

# Shadow colors (exact Themesberg hex)
SHADOW_DARK    = "#b8b9be"
SHADOW_LIGHT   = "#ffffff"


# ── Global app stylesheet ─────────────────────────────────────────────
GLOBAL_STYLE = f"""
* {{
    margin: 0;
    padding: 0;
}}
QWidget {{
    background-color: {SURFACE};
    color: {TEXT_PRIMARY};
    font-family: "Nunito Sans", "Segoe UI", "Inter", "SF Pro Display", sans-serif;
    font-size: 14px;
    border: none;
}}
QLabel {{
    background: transparent;
    border: none;
}}
QStackedWidget {{
    background: transparent;
    border: none;
}}
"""

# ── Typography helpers (applied via setStyleSheet on individual labels) ─
FONT_TITLE    = f"font-size: 20px; font-weight: 700; color: {TEXT_PRIMARY}; background: transparent;"
FONT_HEADING  = f"font-size: 32px; font-weight: 300; color: {TEXT_SECONDARY}; background: transparent;"
FONT_SUBHEAD  = f"font-size: 15px; color: {TEXT_SECONDARY}; background: transparent;"
FONT_LARGE    = f"font-size: 38px; font-weight: 700; background: transparent;"
FONT_BODY     = f"font-size: 14px; color: {TEXT_PRIMARY}; background: transparent;"
FONT_SMALL    = f"font-size: 12px; color: {TEXT_MUTED}; background: transparent;"
FONT_ICON     = f"font-size: 18px; color: {TEXT_SECONDARY}; background: transparent;"

# ── Input fields (inset-style via QSS; shadow painted in NeoInput) ────
INPUT_STYLE = f"""
QLineEdit {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    font-size: 14px;
    padding: 8px 14px;
    border: none;
    selection-background-color: {ACCENT_BLUE};
}}
QLineEdit:focus {{
    color: {TEXT_PRIMARY};
}}
"""
