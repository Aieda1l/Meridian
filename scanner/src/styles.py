"""Neumorphic palette and QSS constants — exact Themesberg Neumorphism UI Kit Pro.

Tokens match shared/design-tokens.json and the Themesberg CSS root variables.
Heavy lifting (shadows, depth) is handled by QPainter in shadows.py.
QSS here is only for typography, colors, and basic element resets.
"""

# ── Palette (matching Themesberg :root CSS vars exactly) ──────────────
SURFACE        = "#e6e7ee"        # --primary / --soft / --neo-surface
SURFACE_DARK   = "#D1D9E6"        # --light / --neo-surface-dark
WHITE          = "#ECF0F3"        # --white / --neo-white
BLACK          = "#262833"        # --black / --neo-black
BORDER_LIGHT   = "#D1D9E6"        # --neo-border-light

# Accent colors
ACCENT_BLUE    = "#2D4CC8"        # --secondary
ACCENT_GREEN   = "#18634B"        # --success
ACCENT_RED     = "#A91E2C"        # --danger
ACCENT_AMBER   = "#F0B400"        # --warning
ACCENT_INFO    = "#0056B3"        # --info

# Text
TEXT_PRIMARY    = "#31344b"        # --dark / --neo-text
TEXT_SECONDARY  = "#44476A"        # --gray / --neo-text-secondary
TEXT_MUTED     = "#93a5be"         # --gray (muted) / --neo-text-muted

# Shadow colors (exact Themesberg hex)
SHADOW_DARK    = "#b8b9be"
SHADOW_LIGHT   = "#ffffff"


# ── Global app stylesheet ─────────────────────────────────────────────
# Themesberg body: font-family: "Nunito Sans", sans-serif;
#                  font-weight: 300; line-height: 1.5; color: #44476a;
#                  background-color: #e6e7ee;
GLOBAL_STYLE = f"""
* {{
    margin: 0;
    padding: 0;
}}
QWidget {{
    background-color: {SURFACE};
    color: {TEXT_SECONDARY};
    font-family: "Nunito Sans", "Segoe UI", sans-serif;
    font-size: 14px;
    font-weight: 300;
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

# ── Typography helpers (matching Themesberg CSS classes) ──────────────
# .display-2: font-size: 3.5rem; font-weight: 600
# .h5: font-size: 1.25rem
# .lead: font-size: 1.25rem; font-weight: 300
# body: font-size: 1rem; font-weight: 300
# .small: font-size: 80%
FONT_TITLE    = f"font-size: 20px; font-weight: 700; color: {TEXT_PRIMARY}; background: transparent;"
FONT_HEADING  = f"font-size: 32px; font-weight: 600; color: {TEXT_PRIMARY}; background: transparent;"
FONT_SUBHEAD  = f"font-size: 15px; font-weight: 300; color: {TEXT_SECONDARY}; background: transparent;"
FONT_LARGE    = f"font-size: 38px; font-weight: 700; background: transparent;"
FONT_BODY     = f"font-size: 14px; font-weight: 300; color: {TEXT_SECONDARY}; background: transparent;"
FONT_SMALL    = f"font-size: 12px; font-weight: 400; color: {TEXT_MUTED}; background: transparent;"
FONT_ICON     = f"font-size: 18px; color: {TEXT_SECONDARY}; background: transparent;"

# ── Input fields (inset-style via QSS; shadow painted in NeoInput) ────
# Themesberg .form-control: font-weight: 300; color: #44476a;
#   border: 0.0625rem solid #d1d9e6; border-radius: 0.55rem;
#   box-shadow: inset 2px 2px 5px #b8b9be, inset -3px -3px 7px #fff;
INPUT_STYLE = f"""
QLineEdit {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    font-family: "Nunito Sans", "Segoe UI", sans-serif;
    font-size: 14px;
    font-weight: 300;
    padding: 8px 14px;
    border: none;
    selection-background-color: {ACCENT_BLUE};
}}
QLineEdit:focus {{
    color: {TEXT_SECONDARY};
}}
QLineEdit::placeholder {{
    color: {TEXT_MUTED};
}}
"""
