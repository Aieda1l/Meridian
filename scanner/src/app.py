"""Application entry point for the Meridian scanner."""

import sys
from pathlib import Path

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

from .config import load_config
from .main_window import MainWindow


def _load_bundled_fonts() -> None:
    """Register bundled Nunito Sans TTF files so Qt always has the correct font.

    The Themesberg Neumorphism UI Kit uses Nunito Sans as its primary typeface.
    We bundle the font to ensure visual consistency regardless of system fonts.
    """
    fonts_dir = Path(__file__).parent / "fonts"
    if not fonts_dir.is_dir():
        return
    for ttf in fonts_dir.glob("*.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(ttf))
        if font_id < 0:
            print(f"Warning: failed to load font {ttf.name}")


def main() -> None:
    app = QApplication(sys.argv)
    _load_bundled_fonts()
    config = load_config()
    window = MainWindow(config)
    window.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
