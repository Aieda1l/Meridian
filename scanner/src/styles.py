"""Neumorphic QSS stylesheet constants for the scanner UI."""

# Palette
SURFACE = "#E0E5EC"
LIGHT_SHADOW = "#FFFFFF"
DARK_SHADOW = "#A3B1C6"
ACCENT_BLUE = "#5B8DEF"
ACCENT_GREEN = "#6DB88E"
ACCENT_RED = "#E06C6C"
TEXT_PRIMARY = "#3A4A5C"
TEXT_SECONDARY = "#7B8CA3"

GLOBAL_STYLE = f"""
QWidget {{
    background-color: {SURFACE};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 14px;
}}
"""

CARD_RAISED = f"""
QFrame {{
    background-color: {SURFACE};
    border: 1px solid {LIGHT_SHADOW};
    border-radius: 16px;
    padding: 16px;
}}
"""

CARD_INSET = f"""
QFrame {{
    background-color: {SURFACE};
    border: 1px solid {DARK_SHADOW};
    border-radius: 12px;
    padding: 12px;
}}
"""

BUTTON_NEO = f"""
QPushButton {{
    background-color: {SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {LIGHT_SHADOW};
    border-radius: 12px;
    padding: 10px 24px;
    font-weight: 600;
    font-size: 14px;
    min-height: 36px;
}}
QPushButton:hover {{
    background-color: #D6DBE3;
}}
QPushButton:pressed {{
    border: 1px solid {DARK_SHADOW};
    background-color: #D0D5DC;
}}
"""

STATUS_PILL_ACTIVE = f"""
QLabel {{
    background-color: {ACCENT_GREEN};
    color: white;
    border-radius: 10px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
}}
"""

STATUS_PILL_INACTIVE = f"""
QLabel {{
    background-color: {DARK_SHADOW};
    color: white;
    border-radius: 10px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
}}
"""

STATUS_PILL_ERROR = f"""
QLabel {{
    background-color: {ACCENT_RED};
    color: white;
    border-radius: 10px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
}}
"""

INPUT_NEO = f"""
QLineEdit {{
    background-color: {SURFACE};
    border: 1px solid {DARK_SHADOW};
    border-radius: 10px;
    padding: 8px 14px;
    color: {TEXT_PRIMARY};
    font-size: 14px;
}}
QLineEdit:focus {{
    border: 2px solid {ACCENT_BLUE};
}}
"""

TOP_BAR_STYLE = f"""
QFrame {{
    background-color: {SURFACE};
    border-bottom: 1px solid {DARK_SHADOW};
    min-height: 60px;
    max-height: 60px;
    padding: 0 16px;
}}
"""

BOTTOM_TRAY_STYLE = f"""
QFrame {{
    background-color: {SURFACE};
    border-top: 1px solid {DARK_SHADOW};
    min-height: 220px;
    max-height: 220px;
}}
"""
