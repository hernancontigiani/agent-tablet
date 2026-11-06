from agent_tablet.themes import effective_theme as _effective_theme
from agent_tablet.themes import tui_css


def effective_theme(settings: dict, dark: bool) -> dict:
    """The palette, for settings that must resolve to one."""
    theme = _effective_theme(settings, dark)
    assert theme is not None, settings
    return theme


def test_default_theme_resolves_per_style_and_scheme():
    tui = {"terminal_theme": "Default", "ui_style": "tui"}
    assert effective_theme(tui, dark=True)["name"] == "Catppuccin Mocha"
    assert effective_theme(tui, dark=False)["name"] == "Catppuccin Latte"
    assert _effective_theme({"terminal_theme": "Default", "ui_style": "classic"}, True) is None
    assert effective_theme({"terminal_theme": "Nord", "ui_style": "classic"}, True)["name"] == "Nord"


def test_tui_css_uses_theme_colors_and_accent():
    css = tui_css(effective_theme({"terminal_theme": "Default"}, dark=True))
    assert "@define-color window_bg_color #1e1e2e;" in css
    assert "@define-color tsm_accent #cba6f7;" in css
    nord = tui_css(effective_theme({"terminal_theme": "Nord"}, dark=True))
    assert "@define-color tsm_accent #b48ead;" in nord  # magenta fallback


def test_catppuccin_default_matches_herdr_chrome_exactly():
    css = tui_css(effective_theme({"terminal_theme": "Default"}, dark=True))
    for token in (
        "tsm_mantle #181825",
        "tsm_surface0 #313244",
        "tsm_overlay0 #6c7086",
        "tsm_subtext0 #a6adc8",
        "tsm_accent #cba6f7",
    ):
        assert f"@define-color {token};" in css
