"""
Alignment guides for Quick Edit
While an item is placed or dragged, its edges are compared with the items
already on the page. When one is within a few pixels of a useful line, the
item snaps to it and a guide is drawn. This is a soft snap: move a little
further and it lets go, and holding Alt switches snapping off.

Lines considered (all in page fractions, 0..1):
- align:   the left / centre / right edges and top / bottom of other items
- center:  the page's vertical centre line (item centred on the page)
- mirror:  the mirror image of another item across the page centre (symmetry)
- spacing: equal vertical spacing: the next row after two rows, or the gap
           a text line would leave below another text item
"""

from dataclasses import dataclass


@dataclass
class Box:
    """An item's rectangle in page fractions"""

    left: float
    top: float
    width: float
    height: float
    kind: str = "text"  # "text" | "image"

    @property
    def right(self):
        """Right edge"""
        return self.left + self.width

    @property
    def bottom(self):
        """Bottom edge"""
        return self.top + self.height

    @property
    def center(self):
        """Horizontal centre"""
        return self.left + self.width / 2


@dataclass
class Guide:
    """A guide line to draw: axis "v" (x = value) or "h" (y = value)"""

    axis: str
    value: float
    kind: str  # align | center | mirror | spacing


def x_candidates(box, others):
    """[(offset, guide lines)] that would line box up horizontally"""
    out = []
    edges = {"left": box.left, "center": box.center, "right": box.right}
    for o in others:
        for target in (o.left, o.center, o.right):
            for edge in edges.values():
                out.append((target - edge, [Guide("v", target, "align")]))
        # symmetry: mirror of o across the page centre
        out.append(((1 - o.right) - box.left, [Guide("v", 1 - o.right, "mirror"), Guide("v", 0.5, "center")]))
        out.append(((1 - o.left) - box.right, [Guide("v", 1 - o.left, "mirror"), Guide("v", 0.5, "center")]))
    out.append((0.5 - box.center, [Guide("v", 0.5, "center")]))
    return out


def y_candidates(box, others):
    """[(offset, guide lines)] that would line box up vertically or space it evenly"""
    out = []
    for o in others:
        for target in (o.top, o.bottom):
            out.append((target - box.top, [Guide("h", target, "align")]))
            out.append((target - box.bottom, [Guide("h", target, "align")]))
        if o.kind == "text":  # the next line of text: a half-line gap below
            nxt = o.top + o.height * 1.5
            out.append((nxt - box.top, [Guide("h", o.top, "spacing"), Guide("h", nxt, "spacing")]))
    tops = sorted({round(o.top, 5) for o in others})
    for t1, t2 in zip(tops, tops[1:]):
        gap = t2 - t1
        for target, rows in ((t2 + gap, (t1, t2)), (t1 - gap, (t1, t2))):
            lines = [Guide("h", v, "spacing") for v in (*rows, target)]
            out.append((target - box.top, lines))
    return out


def _best(candidates, threshold):
    """The smallest offset within threshold, with its guides (0, [] if none)"""
    best = None
    for offset, guides in candidates:
        if abs(offset) <= threshold and (best is None or abs(offset) < abs(best[0])):
            best = (offset, guides)
    return best or (0.0, [])


def snap(box, others, threshold_x, threshold_y):
    """(new_left, new_top, guides) for box, snapped to the nearest guide on each axis.

    threshold_x / threshold_y: how close (page fractions) a line must be to snap;
    the caller converts a few screen pixels to fractions."""
    dx, gx = _best(x_candidates(box, others), threshold_x)
    dy, gy = _best(y_candidates(box, others), threshold_y)
    return box.left + dx, box.top + dy, gx + gy
