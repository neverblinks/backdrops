"""Rescale a card SVG written in picture units to card pixels (fewer digits): every coordinate and length is
multiplied by k after shifting by (-ox, -oy). Handles path data (M L H V C Q A Z, absolute and relative), the
geometry attributes, stroke widths, dash arrays, userSpaceOnUse gradients and their matrix gradientTransform."""
import re
NUM = r"-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?"


def fmt(v):
    a = abs(v)
    s = f"{v:.0f}" if a >= 20 else f"{v:.1f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    s = s.replace("-0.", "-.", 1) if s.startswith("-0.") else (s[1:] if s.startswith("0.") else s)
    return "0" if s in ("-0", "", "-") else s


def path(d, k, ox, oy):
    """Scale path data, rounding ABSOLUTE positions to integers and re-deriving relative steps from them (no drift)."""
    toks = re.findall(rf"[A-Za-z]|{NUM}", d)
    arity = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "Q": 4, "A": 7, "Z": 0, "S": 4, "T": 2}
    out, i, cmd = [], 0, None
    cx = cy = sx = sy = 0.0          # current and subpath start, in source units
    rx_ = ry_ = 0                    # current point, rounded, in card units
    srx = sry = 0
    R = lambda v: int(round(v))
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t; i += 1
            if cmd in "Zz":
                out.append("z"); cx, cy, rx_, ry_ = sx, sy, srx, sry
            continue
        up, rel = cmd.upper(), cmd.islower()
        n = arity[up]
        v = [float(x) for x in toks[i:i + n]]; i += n
        def ab(x, y):
            return (cx + x, cy + y) if rel else (x, y)
        if up in "MLT":
            ax, ay = ab(v[0], v[1])
            nx, ny = R((ax - ox) * k), R((ay - oy) * k)
            letter = "m" if up == "M" else "l"
            seg = f"{letter}{nx - rx_} {ny - ry_}" if up != "M" or out else f"M{nx} {ny}"
            if up == "M" and out:
                seg = f"m{nx - rx_} {ny - ry_}"
            out.append(seg)
            cx, cy, rx_, ry_ = ax, ay, nx, ny
            if up == "M":
                sx, sy, srx, sry = ax, ay, nx, ny
                cmd = "l" if rel else "L"
        elif up == "H":
            ax = cx + v[0] if rel else v[0]
            nx = R((ax - ox) * k); out.append(f"h{nx - rx_}"); cx, rx_ = ax, nx
        elif up == "V":
            ay = cy + v[0] if rel else v[0]
            ny = R((ay - oy) * k); out.append(f"v{ny - ry_}"); cy, ry_ = ay, ny
        elif up in "CQS":
            pts = [ab(v[j], v[j + 1]) for j in range(0, n, 2)]
            sc = [(R((x - ox) * k), R((y - oy) * k)) for x, y in pts]
            letter = up.lower()
            out.append(letter + " ".join(f"{x - rx_} {y - ry_}" for x, y in sc))
            cx, cy = pts[-1]; rx_, ry_ = sc[-1]
        elif up == "A":
            ax, ay = ab(v[5], v[6])
            nx, ny = R((ax - ox) * k), R((ay - oy) * k)
            out.append(f"a{fmt(v[0] * k)} {fmt(v[1] * k)} {fmt(v[2])} {int(v[3])} {int(v[4])} {nx - rx_} {ny - ry_}")
            cx, cy, rx_, ry_ = ax, ay, nx, ny
    # compact: drop zero moves, repeated command letters (implicit repeats), and spaces before minus signs
    segs = [o for o in out if o not in ("l0 0", "h0", "v0")]
    merged, last = [], None
    for o in segs:
        letter = o[0]
        if letter == last and letter in "lhvcq":
            body = o[1:]
            merged.append(body if body.startswith("-") else " " + body)
        else:
            merged.append(o)
        last = letter if letter.isalpha() else last
    return re.sub(r" -", "-", "".join(merged))


