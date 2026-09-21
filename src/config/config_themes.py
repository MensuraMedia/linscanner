"""
Theme Definitions
Dark themes. The default "Black Yellow Gray" is sampled from the
universal-instruction-set reference ui-kit-black-yellow-gray.jpg; the other
seven come from gtk-python-dashboard-starter.
"""


class ThemeDefinition:
    """Single theme definition (colours used to generate the app CSS)"""

    def __init__(
        self,
        name,
        accent_color,
        sidebar_bg,
        window_bg,
        hover_color,
        card_bg=None,
        raised_bg=None,
        accent_text="#111111",
        text_primary="#eeeeee",
        text_secondary="#b3b3b3",
        text_muted="#82828e",
        success="#3fd059",
        error="#e8555d",
    ):
        self.name = name
        self.accent_color = accent_color
        self.sidebar_bg = sidebar_bg
        self.window_bg = window_bg
        self.hover_color = hover_color
        self.card_bg = card_bg or sidebar_bg
        self.raised_bg = raised_bg or hover_color
        self.accent_text = accent_text
        self.text_primary = text_primary
        self.text_secondary = text_secondary
        self.text_muted = text_muted
        self.success = success
        self.error = error


DEFAULT_THEME_ID = "black-yellow-gray"

DARK_THEMES = {
    "black-yellow-gray": ThemeDefinition(
        name="Black Yellow Gray",
        accent_color="#fbd700",  # sampled: gauge / bars / primary button
        sidebar_bg="#111111",  # sampled: screen background
        window_bg="#111111",
        hover_color="#212121",  # sampled: pills and chips
        card_bg="#181818",  # sampled: cards
        raised_bg="#212121",
        text_primary="#ffffff",
        text_secondary="#b3b3b3",
        text_muted="#82828e",  # sampled: neutral progress segment
        success="#3fd059",  # sampled: green progress segment
        error="#e8555d",  # sampled: red bar
    ),
    "default": ThemeDefinition(
        name="Default Blue",
        accent_color="#0078D7",
        sidebar_bg="#353535",
        window_bg="#2d2d2d",
        hover_color="#404040",
        accent_text="#ffffff",
    ),
    "adapta": ThemeDefinition(
        name="Adapta",
        accent_color="#00bcd4",
        sidebar_bg="#222d32",
        window_bg="#263238",
        hover_color="#2e3c43",
    ),
    "materia": ThemeDefinition(
        name="Materia",
        accent_color="#8ab4f8",
        sidebar_bg="#1e1e1e",
        window_bg="#212121",
        hover_color="#292929",
    ),
    "dracula": ThemeDefinition(
        name="Dracula",
        accent_color="#bd93f9",
        sidebar_bg="#282a36",
        window_bg="#1e1f29",
        hover_color="#383a4a",
    ),
    "nord": ThemeDefinition(
        name="Nord",
        accent_color="#88c0d0",
        sidebar_bg="#2e3440",
        window_bg="#3b4252",
        hover_color="#434c5e",
    ),
    "gruvbox": ThemeDefinition(
        name="Gruvbox",
        accent_color="#fe8019",
        sidebar_bg="#282828",
        window_bg="#1d2021",
        hover_color="#3c3836",
    ),
    "monokai": ThemeDefinition(
        name="Monokai",
        accent_color="#f92672",
        sidebar_bg="#272822",
        window_bg="#1e1f1c",
        hover_color="#3e3d32",
        accent_text="#ffffff",
    ),
}


def get_theme(theme_id):
    """Get theme by ID (falls back to the default theme)"""
    return DARK_THEMES.get(theme_id, DARK_THEMES[DEFAULT_THEME_ID])


def get_all_themes():
    """Get all available themes"""
    return DARK_THEMES
