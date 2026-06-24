import sys
from dataclasses import dataclass

from PySide6.QtGui import QColor

if sys.platform == "win32":
    import winreg
else:
    winreg = None


ACCENT = "#0A84FF"


@dataclass(frozen=True)
class AppTheme:
    dark: bool
    text: str
    text_soft: str
    text_muted: str
    panel_bg: str
    panel_border: str
    card_bg: str
    card_border: str
    main_background: str
    groove: str
    handle: str
    disabled_bg: str
    disabled_text: str


DARK_THEME = AppTheme(
    dark=True,
    text="#F5F7FB",
    text_soft="#D7E3F7",
    text_muted="#8F9BB3",
    panel_bg="rgba(255, 255, 255, 15)",
    panel_border="rgba(255, 255, 255, 30)",
    card_bg="rgba(255, 255, 255, 16)",
    card_border="rgba(255, 255, 255, 24)",
    main_background=(
        "qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, "
        "stop: 0 #101217, stop: 0.45 #161820, stop: 1 #0D1118)"
    ),
    groove="rgba(255, 255, 255, 34)",
    handle="#F3F7FF",
    disabled_bg="rgba(255, 255, 255, 13)",
    disabled_text="rgba(255, 255, 255, 82)",
)

LIGHT_THEME = AppTheme(
    dark=False,
    text="#111827",
    text_soft="#263244",
    text_muted="#667085",
    panel_bg="rgba(255, 255, 255, 220)",
    panel_border="rgba(17, 24, 39, 20)",
    card_bg="rgba(255, 255, 255, 235)",
    card_border="rgba(17, 24, 39, 24)",
    main_background=(
        "qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, "
        "stop: 0 #F3F7FB, stop: 0.48 #EAF1F8, stop: 1 #F8FAFC)"
    ),
    groove="rgba(17, 24, 39, 28)",
    handle="#FFFFFF",
    disabled_bg="rgba(17, 24, 39, 8)",
    disabled_text="rgba(17, 24, 39, 90)",
)


def windows_prefers_dark() -> bool:
    if sys.platform != "win32":
        return QColor(0, 0, 0).lightness() < 128

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            apps_use_light_theme, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(apps_use_light_theme) == 0
    except OSError:
        return True


def current_app_theme() -> AppTheme:
    return DARK_THEME if windows_prefers_dark() else LIGHT_THEME


def slider_style(theme: AppTheme, handle_size: int = 18) -> str:
    margin = -(handle_size // 2 - 2)
    radius = handle_size // 2
    return f"""
        QSlider {{
            min-height: 30px;
            background: transparent;
        }}
        QSlider::groove:horizontal {{
            height: 4px;
            border-radius: 2px;
            background: {theme.groove};
        }}
        QSlider::sub-page:horizontal {{
            height: 4px;
            border-radius: 2px;
            background: {ACCENT};
        }}
        QSlider::add-page:horizontal {{
            height: 4px;
            border-radius: 2px;
            background: {theme.groove};
        }}
        QSlider::handle:horizontal {{
            width: {handle_size}px;
            height: {handle_size}px;
            margin: {margin}px 0;
            border-radius: {radius}px;
            background: {theme.handle};
            border: 2px solid {ACCENT};
        }}
        QSlider::handle:horizontal:hover {{
            background: #FFFFFF;
            border: 2px solid #4AA3FF;
        }}
        QSlider::handle:horizontal:disabled {{
            background: {theme.disabled_text};
            border: 2px solid {theme.panel_border};
        }}
    """
