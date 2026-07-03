#!/usr/bin/env python3
"""Render a day to PNG (mirrors GameComponent draw logic) for visual QA.

Usage: preview_day.py <dayIdx> [--empty]   (--empty = puzzle only, no solution)
Writes /tmp/tt_preview_<idx>.png
"""
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

DIRD = {"N": (0, -1), "S": (0, 1), "W": (-1, 0), "E": (1, 0)}


def load_days():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(here, "..", "app", "src", "lib", "game", "data", "days.js"))
    txt = open(path).read()
    body = txt.split("export const DAYS = ", 1)[1].split("\n};", 1)[0] + "\n}"
    body = re.sub(r"([{,])(\w+):", r'\1"\2":', body)
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    return json.loads(body)


def font(sz):
    for p in [
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/Library/Fonts/Arial.ttf",
    ]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def render(d, show_solution=True):
    R, C = d["rows"], d["cols"]
    cell = 56
    ox, oy = int(cell * 0.55), int(cell * 1.0)
    W = ox + C * cell + int(cell * 1.1)
    H = oy + R * cell + int(cell * 0.55)
    scale = 2
    img = Image.new("RGB", (W * scale, H * scale), "#ffffff")
    dr = ImageDraw.Draw(img)
    S = scale

    def rect(x0, y0, x1, y1, **kw):
        dr.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], **kw)

    def line(x0, y0, x1, y1, fill, width):
        dr.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=fill, width=int(width * S))

    accent = "#e5484d"
    given = "#64748b"
    ink = "#0f172a"
    border = "#cbd5e1"

    rect(ox, oy, ox + C * cell, oy + R * cell, fill="#ffffff")
    for c in range(C + 1):
        line(ox + c * cell, oy, ox + c * cell, oy + R * cell, border, 1)
    for r in range(R + 1):
        line(ox, oy + r * cell, ox + C * cell, oy + r * cell, border, 1)
    rect(ox, oy, ox + C * cell, oy + R * cell, outline=ink, width=2 * S)

    f = font(int(cell * 0.42 * S))
    for c in range(C):
        t = str(d["colClues"][c])
        w = dr.textlength(t, font=f)
        dr.text(((ox + c * cell + cell / 2) * S - w / 2, (oy - cell * 0.72) * S), t, fill=ink, font=f)
    for r in range(R):
        t = str(d["rowClues"][r])
        dr.text(((ox + C * cell + cell * 0.28) * S, (oy + r * cell + cell * 0.28) * S), t, fill=ink, font=f)

    exits = {}
    for (r, c, s) in d["exits"]:
        exits.setdefault((r, c), set()).add(s)

    if show_solution:
        locked = {}
        for (r, c, s) in d["givens"]:
            locked[(r, c)] = s
        rw = max(3, cell * 0.16)
        for (r, c, dirs) in d["solution"]:
            cx = ox + c * cell + cell / 2
            cy = oy + r * cell + cell / 2
            for ch in dirs:
                dxu, dyu = DIRD[ch]
                is_stub = (r, c) in exits and ch in exits[(r, c)]
                col = given if (r, c) in locked and ch in locked[(r, c)] else accent
                if is_stub:
                    col = given
                ex = cx + dxu * (cell / 2 + (cell * 0.38 if is_stub else 0))
                ey = cy + dyu * (cell / 2 + (cell * 0.38 if is_stub else 0))
                if dxu == 0:
                    ex = cx
                if dyu == 0:
                    ey = cy
                # fix: recompute end at the correct edge
                ex = cx + (dxu * (cell / 2 + (cell * 0.38 if is_stub else 0)))
                ey = cy + (dyu * (cell / 2 + (cell * 0.38 if is_stub else 0)))
                line(cx, cy, ex, ey, col, rw)
            dr.ellipse(
                [(cx - rw * 0.42) * S, (cy - rw * 0.42) * S, (cx + rw * 0.42) * S, (cy + rw * 0.42) * S],
                fill=accent,
            )
    else:
        # puzzle only: draw given pieces + exit stubs
        rw = max(3, cell * 0.16)
        pieces = {}
        for (r, c, s) in d["givens"]:
            pieces[(r, c)] = s
        for (r, c), dirs in pieces.items():
            cx = ox + c * cell + cell / 2
            cy = oy + r * cell + cell / 2
            for ch in dirs:
                dxu, dyu = DIRD[ch]
                is_stub = (r, c) in exits and ch in exits[(r, c)]
                ex = cx + dxu * (cell / 2 + (cell * 0.38 if is_stub else 0))
                ey = cy + dyu * (cell / 2 + (cell * 0.38 if is_stub else 0))
                line(cx, cy, ex, ey, given, rw)

    img = img.resize((W, H), Image.LANCZOS)
    return img


def main():
    idx = sys.argv[1] if len(sys.argv) > 1 else "0"
    show = "--empty" not in sys.argv
    days = load_days()
    img = render(days[idx], show_solution=show)
    out = f"/tmp/tt_preview_{idx}{'' if show else '_empty'}.png"
    img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
