"""Rescale a Miami scene's SVG (After Hours, Magenta Hour) into a smaller integer grid, for its card.

Handles exactly the vocabulary those make-scene.py files write: paths with M/m/L/l/H/h/V/v/Q/q/Z commands,
rect/circle geometry, stroke widths and dash arrays, userSpaceOnUse gradients (and their
y-squash gradientTransform), and the reflection's matrix transform.
"""
from __future__ import annotations

import re

NUM = r"-?\d*\.?\d+(?:e-?\d+)?"


def _tokens(d):
    return re.findall(rf"[MmLlHhVvQqZz]|{NUM}", d)


def rdp(points, eps):
    """Douglas-Peucker: drop points within eps of the line through their neighbours."""
    if len(points) < 3:
        return points
    (x0, y0), (x1, y1) = points[0], points[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = (dx * dx + dy * dy) ** 0.5 or 1e-9
    worst, at = -1.0, 0
    for i, (x, y) in enumerate(points[1:-1], 1):
        dist = abs(dy * (x - x0) - dx * (y - y0)) / norm if (dx or dy) else ((x - x0) ** 2 + (y - y0) ** 2) ** 0.5
        if dist > worst:
            worst, at = dist, i
    if worst <= eps:
        return [points[0], points[-1]]
    return rdp(points[: at + 1], eps)[:-1] + rdp(points[at:], eps)


def simplify(out, eps):
    """Run rdp over each run of straight segments (the M or L point before a run included)."""
    res, run = [], []
    def flush():
        if run:
            pts = rdp([p for _, p in run], eps)
            res.extend(("L", [p]) for p in pts[1:])
            run.clear()
    prev = None
    for c, pts in out:
        if c == "L":
            if not run and prev is not None:
                run.append(("anchor", prev))
            run.append(("L", pts[0]))
            prev = pts[0]
            continue
        flush()
        res.append((c, pts))
        prev = pts[-1] if pts else prev
    flush()
    return res


def rescale_path(d, k, ox, oy, step=1.0, eps=0.0):
    """Absolute points through (x - ox) * k, (y - oy) * k, rounded to `step`, re-emitted relative."""
    toks = _tokens(d)
    i, cmd = 0, None
    x = y = sx = sy = 0.0
    out = []  # (cmd, [abs points]) in scaled space
    while i < len(toks):
        t = toks[i]
        if re.fullmatch(r"[A-Za-z]", t):
            cmd = t
            i += 1
            if cmd in "Zz":
                out.append(("z", []))
                x, y = sx, sy
                continue
        if cmd in "Mm":
            nx, ny = float(toks[i]), float(toks[i + 1]); i += 2
            if cmd == "m":
                nx, ny = x + nx, y + ny
            x, y, sx, sy = nx, ny, nx, ny
            out.append(("M", [(x, y)]))
            cmd = "l" if cmd == "m" else "L"
        elif cmd in "Ll":
            nx, ny = float(toks[i]), float(toks[i + 1]); i += 2
            if cmd == "l":
                nx, ny = x + nx, y + ny
            x, y = nx, ny
            out.append(("L", [(x, y)]))
        elif cmd in "Hh":
            v = float(toks[i]); i += 1
            x = x + v if cmd == "h" else v
            out.append(("L", [(x, y)]))
        elif cmd in "Vv":
            v = float(toks[i]); i += 1
            y = y + v if cmd == "v" else v
            out.append(("L", [(x, y)]))
        elif cmd in "Qq":
            vals = [float(v) for v in toks[i:i + 4]]; i += 4
            if cmd == "q":
                c = (x + vals[0], y + vals[1]); e = (x + vals[2], y + vals[3])
            else:
                c, e = (vals[0], vals[1]), (vals[2], vals[3])
            x, y = e
            out.append(("Q", [c, e]))
        else:
            raise ValueError(f"unhandled path command {cmd!r}")
    def S(p):
        return (round((p[0] - ox) * k / step) * step, round((p[1] - oy) * k / step) * step)
    if eps:
        out = [(c, [((x - ox) * k, (y - oy) * k) for x, y in pts]) for c, pts in out]
        out = simplify(out, eps)
        out = [(c, [(x / k + ox, y / k + oy) for x, y in pts]) for c, pts in out]
    def f(v):
        v = round(v, 3)
        return str(int(v)) if v == int(v) else f"{v:g}"
    res, cur, start, last = [], None, None, None
    for c, pts in out:
        if c == "z":
            res.append("z"); cur = start; last = None
            continue
        sp = [S(p) for p in pts]
        if c == "M":
            res.append(f"M{f(sp[0][0])} {f(sp[0][1])}"); cur = start = sp[0]; last = "M"
            continue
        if c == "L":
            dx, dy = sp[0][0] - cur[0], sp[0][1] - cur[1]
            if dx == 0 and dy == 0:
                continue
            if dy == 0:
                op, args = "h", [dx]
            elif dx == 0:
                op, args = "v", [dy]
            else:
                op, args = "l", [dx, dy]
            seg = ""
            for j, v in enumerate(args):
                txt = f(v)
                if (j or last == op) and not txt.startswith("-"):
                    seg += " "
                seg += txt
            res.append(("" if last == op else op) + seg); last = op
            cur = sp[0]
        else:  # Q
            (cx, cy), (ex, ey) = sp
            res.append(f"q{f(cx - cur[0])} {f(cy - cur[1])} {f(ex - cur[0])} {f(ey - cur[1])}"); last = "q"
            cur = sp[1]
    return "".join(res)


def rescale_svg(svg, k, ox, oy, width, height, eps=0.0):
    def num(v, off=0.0):
        r = round((float(v) - off) * k, 1)
        return f"{r:g}"
    # pattern tiles keep their own coordinates; the scale goes into patternTransform instead
    patterns = re.findall(r"<pattern\b.*?</pattern>", svg, re.S)
    for i, block in enumerate(patterns):
        svg = svg.replace(block, f"<!--pattern{i}-->", 1)
    def restore(svg):
        for i, block in enumerate(patterns):
            m = re.search(r'patternTransform="([^"]*)"', block)
            scale = f"matrix({k:.5g} 0 0 {k:.5g} {-ox * k:.4g} {-oy * k:.4g})"
            if m:
                block = block.replace(m.group(0), f'patternTransform="{scale} {m.group(1)}"', 1)
            else:
                block = block.replace("<pattern ", f'<pattern patternTransform="{scale}" ', 1)
            svg = svg.replace(f"<!--pattern{i}-->", block, 1)
        return svg
    svg = re.sub(r' d="([^"]*)"', lambda m: f' d="{rescale_path(m.group(1), k, ox, oy, eps=eps)}"', svg)
    def user_space(tag):
        return not tag.startswith("<linearGradient") and not tag.startswith("<radialGradient") or 'userSpaceOnUse' in tag
    for attr, off in (("x", ox), ("cx", ox), ("x1", ox), ("x2", ox), ("y", oy), ("cy", oy), ("y1", oy), ("y2", oy)):
        svg = re.sub(rf'(<(?:rect|circle|linearGradient|radialGradient)[^>]*?) {attr}="({NUM})"',
                     lambda m: m.group(0).replace(f' {attr}="{m.group(2)}"', f' {attr}="{num(m.group(2), off)}"') if user_space(m.group(0)) else m.group(0), svg)
    for attr in ("width", "height", "r", "stroke-width"):
        svg = re.sub(rf'(<(?:rect|circle|path|g|radialGradient)[^>]*?) {attr}="({NUM})"',
                     lambda m: m.group(0).replace(f' {attr}="{m.group(2)}"', f' {attr}="{num(m.group(2))}"'), svg)
    svg = re.sub(r' stroke-dasharray="([^"]*)"', lambda m: ' stroke-dasharray="' + " ".join(num(v) for v in m.group(1).split()) + '"', svg)
    # rects without x/y start at 0 in picture units: shift them by the crop
    svg = re.sub(r'<rect (?![^>]*\by=)', f'<rect y="{num(0, oy)}" ', svg)
    # radial gradients squashed in y: recompute the translate for the new centre
    def fix_rad(m):
        tag = m.group(0)
        g = re.search(r'gradientTransform="matrix\(1 0 0 ([\d.]+) 0 [-\d.]+\)"', tag)
        if not g:
            return tag
        sy = float(g.group(1)); cy = float(re.search(r' cy="([-\d.]+)"', tag).group(1))
        return tag.replace(g.group(0), f'gradientTransform="matrix(1 0 0 {sy:g} 0 {round(cy * (1 - sy), 1):g})"')
    svg = re.sub(r"<radialGradient[^>]*>", fix_rad, svg)
    # the reflection: y_r = -s*y + T  ->  y_r' = -s*y' + (T - oy - s*oy) * k
    def fix_matrix(m):
        s, t = float(m.group(1)), float(m.group(2))
        return f'transform="matrix(1 0 0 -{s:g} 0 {round((t - oy - s * oy) * k, 1):g})"'
    svg = re.sub(r'transform="matrix\(1 0 0 -([\d.]+) 0 ([-\d.]+)\)"', fix_matrix, svg)
    svg = re.sub(r'viewBox="[^"]*"', f'viewBox="0 0 {width} {height}"', svg, count=1)
    svg = svg.replace(' stop-opacity="1"', "")
    svg = re.sub(r'(["\s(])(-?)0\.(\d)', r'\1\2.\3', svg)
    return restore(svg)