def drop_unused(svg):
    """Remove gradients, masks and clip paths nothing references."""
    for m in list(re.finditer(r'<(linearGradient|radialGradient|mask|clipPath)\b[^>]*id="([^"]+)".*?</\1>', svg, re.S)):
        if f"url(#{m.group(2)})" not in svg:
            svg = svg.replace(m.group(0), "")
    return re.sub(r'offset="([.\d]+)"', lambda m: f'offset="{float(m.group(1)):.3f}"'.replace('"0.', '".').rstrip("0").replace('.000"', '0"'), svg)


def scale_svg(svg, k, ox, oy):
    svg = re.sub(r'\sd="([^"]*)"', lambda m: f' d="{path(m.group(1), k, ox, oy)}"', svg)
    for a, off in (("x", "x"), ("cx", "x"), ("x1", "x"), ("x2", "x"), ("y", "y"), ("cy", "y"), ("y1", "y"), ("y2", "y")):
        svg = re.sub(rf'(\s{a}=")({NUM})"', lambda m, off=off: f'{m.group(1)}{fmt((float(m.group(2)) - (ox if off == "x" else oy)) * k)}"', svg)
    for a in ("width", "height", "r", "rx", "ry", "stroke-width"):
        svg = re.sub(rf'(\s{a}=")({NUM})"', lambda m: f'{m.group(1)}{fmt(float(m.group(2)) * k)}"', svg)
    svg = re.sub(r'(stroke-dasharray=")([^"]*)"', lambda m: m.group(1) + " ".join(fmt(float(v) * k) for v in m.group(2).split()) + '"', svg)
    svg = re.sub(rf'gradientTransform="matrix\(({NUM}) ({NUM}) ({NUM}) ({NUM}) ({NUM}) ({NUM})\)"',
                 lambda m: f'gradientTransform="matrix({m.group(1)} {m.group(2)} {m.group(3)} {m.group(4)} {fmt(float(m.group(5)) * k)} {fmt(float(m.group(6)) * k)})"', svg)
    return svg


def _rdp(pts, eps):
    if len(pts) < 3:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    n = (dx * dx + dy * dy) ** 0.5 or 1e-9
    worst, at = -1.0, 0
    for i, (x, y) in enumerate(pts[1:-1], 1):
        d = abs(dy * (x - x0) - dx * (y - y0)) / n
        if d > worst:
            worst, at = d, i
    if worst <= eps:
        return [pts[0], pts[-1]]
    return _rdp(pts[:at + 1], eps)[:-1] + _rdp(pts[at:], eps)


def simplify(svg, eps=0.8):
    """Douglas-Peucker every straight-segment subpath (M then l/h/v only) in card units; curves are left alone."""
    def one(d):
        if re.search(r"[CcQqAaSsTt]", d):
            return d
        out = []
        for sub in re.findall(r"[Mm][^Mm]*", d):
            toks = re.findall(rf"[A-Za-z]|{NUM}", sub)
            if toks[0] != "M" or any(t in "LHVhv" for t in toks if t.isalpha() and t not in "Mlz"):
                out.append(sub); continue
            x, y = float(toks[1]), float(toks[2])
            pts = [(x, y)]
            closed = sub.rstrip().endswith(("z", "Z"))
            nums = [float(t) for t in toks[3:] if not t.isalpha()]
            for i in range(0, len(nums) - 1, 2):
                x += nums[i]; y += nums[i + 1]
                pts.append((x, y))
            pts = _rdp(pts, eps)
            seg = f"M{fmt(pts[0][0])} {fmt(pts[0][1])}"
            if len(pts) > 1:
                rel = []
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    rel.append(f"{fmt(bx - ax)} {fmt(by - ay)}")
                seg += "l" + " ".join(rel)
            out.append(re.sub(r" -", "-", seg) + ("z" if closed else ""))
        return "".join(out)
    return re.sub(r'\sd="([^"]*)"', lambda m: f' d="{one(m.group(1))}"', svg)
