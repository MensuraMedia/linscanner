"""Open with LinScanner: the command line takes files, and the menu entry advertises them"""

import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return f.read()


def test_command_line_accepts_files():
    from main import parse_args

    args = parse_args(["a.pdf", "b.png"])
    assert args.files == ["a.pdf", "b.png"]
    assert parse_args([]).files == []
    # options still work alongside files
    assert parse_args(["--page", "preview", "x.tif"]).files == ["x.tif"]


def test_desktop_entry_declares_files_and_types():
    entry = read("install.sh")
    exec_line = re.search(r"^Exec=(.+)$", entry, re.M).group(1)
    assert exec_line.endswith("%F"), "the menu entry must pass the selected files"
    mimes = re.search(r"^MimeType=(.+)$", entry, re.M).group(1).strip(";").split(";")
    assert "application/pdf" in mimes
    for t in ("image/png", "image/jpeg", "image/tiff"):
        assert t in mimes


@pytest.mark.parametrize("ext", [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"])
def test_openable_types_match_the_menu_entry(ext):
    from modules.manager_documents import OPENABLE

    assert ext in OPENABLE
