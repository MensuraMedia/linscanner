"""
Styled text runs for Quick Edit
A text item holds "runs": [{"text", "font", "size_pt", "color"}, ...], drawn
left to right on one baseline, so a few highlighted words can have their own
font, size or colour. Older items with a single text / font / size_pt / color
are read as one run.

All positions are character offsets into the item's plain text.
"""

import copy

STYLE_KEYS = ("font", "size_pt", "color")
DEFAULT_STYLE = {"font": "DejaVu Sans", "size_pt": 14.0, "color": "#000000"}


def runs_of(item):
    """The item's runs (converting an older single-style item)"""
    if item.get("runs"):
        return item["runs"]
    style = {k: item.get(k, DEFAULT_STYLE[k]) for k in STYLE_KEYS}
    return [dict(style, text=item.get("text", ""))]


def plain(runs):
    """The runs' text without styles"""
    return "".join(r["text"] for r in runs)


def style_of(run):
    """A run's style"""
    return {k: run[k] for k in STYLE_KEYS}


def style_at(runs, pos):
    """The style that text typed at pos continues (the character before pos; the first run at 0)"""
    offset = 0
    for r in runs:
        if pos <= offset + len(r["text"]) and (pos > offset or offset == 0):
            return style_of(r)
        offset += len(r["text"])
    return style_of(runs[-1]) if runs else dict(DEFAULT_STYLE)


def tidy(runs):
    """Merge neighbours with the same style and drop empty runs (one run is always kept)"""
    out = []
    for r in runs:
        if not r["text"] and (out or len(runs) > 1):
            continue
        if out and style_of(out[-1]) == style_of(r):
            out[-1] = dict(out[-1], text=out[-1]["text"] + r["text"])
        else:
            out.append(dict(r))
    return out or [dict(style_of(runs[0]) if runs else DEFAULT_STYLE, text="")]


def split_at(runs, pos):
    """Runs split so that a run boundary falls at pos"""
    out, offset = [], 0
    for r in runs:
        n = len(r["text"])
        if offset < pos < offset + n:
            k = pos - offset
            out += [dict(r, text=r["text"][:k]), dict(r, text=r["text"][k:])]
        else:
            out.append(dict(r))
        offset += n
    return out


def insert(runs, pos, text, style=None):
    """Runs with text inserted at pos (in style, or the style at pos)"""
    style = style or style_at(runs, pos)
    parts = split_at(runs, pos)
    out, offset, done = [], 0, False
    for r in parts:
        if not done and offset == pos:
            out.append(dict(style, text=text))
            done = True
        out.append(r)
        offset += len(r["text"])
    if not done:
        out.append(dict(style, text=text))
    return tidy(out)


def delete(runs, start, end):
    """Runs with the characters start..end removed"""
    if end <= start:
        return copy.deepcopy(runs)
    keep_style = style_at(runs, start + 1) if start < len(plain(runs)) else style_at(runs, start)
    parts = split_at(split_at(runs, start), end)
    out, offset = [], 0
    for r in parts:
        n = len(r["text"])
        if not (start <= offset and offset + n <= end):
            out.append(r)
        offset += n
    if not plain(out):
        return [dict(keep_style, text="")]  # keep the style for what's typed next
    return tidy(out)


def restyle(runs, start, end, **style):
    """Runs with characters start..end given the style (font / size_pt / color)"""
    parts = split_at(split_at(runs, start), end)
    out, offset = [], 0
    for r in parts:
        n = len(r["text"])
        if start <= offset and offset + n <= end and n:
            r = dict(r, **{k: v for k, v in style.items() if k in STYLE_KEYS})
        out.append(r)
        offset += n
    return tidy(out)


def word_at(text, pos):
    """(start, end) of the word around pos"""
    start = pos
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    end = pos
    while end < len(text) and not text[end].isspace():
        end += 1
    return start, end


def set_runs(item, runs):
    """Store runs on an item, keeping the older single-style fields in step (first run)"""
    runs = tidy(runs)
    item["runs"] = runs
    item["text"] = plain(runs)
    for k in STYLE_KEYS:
        item[k] = runs[0][k]
    return item
