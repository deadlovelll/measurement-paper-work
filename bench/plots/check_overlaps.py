#!/usr/bin/env python
"""Layout gate: no figure ships with text on top of text."""

from __future__ import annotations

import contextlib
import itertools
import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from matplotlib.figure import Figure

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import style

MIN_AREA_PX = 6.0
MIN_FRACTION = 0.06
MIN_TITLE_GAP_PX = 8.0
MIN_INTRUSION_PX = 4.0

VIOLATIONS: list[dict] = []


def _boxes(fig: Figure) -> list[dict[str, Any]]:
    """Every text artist in the figure with its pixel box and the axes it belongs to."""
    out = []
    fig.canvas.draw()
    for ax in fig.axes:
        groups = [("annotation", ax.texts),
                  ("xtick", ax.get_xticklabels()), ("ytick", ax.get_yticklabels()),
                  ("xlabel", [ax.xaxis.label]), ("ylabel", [ax.yaxis.label]),
                  ("title", [ax.title])]
        leg = ax.get_legend()
        if leg is not None:
            groups.append(("legend", leg.get_texts()))
        for kind, artists in groups:
            for t in artists:
                if not t.get_text() or not t.get_visible():
                    continue
                try:
                    bb = t.get_window_extent()
                except Exception:
                    continue
                if bb.width <= 0 or bb.height <= 0:
                    continue
                out.append({"kind": kind, "text": t.get_text(), "bbox": bb, "ax": ax})
    for t in fig.texts:
        if t.get_text() and t.get_visible():
            with contextlib.suppress(Exception):
                out.append({"kind": "figtext", "text": t.get_text(),
                            "bbox": t.get_window_extent(), "ax": None})
    if fig.legends:
        for leg in fig.legends:
            out.extend({"kind": "figlegend", "text": t.get_text(),
                        "bbox": t.get_window_extent(), "ax": None}
                       for t in leg.get_texts() if t.get_text())
    return out


def _overlap_area(a, b) -> float:
    dx = min(a.x1, b.x1) - max(a.x0, b.x0)
    dy = min(a.y1, b.y1) - max(a.y0, b.y0)
    return dx * dy if dx > 0 and dy > 0 else 0.0


def audit(fig, name: str) -> None:
    items = _boxes(fig)
    found = []

    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if a["text"] == b["text"] and a["kind"] == b["kind"] and a["ax"] is not b["ax"]:
                continue
            area = _overlap_area(a["bbox"], b["bbox"])
            if area <= MIN_AREA_PX:
                continue
            smaller = min(a["bbox"].width * a["bbox"].height,
                          b["bbox"].width * b["bbox"].height)
            if smaller > 0 and area / smaller < MIN_FRACTION:
                continue
            found.append(f"text over text: {a['kind']} {a['text']!r} x "
                         f"{b['kind']} {b['text']!r} ({area:.0f} px^2)")


    axes_boxes = [(ax, ax.get_window_extent()) for ax in fig.axes]
    for it in items:
        if it["ax"] is None or it["kind"] not in ("annotation", "xtick", "ytick"):
            continue
        for ax, abox in axes_boxes:
            if ax is it["ax"]:
                continue
            depth = min(it["bbox"].x1, abox.x1) - max(it["bbox"].x0, abox.x0)
            vertical = min(it["bbox"].y1, abox.y1) - max(it["bbox"].y0, abox.y0)
            if depth > MIN_INTRUSION_PX and vertical > 0:
                found.append(f"{it['kind']} reaches {depth:.0f} px into another panel: "
                             f"{it['text']!r}")
                break

    titles = sorted((it for it in items if it["kind"] == "title" and it["text"]),
                    key=lambda it: it["bbox"].x0)
    for a, b in itertools.pairwise(titles):
        if abs(a["bbox"].y0 - b["bbox"].y0) > max(a["bbox"].height, b["bbox"].height):
            continue
        gap = b["bbox"].x0 - a["bbox"].x1
        if gap < MIN_TITLE_GAP_PX:
            found.append(f"titles nearly touch ({gap:.0f} px): "
                         f"{a['text']!r} | {b['text']!r}")

    for ax in fig.axes:
        leg = ax.get_legend()
        if leg is None:
            continue
        abox = ax.get_window_extent()
        boxes = [b for t in leg.get_texts() if t.get_text()
                 if (b := t.get_window_extent()) is not None
                 and _overlap_area(b, abox) > MIN_AREA_PX]
        if not boxes:
            continue
        for patch in ax.patches:
            with contextlib.suppress(Exception):
                pb = patch.get_window_extent()
                for tb in boxes:
                    if _overlap_area(tb, pb) > MIN_AREA_PX:
                        found.append("legend sits on a bar")
                        break
        for line in ax.lines:
            if line.get_linestyle() == "None" or not line.get_visible():
                continue
            with contextlib.suppress(Exception):
                pts = line.get_transform().transform(line.get_xydata())
                dense = []
                for (x0, y0), (x1, y1) in itertools.pairwise(pts):
                    dense.extend((x0 + (x1 - x0) * i / 24.0, y0 + (y1 - y0) * i / 24.0)
                                 for i in range(25))
                for tb in boxes:
                    if any(tb.x0 <= x <= tb.x1 and tb.y0 <= y <= tb.y1 for x, y in dense):
                        found.append(f"legend sits on the line {line.get_label()!r}")
                        break

    if found:
        VIOLATIONS.append({"figure": name, "problems": found})
        print(f"[FAIL] {name}")
        for f in dict.fromkeys(found):
            print(f"         {f}")
    else:
        print(f"[ok]   {name}")


def main() -> None:
    ru = "--ru" in sys.argv
    style.HOOKS.append(audit)
    if ru:
        import make_figures_ru as gen
    else:
        import make_figures as gen
    gen.main()
    print()
    if VIOLATIONS:
        total = sum(len(v["problems"]) for v in VIOLATIONS)
        print(f"=== layout gate FAILED: {len(VIOLATIONS)} figures, {total} problems")
        sys.exit(1)
    print("=== layout gate passed: no text collisions in any figure")


if __name__ == "__main__":
    main()
