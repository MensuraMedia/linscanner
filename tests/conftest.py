"""Test setup: make src/ importable and expose fixture paths"""

import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

requires_sane = pytest.mark.skipif(shutil.which("scanimage") is None, reason="sane-utils not installed")
requires_display = pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"), reason="no display"
)


def fixture_text(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return f.read()


@pytest.fixture(autouse=True)
def private_user_data(tmp_path, monkeypatch):
    """Keep tests away from the real ~/.local/share/linscanner (signatures, fonts, recent list)"""
    if "XDG_DATA_HOME" not in os.environ or not os.environ["XDG_DATA_HOME"].startswith(str(tmp_path)):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user-data"))
