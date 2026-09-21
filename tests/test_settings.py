"""Settings persistence"""

import json

from modules.manager_settings import DEFAULTS, SettingsManager


def test_defaults_and_roundtrip(tmp_path):
    path = tmp_path / "s.json"
    s = SettingsManager(str(path))
    assert s.get("theme") == DEFAULTS["theme"] == "default"  # framework Default Blue
    s.set("quality", "high")
    assert SettingsManager(str(path)).get("quality") == "high"


def test_bad_values_ignored(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"quality": 5, "unknown": 1, "paper": "a4"}))
    s = SettingsManager(str(path))
    assert s.get("quality") == DEFAULTS["quality"]  # wrong type rejected
    assert s.get("paper") == "a4"
    assert "unknown" not in s.values


def test_override_not_saved(tmp_path):
    path = tmp_path / "s.json"
    s = SettingsManager(str(path))
    s.override("show_all_backends", True)
    s.set("paper", "legal")
    assert s.get("show_all_backends") is True
    assert json.loads(path.read_text())["show_all_backends"] is False


def test_corrupt_file_falls_back(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{not json")
    assert SettingsManager(str(path)).get("paper") == DEFAULTS["paper"]


def test_themes_are_the_framework_seven_and_removed_ids_fall_back():
    from config.config_themes import DEFAULT_THEME_ID, get_all_themes, get_theme

    assert set(get_all_themes()) == {"default", "adapta", "materia", "dracula", "nord", "gruvbox", "monokai"}
    assert DEFAULT_THEME_ID == "default" and get_theme("default").accent_color == "#0078D7"
    assert get_theme("black-yellow-gray") is get_theme("default")  # removed theme -> default
