"""Shared desktop resources and font setup for all supported platforms."""
from pathlib import Path
import sys

from PySide6.QtGui import QFont, QFontDatabase


def resource_path(relative):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    return root / relative


def configure_application(app):
    app.setStyle('Fusion')
    font_id = QFontDatabase.addApplicationFont(str(resource_path('assets/fonts/NotoSansCJKsc-Regular.otf')))
    bundled = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    native = {'win32': ['Microsoft YaHei UI', 'Microsoft YaHei'],
              'darwin': ['PingFang SC', 'Heiti SC']}.get(sys.platform, [])
    font = QFont()
    font.setFamilies(native + bundled + ['sans-serif'])
    font.setPointSize(9)
    app.setFont(font)


def zoom_shortcut_label():
    # Qt maps ControlModifier to the Command key on macOS.
    return '⌘+滚轮' if sys.platform == 'darwin' else 'Ctrl+滚轮'
