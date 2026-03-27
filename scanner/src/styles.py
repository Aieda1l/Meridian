"""Neumorphic palette and minimal QSS constants.

Heavy lifting (shadows, depth) is handled by QPainter in shadows.py
and the custom widgets.  QSS here is only for typography, colors, and
basic element resets — never for shadows or borders that fake depth.
"""

# ── Palette ────────────────────────────────────────────────────────────
SURFACE        = "#E0E5EC"
SURFACE_DARK   = "#D1D9E6"   # slightly darker for contrast panels
ACCENT_BLUE    = "#5B8DEF"
ACCENT_GREEN   = "#4CAF82"
ACCENT_RED     = "#E06C6C"
ACCENT_AMBER   = "#E8A84C"
TEXT_PRIMARY    = "#2E3A47"
TEXT_SECONDARY  = "#8292A5"
WHITE          = "#FFFFFF"

# ── Global app stylesheet ─────────────────────────────────────────────
# Applied once on the QApplication / top-level widget.
GLOBAL_STYLE = f"""
* {{
    margin: 0;
    padding: 0;
}}
QWidget {{
    background-color: {SURFACE};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", "SF Pro Display", sans-serif;
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
FONT_SMALL    = f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent;"
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
