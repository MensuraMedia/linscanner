"""
Theme Applicator
Generates the application CSS from a ThemeDefinition and applies it to the
screen. Style follows the black-yellow-gray reference: near-black base,
rounded dark cards, one saturated accent, pill-shaped primary buttons.
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402


class ThemeApplicator:
    """Applies theme colours to the application"""

    def __init__(self):
        self.css_provider = Gtk.CssProvider()
        self.current_theme = None
        self._registered = False

    def apply_theme(self, theme):
        self.current_theme = theme
        try:
            self.css_provider.load_from_data(self.generate_css(theme).encode())
        except Exception as e:  # malformed CSS must not stop the app
            print(f"Error applying theme {theme.name}: {e}")
            return False
        if not self._registered:
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            self._registered = True
        return True

    @staticmethod
    def generate_css(t):
        return f"""
* {{ font-family: Ubuntu, Cantarell, sans-serif; }}
window, .content-area {{ background-color: {t.window_bg}; color: {t.text_primary}; }}
label {{ color: {t.text_primary}; }}
headerbar {{ background: {t.sidebar_bg}; border-bottom: 1px solid #000; color: {t.text_primary}; }}

/* Sidebar */
.sidebar {{ background-color: {t.sidebar_bg}; border-right: 1px solid {t.raised_bg}; }}
.logo-area {{ background-color: {t.sidebar_bg}; padding: 10px; }}
.logo-text {{ color: {t.accent_color}; font-size: 15pt; font-weight: bold; }}
.nav-button {{
    background: transparent; border: none; border-radius: 10px; box-shadow: none;
    margin: 2px 8px; padding: 6px 12px; min-height: 28px; color: {t.text_muted};
}}
.nav-button label {{ color: {t.text_muted}; }}
.nav-button:hover {{ background-color: {t.raised_bg}; }}
.nav-button:hover label {{ color: {t.text_primary}; }}
.nav-button.active {{ background-color: {t.raised_bg}; }}
.nav-button.active label {{ color: {t.accent_color}; font-weight: bold; }}

/* Pages and cards */
.page-title {{ font-size: 20pt; font-weight: bold; color: {t.text_primary}; }}
.page-subtitle {{ font-size: 12pt; font-weight: bold; color: {t.text_primary}; }}
.muted {{ color: {t.text_muted}; }}
.secondary {{ color: {t.text_secondary}; }}
.card {{ background-color: {t.card_bg}; border-radius: 16px; padding: 18px; }}
.card-title {{ font-size: 12pt; font-weight: bold; color: {t.text_primary}; }}
.status-ok {{ color: {t.success}; }}
.status-error {{ color: {t.error}; }}
.status-busy {{ color: {t.accent_color}; }}

/* Inputs */
combobox button, combobox box, entry, filechooserbutton button {{
    background: {t.raised_bg}; color: {t.text_primary}; border: none; border-radius: 10px;
    box-shadow: none; min-height: 30px;
}}
combobox window menu, menu {{ background: {t.raised_bg}; color: {t.text_primary}; }}
menuitem:hover {{ background: {t.hover_color}; }}
checkbutton check {{ background: {t.raised_bg}; border: 1px solid {t.text_muted}; }}
checkbutton check:checked {{ background: {t.accent_color}; }}

/* Buttons */
button {{
    background: {t.raised_bg}; color: {t.text_primary}; border: none; border-radius: 10px;
    box-shadow: none; padding: 6px 14px;
}}
button label {{ color: {t.text_primary}; }}
button:hover {{ background: {t.hover_color}; }}
button:disabled label {{ color: {t.text_muted}; }}
.primary-pill {{
    background: {t.accent_color}; border-radius: 999px; padding: 10px 34px;
}}
.primary-pill label {{ color: {t.accent_text}; font-weight: bold; font-size: 12pt; }}
.primary-pill:hover {{ background: shade({t.accent_color}, 1.08); }}
.primary-pill:disabled {{ background: {t.raised_bg}; }}

/* Segmented toggles (Color / B&W, High / Medium / Low) */
.segment {{ background: {t.raised_bg}; border-radius: 999px; padding: 3px; }}
.segment button {{ background: transparent; border-radius: 999px; padding: 6px 16px; }}
.segment button label {{ color: {t.text_secondary}; }}
.segment button:checked {{ background: {t.accent_color}; }}
.segment button:checked label {{ color: {t.accent_text}; font-weight: bold; }}

/* Progress */
progressbar trough {{ background: {t.raised_bg}; border-radius: 999px; min-height: 8px; }}
progressbar progress {{ background: {t.accent_color}; border-radius: 999px; min-height: 8px; }}

/* Preview */
.preview-frame {{ background-color: #000000; border-radius: 12px; }}
.thumb {{ background: {t.raised_bg}; border-radius: 10px; padding: 4px; border: 2px solid transparent; }}
.thumb.selected {{ border: 2px solid {t.accent_color}; }}
.thumb-label {{ color: {t.text_muted}; font-size: 9pt; }}
.theme-swatch {{ border-radius: 999px; }}
scrollbar slider {{ background: {t.raised_bg}; }}
"""
