"""Shared pieces for the bridge-ride scenes: the wide picture frame, the app's animation form, the highlight
limiter, and the cyclist built from rows of short strokes in six pedalling poses.

Frame: a 1920 x 1248 core with PAD units more scene on each side,
showing VIEW_H units of height, so the laptop (1512 x 949 pt picture area) fits by width and an
ultrawide window fits by width too. The limiter is a root-level rect in CSS px centred on the window.
"""
from __future__ import annotations

import math

import numpy as np

W, H = 1920, 1248
PAD = 400
XL, XR = -PAD, W + PAD
BEAT = 0.125
MAC_SCALE = 1512 / 1920
VIEW_H = round(949 / MAC_SCALE, 2)          # 1205.08
VIEW_Y = (H - VIEW_H) / 2
BAND = (340, 1580)                          # the 277-1240 pt text column at 1512 pt, in picture units


def pct(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".") + "%"


class Motion:
    """Keyframes and class rules in the only form the app animates (full shorthand, step-end, explicit stops)."""

    def __init__(self):
        self.frames: dict[str, str] = {}
        self.rules: list[str] = []
        self.shared: dict[tuple, str] = {}
        self.count = 0

    def keyframes(self, name, stops):
        assert stops[0][0] == 0 and stops[-1][0] == 1
        assert all(a[0] < b[0] for a, b in zip(stops, stops[1:])), name
        self.frames[name] = f"@keyframes {name}{{" + "".join(f"{pct(f * 100)}{{{v}}}" for f, v in stops) + "}"
        return name

    def use(self, name, seconds, delay=0.0):
        assert abs(seconds / BEAT - round(seconds / BEAT)) < 1e-6, seconds
        assert abs(delay / BEAT - round(delay / BEAT)) < 1e-6, delay
        key = (name, round(seconds / BEAT), round(delay / BEAT))
        if key not in self.shared:
            cls = f"m{self.count}"
            self.count += 1
            self.shared[key] = cls
            self.rules.append(f".{cls}{{animation:{name} {seconds:g}s step-end infinite {delay:g}s}}")
        return self.shared[key]

    def css(self):
        return ("<style>" + "".join(self.frames.values()) + "".join(self.rules)
                + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>")


def vgrad(gid, stops, y1, y2, x=0):
    s = "".join(f'<stop offset="{o}" stop-color="{c}"' + (f' stop-opacity="{a}"' if a != 1 else "") + "/>"
                for o, c, a in [(t[0], t[1], t[2] if len(t) > 2 else 1) for t in stops])
    return f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{x}" y1="{y1}" x2="{x}" y2="{y2}">{s}</linearGradient>'


def hgrad(gid, stops, x1, x2):
    s = "".join(f'<stop offset="{o}" stop-color="{c}"' + (f' stop-opacity="{a}"' if a != 1 else "") + "/>"
                for o, c, a in [(t[0], t[1], t[2] if len(t) > 2 else 1) for t in stops])
    return f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{x1}" y1="0" x2="{x2}" y2="0">{s}</linearGradient>'


def rgrad(gid, cx, cy, r, stops, sy=1.0):
    s = "".join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in stops)
    tf = f' gradientTransform="matrix(1 0 0 {sy} 0 {round(cy * (1 - sy), 1)})"' if sy != 1 else ""
    return f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{cx}" cy="{cy}" r="{r}"{tf}>{s}</radialGradient>'


def limiter(cap, glass, tint):
    """Highlight limiter: a darken blend behind the column caps every pixel at `cap` per channel, so lights magnified
    on big windows can't fill a glyph's box. It sits under the app's glass (opacity `glass`, colour `tint`), so it is
    drawn at cap' = (cap - glass tint) / (1 - glass) per channel, which the glass brings back to `cap`. Full through the
    text edge (366 CSS px) to 372, then a 12 px fade."""
    core, fade = 372, 12
    left, width = -(core + fade), 2 * (core + fade)
    off = lambda x: f"{(x - left) / width:.4f}".rstrip("0").rstrip(".")
    rgb = lambda h: (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))
    c = "#%02x%02x%02x" % tuple(max(0, min(255, round((v - glass * t) / (1 - glass)))) for v, t in zip(rgb(cap), rgb(tint)))
    s = (f'<stop offset="0" stop-color="{c}" stop-opacity="0"/><stop offset="{off(-core)}" stop-color="{c}"/>'
         f'<stop offset="{off(core)}" stop-color="{c}"/><stop offset="1" stop-color="{c}" stop-opacity="0"/>')
    return (f'<defs><linearGradient id="br-cap" x2="1">{s}</linearGradient></defs>'
            f'<rect x="50%" width="{width}" height="100%" transform="translate({left} 0)" fill="url(#br-cap)" style="mix-blend-mode:darken"/>')


def document(motion, defs, body):
    """Root in CSS px (no viewBox) holding the picture nested and sliced at the laptop framing."""
    pic = f'<svg width="100%" height="100%" viewBox="{XL} {VIEW_Y:g} {XR - XL} {VIEW_H}" preserveAspectRatio="xMidYMid slice">'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">{motion.css()}'
            f'{pic}<defs>{"".join(defs)}</defs>{"".join(body)}</svg></svg>')


# ------------------------------------------------------------------ the cyclist

def _seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = np.clip(((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy + 1e-12), 0, 1)
    return np.hypot(px - (ax + t * vx), py - (ay + t * vy)), t


def _ik(hip, target, l1, l2, bend=1):
    """Knee/elbow from a two-link chain; bend=+1 puts the joint on the left of hip->target (forward-up for a leg)."""
    dx, dy = target[0] - hip[0], target[1] - hip[1]
    d = min(math.hypot(dx, dy), l1 + l2 - 1e-6)
    a = math.atan2(dy, dx)
    cos_k = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    k = math.acos(max(-1, min(1, cos_k)))
    ang = a + bend * k
    return (hip[0] + l1 * math.cos(ang), hip[1] + l1 * math.sin(ang))


class Rider:
    """A road cyclist in side view, facing right, in metres (x forward, y up, ground at 0).

    shapes(phase) -> list of (kind, layer, params); layer 0 = far side, 1 = bike, 2 = near side.
    Everything is a tapered capsule, a ring or a filled circle, so it rasterises analytically."""

    R = 0.335            # wheel radius incl. tyre
    CRANK = 0.1725

    def __init__(self):
        self.rear = (0.0, self.R)
        self.front = (1.0, self.R)
        self.bb = (0.41, 0.27)
        self.st_top = (0.25, 0.80)
        self.ht_top = (0.86, 0.855)
        self.ht_bot = (0.895, 0.735)
        self.saddle = (0.21, 0.94)
        self.hip = (0.19, 0.99)
        self.shoulder = (0.66, 1.38)
        self.hands = (0.985, 0.925)

    def shapes(self, phase):
        S = []
        cap = lambda layer, a, b, ra, rb: S.append(("cap", layer, (a, b, ra, rb)))
        # far leg + far crank
        for side, layer in ((math.pi, 0), (0.0, 2)):
            th = phase + side
            pedal = (self.bb[0] + self.CRANK * math.cos(th), self.bb[1] + self.CRANK * math.sin(th))
            ankle = (pedal[0] - 0.075 + 0.025 * math.sin(th), pedal[1] + 0.075)
            knee = _ik(self.hip, ankle, 0.47, 0.45, bend=1)
            cap(layer, self.hip, knee, 0.075, 0.052)       # thigh
            cap(layer, knee, ankle, 0.05, 0.034)           # shin, tapering to the ankle
            toe = (pedal[0] + 0.075, pedal[1] - 0.01)
            cap(layer, (ankle[0] - 0.035, ankle[1] - 0.01), toe, 0.035, 0.026)   # shoe
            cap(1 if layer == 2 else 0, self.bb, pedal, 0.017, 0.017)          # crank arm
        # bike: wheels (rings + hubs), frame tubes, fork, bars, saddle, chainring
        for c in (self.rear, self.front):
            S.append(("ring", 1, (c, self.R - 0.024, 0.046)))      # tyre
            S.append(("disc", 1, (c, 0.022)))
        cap(1, self.bb, self.st_top, 0.02, 0.019)                   # seat tube
        cap(1, self.st_top, self.ht_top, 0.024, 0.024)              # top tube
        cap(1, self.bb, self.ht_bot, 0.024, 0.021)                  # down tube
        cap(1, self.ht_bot, self.ht_top, 0.022, 0.022)              # head tube
        cap(1, self.bb, self.rear, 0.016, 0.012)                    # chainstay
        cap(1, self.st_top, self.rear, 0.014, 0.011)                # seatstay
        cap(1, self.ht_bot, (self.front[0] - 0.02, self.front[1]), 0.018, 0.012)   # fork
        cap(1, self.st_top, (self.saddle[0] + 0.01, self.saddle[1] - 0.02), 0.014, 0.014)   # seatpost
        cap(1, (self.saddle[0] - 0.11, self.saddle[1]), (self.saddle[0] + 0.12, self.saddle[1] - 0.01), 0.022, 0.012)   # saddle
        cap(1, self.ht_top, (0.93, 0.905), 0.016, 0.016)            # stem
        cap(1, (0.93, 0.905), (0.985, 0.915), 0.016, 0.016)          # bar top
        cap(1, (0.985, 0.915), (1.005, 0.83), 0.015, 0.015)          # drop
        cap(1, (1.005, 0.83), (0.955, 0.80), 0.015, 0.015)
        S.append(("disc", 1, (self.bb, 0.1)))                       # chainring
        # rider body (near side layer 2; the far arm is hidden behind the near one in side view)
        cap(2, self.hip, self.shoulder, 0.115, 0.10)                # torso
        cap(2, (self.hip[0] - 0.02, self.hip[1] - 0.01), (self.hip[0] + 0.12, self.hip[1] + 0.06), 0.1, 0.09)   # seat/hips
        elbow = _ik(self.shoulder, self.hands, 0.30, 0.29, bend=-1)
        cap(2, self.shoulder, elbow, 0.05, 0.042)
        cap(2, elbow, self.hands, 0.04, 0.032)
        head = (self.shoulder[0] + 0.15, self.shoulder[1] + 0.16)
        cap(2, (self.shoulder[0] + 0.02, self.shoulder[1] + 0.03), head, 0.06, 0.05)   # neck
        S.append(("disc", 2, (head, 0.11)))
        S.append(("cap", 2, ((head[0] - 0.1, head[1] + 0.035), (head[0] + 0.07, head[1] + 0.06), 0.085, 0.07)))   # helmet
        return S

    LIGHT_REAR = (0.17, 0.85)     # under the saddle
    LIGHT_FRONT = (0.98, 0.95)    # on the bar


def _coverage(shapes, xs, ys, layer_max):
    """Label grid: -1 empty, else the topmost layer covering each sample."""
    X, Y = np.meshgrid(xs, ys)
    lab = np.full(X.shape, -1)
    for layer in (0, 1, 2):
        if layer > layer_max:
            break
        m = np.zeros(X.shape, bool)
        for kind, l, p in shapes:
            if l != layer:
                continue
            if kind == "cap":
                (ax, ay), (bx, by), ra, rb = p
                d, t = _seg_dist(X, Y, ax, ay, bx, by)
                m |= d <= ra + (rb - ra) * t
            elif kind == "ring":
                (cx, cy), r, w = p
                m |= np.abs(np.hypot(X - cx, Y - cy) - r) <= w / 2
            else:
                (cx, cy), r = p
                m |= np.hypot(X - cx, Y - cy) <= r
        lab[m] = layer
    return lab


def rider_rows(rider, phase, scale, pitch=1.0, sub=5, dx=0.04):
    """Rasterise one pose into rows of runs, in picture units relative to the wheel contact of the rear wheel
    (x right, y down, ground at 0). Returns {colour_key: {row_y: [(x0, x1), ...]}} with keys 'body' and 'rim'."""
    shapes = rider.shapes(phase)
    x_lo, x_hi = -0.45 * scale, 1.45 * scale
    rows_n = int(math.ceil(1.75 * scale / pitch))
    xs_u = np.arange(x_lo, x_hi, dx)
    out = {"body": {}, "rim": {}}
    layer2 = {}
    for r in range(rows_n):
        y_top = -(r + 1) * pitch
        sub_ys_u = y_top + (np.arange(sub) + 0.5) * pitch / sub          # picture units (y down, negative up)
        lab = _coverage(shapes, xs_u / scale, -sub_ys_u / scale, 2)
        filled = (lab >= 0).mean(axis=0) >= 0.4
        body_top = (lab == 2).mean(axis=0) >= 0.4
        y_c = round(y_top + pitch / 2, 3)
        if filled.any():
            out["body"][y_c] = _runs(xs_u, filled)
            layer2[y_c] = body_top
    # rim light: the top edge of the rider's body (helmet, back, shoulders), one row thick
    ys = sorted(out["body"])
    occ = {y: np.zeros(len(xs_u), bool) for y in ys}
    for y in ys:
        for a, b in out["body"][y]:
            occ[y][(xs_u >= a) & (xs_u <= b)] = True
    for i, y in enumerate(ys):
        above = occ[ys[i - 1]] if i > 0 and abs(ys[i - 1] - (y - pitch)) < 1e-6 else np.zeros(len(xs_u), bool)
        edge = occ[y] & ~above & layer2[y]
        if edge.any():
            out["rim"][y] = [(a, b) for a, b in _runs(xs_u, edge) if b - a > 0.6]
    return out


def _runs(xs, mask):
    runs = []
    on, start = False, 0.0
    for i, v in enumerate(mask):
        if v and not on:
            start, on = xs[i], True
        elif not v and on:
            runs.append((round(float(start), 2), round(float(xs[i - 1]), 2)))
            on = False
    if on:
        runs.append((round(float(start), 2), round(float(xs[-1]), 2)))
    return [(a, b) for a, b in runs if b - a > 0.15]


# ------------------------------------------------------------------ the moving rider

POSES = 6


def _same(a, b, tol=0.06):
    return len(a) == len(b) and all(abs(x0 - y0) < tol and abs(x1 - y1) < tol for (x0, x1), (y0, y1) in zip(a, b))


def _runs_path(rows):
    """All runs of a {row_y: [(x0, x1)]} map as one path of short horizontal strokes."""
    d = []
    for y, runs in sorted(rows.items()):
        for a, b in runs:
            d.append(f"M{a:.1f} {y:.1f}h{b - a:.1f}")
    return "".join(d).replace(".0 ", " ").replace(".0h", "h").replace(".0M", "M")


def rider_group(scale=30, body="#15111d", rim="#ffbd8a", rim_opacity=0.8, lights=True, motion=None, name="br"):
    """The rider drawn at the origin (rear wheel contact, x right, y down): rows shared by all poses once, six pose
    groups swapping by opacity (one beat each). Plain strokes, no dash patterns: it is moved by transforms."""
    rd = Rider()
    poses = [rider_rows(rd, -math.pi / 2 + i * 2 * math.pi / POSES, scale) for i in range(POSES)]
    shared = {"body": {}, "rim": {}}
    own = [{"body": {}, "rim": {}} for _ in range(POSES)]
    for key in ("body", "rim"):
        for y in set().union(*(p[key].keys() for p in poses)):
            rows = [p[key].get(y, []) for p in poses]
            if all(_same(rows[0], r) for r in rows[1:]):
                if rows[0]:
                    shared[key][y] = rows[0]
            else:
                for i, r in enumerate(rows):
                    if r:
                        own[i][key][y] = r

    def grp(rows):
        out = ""
        if rows["body"]:
            out += f'<path stroke="{body}" d="{_runs_path(rows["body"])}"/>'
        if rows["rim"]:
            out += f'<path stroke="{rim}" opacity="{rim_opacity}" d="{_runs_path(rows["rim"])}"/>'
        return out
    pose = motion.keyframes(f"{name}pose", [(0, "opacity:1"), (1 / POSES, "opacity:0"), (1, "opacity:0")])
    parts = [grp(shared)]
    for i in range(POSES):
        parts.append(f'<g class="{motion.use(pose, POSES * BEAT, -i * BEAT)}" opacity="{1 if i == 0 else 0}">{grp(own[i])}</g>')
    if lights:
        (rx, ry), (fx, fy) = Rider.LIGHT_REAR, Rider.LIGHT_FRONT
        parts.append(f'<path stroke="#ff3b3b" stroke-width="2.2" d="M{rx * scale - 1:.1f} {-ry * scale:.1f}h2"/>'
                     f'<path stroke="#fff2cc" stroke-width="2.2" d="M{fx * scale - 1:.1f} {-fy * scale:.1f}h2"/>')
    return f'<g fill="none" stroke-width="1.5">{"".join(parts)}</g>'


def rider_ride(motion, y_ground, x_from, x_to, scale=30, step=11, name="br", rest_x=None, **kw):
    """The rider crossing left to right on a straight deck at y_ground, looping. Two nested CSS transforms: the outer
    jumps CHUNK steps at a time, the inner walks one step a beat through the chunk (25 + 11 stops instead of 275)."""
    chunk = 11
    x_start = x_from - 1.5 * scale
    n = math.ceil((x_to + 0.5 * scale - x_start) / (step * chunk))
    outer = motion.keyframes(f"{name}go", [(k / n, f"transform:translate({x_start + step * chunk * k:.0f}px,{y_ground}px)") for k in range(n)]
                             + [(1, f"transform:translate({x_start + step * chunk * (n - 1):.0f}px,{y_ground}px)")])
    inner = motion.keyframes(f"{name}step", [(j / chunk, f"transform:translate({step * j}px,0)") for j in range(chunk)]
                             + [(1, f"transform:translate({step * (chunk - 1)}px,0)")])
    beats = n * chunk
    # the attribute is the still frame (motion off): the rider standing where rest_x puts him; CSS overrides it
    rest = x_start if rest_x is None else rest_x
    svg = (f'<g class="{motion.use(outer, beats * BEAT)}" transform="translate({rest:.0f} {y_ground})">'
           f'<g class="{motion.use(inner, chunk * BEAT)}">{rider_group(scale, motion=motion, name=name, **kw)}</g></g>')
    return svg, dict(beats=beats, seconds=beats * BEAT, chars=len(svg))


def slide(motion, name, inner, x_start, x_end, y, step, chunk=11, extra_y=0.0):
    """Move `inner` (drawn at its own origin) from x_start to x_end at `step` units a beat (negative = leftward), looping,
    with two nested CSS transforms (outer jumps a chunk, inner walks one step a beat). y may drift by extra_y overall."""
    span = x_end - x_start
    n = max(1, math.ceil(abs(span) / abs(step * chunk)))
    pos = lambda k: (x_start + step * chunk * k, y + extra_y * k / n)
    outer = motion.keyframes(f"{name}go", [(k / n, f"transform:translate({pos(k)[0]:.0f}px,{pos(k)[1]:.1f}px)") for k in range(n)]
                             + [(1, f"transform:translate({pos(n - 1)[0]:.0f}px,{pos(n - 1)[1]:.1f}px)")])
    inner_k = motion.keyframes(f"{name}st", [(j / chunk, f"transform:translate({step * j}px,0)") for j in range(chunk)]
                               + [(1, f"transform:translate({step * (chunk - 1)}px,0)")])
    beats = n * chunk
    return (f'<g class="{motion.use(outer, beats * BEAT)}" transform="translate({x_start:.0f} {y})">'
            f'<g class="{motion.use(inner_k, chunk * BEAT)}">{inner}</g></g>'), beats


def cycle(motion, name, n_states, beats_each, svgs):
    """Show svgs[i] in turn, each for beats_each beats, looping."""
    total = n_states * beats_each
    on = motion.keyframes(f"{name}cy", [(0, "opacity:1"), (beats_each / total, "opacity:0"), (1, "opacity:0")])
    out = []
    for i, s in enumerate(svgs):
        out.append(f'<g class="{motion.use(on, total * BEAT, -i * beats_each * BEAT)}" opacity="{1 if i == 0 else 0}">{s}</g>')
    return "".join(out)


def swell(motion, name, period_beats, lo, hi, phase_beats=0, steps=None):
    """A slow opacity breath between lo and hi (cosine), one stop a beat while it changes; returns the class."""
    steps = steps or period_beats
    stops = []
    for k in range(steps + 1):
        t = k / steps
        v = lo + (hi - lo) * (0.5 - 0.5 * math.cos(2 * math.pi * t))
        stops.append((t, f"opacity:{v:.3f}".rstrip("0").rstrip(".")))
    key = motion.keyframes(f"{name}sw", stops)
    return motion.use(key, period_beats * BEAT, -phase_beats * BEAT)



def col(x, ramp=200):
    """1 inside the laptop text column, 0 in the margins, smoothstep between (dim small bright things at the source)."""
    a, b = BAND
    if a <= x <= b:
        return 1.0
    t = (a - x) / ramp if x < a else (x - b) / ramp
    t = max(0.0, min(1.0, t))
    return 1 - t * t * (3 - 2 * t)


def hstops(gid, stops):
    """A horizontal userSpace gradient across the wide picture from (x, colour, opacity) stops."""
    return (f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{XL}" x2="{XR}">'
            + "".join(f'<stop offset="{(x - XL) / (XR - XL):.3f}" stop-color="{c}" stop-opacity="{o}"/>' for x, c, o in stops) + '</linearGradient>')


# ------------------------------------------------------------------ the rider from any side (for roads that turn)

def rider_shapes3d(rider, phase):
    """The same rider in 3D: (kind, part, params) with points (x forward, y up, z toward the camera's right when seen
    from behind). Legs and arms sit off the bike's plane; wheels are rings in the bike's plane."""
    S = []
    cap = lambda part, a, b, ra, rb: S.append(("cap", part, (a, b, ra, rb)))
    P = lambda p, z=0.0: (p[0], p[1], z)
    for side, z in ((math.pi, -0.11), (0.0, 0.11)):          # far (left) leg, near (right) leg
        th = phase + side
        pedal = (rider.bb[0] + rider.CRANK * math.cos(th), rider.bb[1] + rider.CRANK * math.sin(th))
        ankle = (pedal[0] - 0.075 + 0.025 * math.sin(th), pedal[1] + 0.075)
        knee = _ik(rider.hip, ankle, 0.47, 0.45, bend=1)
        cap("leg", P(rider.hip, z * 0.9), P(knee, z * 1.05), 0.075, 0.052)
        cap("leg", P(knee, z * 1.05), P(ankle, z), 0.05, 0.034)
        cap("leg", P((ankle[0] - 0.035, ankle[1] - 0.01), z), P((pedal[0] + 0.075, pedal[1] - 0.01), z), 0.035, 0.026)
        cap("bike", P(rider.bb, z * 0.6), P(pedal, z), 0.017, 0.017)
    for c in (rider.rear, rider.front):
        S.append(("ring", "bike", (P(c), rider.R - 0.024, 0.046)))
        S.append(("disc", "bike", (P(c), 0.022)))
    for a, b, ra, rb in ((rider.bb, rider.st_top, 0.02, 0.019), (rider.st_top, rider.ht_top, 0.024, 0.024),
                         (rider.bb, rider.ht_bot, 0.024, 0.021), (rider.ht_bot, rider.ht_top, 0.022, 0.022),
                         (rider.bb, rider.rear, 0.016, 0.012), (rider.st_top, rider.rear, 0.014, 0.011),
                         (rider.ht_bot, (rider.front[0] - 0.02, rider.front[1]), 0.018, 0.012),
                         (rider.st_top, (rider.saddle[0] + 0.01, rider.saddle[1] - 0.02), 0.014, 0.014),
                         ((rider.saddle[0] - 0.11, rider.saddle[1]), (rider.saddle[0] + 0.12, rider.saddle[1] - 0.01), 0.03, 0.02),
                         (rider.ht_top, (0.93, 0.905), 0.016, 0.016)):
        cap("bike", P(a), P(b), ra, rb)
    for z in (-0.2, 0.2):                                      # the handlebar's two drops
        cap("bike", P((0.93, 0.905), 0), P((0.985, 0.915), z), 0.016, 0.016)
        cap("bike", P((0.985, 0.915), z), P((1.005, 0.83), z), 0.015, 0.015)
    S.append(("disc", "bike", (P(rider.bb, 0.05), 0.1)))
    cap("body", P(rider.hip), P(rider.shoulder), 0.15, 0.17)   # torso: wider than deep (shoulders ~0.4 m)
    cap("body", P((rider.hip[0] - 0.02, rider.hip[1] - 0.01)), P((rider.hip[0] + 0.12, rider.hip[1] + 0.06)), 0.12, 0.11)
    for z in (-0.19, 0.19):
        elbow = _ik(rider.shoulder, rider.hands, 0.30, 0.29, bend=-1)
        cap("body", P(rider.shoulder, z), P(elbow, z * 1.05), 0.05, 0.042)
        cap("body", P(elbow, z * 1.05), P(rider.hands, z), 0.04, 0.032)
    head = (rider.shoulder[0] + 0.15, rider.shoulder[1] + 0.16)
    cap("body", P((rider.shoulder[0] + 0.02, rider.shoulder[1] + 0.03)), P(head), 0.06, 0.05)
    S.append(("disc", "body", (P(head), 0.11)))
    cap("body", P((head[0] - 0.1, head[1] + 0.035)), P((head[0] + 0.07, head[1] + 0.06)), 0.09, 0.08)
    return S


def rider_rows_view(rider, phase, scale, yaw, pitch=1.0, sub=5, dx=0.04):
    """Rows of runs for the rider seen at `yaw` degrees (0 = side view facing right, 90 = from behind, riding away;
    -90 = from the front). Orthographic. Same output shape as rider_rows: {'body': {y: runs}, 'rim': {...}}."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    shapes = rider_shapes3d(rider, phase)
    proj = lambda p: (p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c)     # screen x, y, depth (+ = toward us)
    items = []
    for kind, part, prm in shapes:
        if kind == "cap":
            a, b, ra, rb = prm
            pa, pb = proj(a), proj(b)
            items.append(((pa[2] + pb[2]) / 2, kind, part, (pa, pb, ra, rb)))
        else:
            ctr = proj(prm[0])
            items.append((ctr[2], kind, part, (ctr,) + tuple(prm[1:])))
    items.sort(key=lambda t: t[0])                                     # far first
    x_lo, x_hi = (-0.45 * abs(c) - 0.35) * scale, (1.45 * abs(c) + 0.35) * scale
    xs_u = np.arange(x_lo, x_hi, dx)
    out = {"body": {}, "rim": {}}
    rows_n = int(math.ceil(1.75 * scale / pitch))
    layer2 = {}
    for r in range(rows_n):
        y_top = -(r + 1) * pitch
        sub_ys = y_top + (np.arange(sub) + 0.5) * pitch / sub
        X, Y = np.meshgrid(xs_u / scale, -sub_ys / scale)
        filled = np.zeros(X.shape, bool)
        body = np.zeros(X.shape, bool)
        for _, kind, part, prm in items:
            if kind == "cap":
                (ax, ay, _), (bx, by, _), ra, rb = prm
                d, t = _seg_dist(X, Y, ax, ay, bx, by)
                m = d <= ra + (rb - ra) * t
            elif kind == "ring":
                (cx, cy, _), rad, w = prm
                a = max(rad * abs(c), 0.001)
                # an ellipse ring: radial distance in normalised space, scaled back by the local radius
                q = np.hypot((X - cx) / a, (Y - cy) / rad)
                m = np.abs(q - 1) * np.minimum(rad, np.maximum(a, w)) <= w / 2 + 0.004 if a > 0.03 else ((np.abs(X - cx) <= w / 2 + a) & (np.abs(Y - cy) <= rad + w / 2))
            else:
                (cx, cy, _), rad = prm
                m = np.hypot(X - cx, Y - cy) <= rad
            filled |= m
            body = np.where(m, part == "body", body)
        f = filled.mean(axis=0) >= 0.4
        y_c = round(y_top + pitch / 2, 3)
        if f.any():
            out["body"][y_c] = _runs(xs_u, f)
            layer2[y_c] = body.mean(axis=0) >= 0.4
    ys = sorted(out["body"])
    occ = {y: np.zeros(len(xs_u), bool) for y in ys}
    for y in ys:
        for a_, b_ in out["body"][y]:
            occ[y][(xs_u >= a_) & (xs_u <= b_)] = True
    for i, y in enumerate(ys):
        above = occ[ys[i - 1]] if i > 0 and abs(ys[i - 1] - (y - pitch)) < 1e-6 else np.zeros(len(xs_u), bool)
        edge = occ[y] & ~above & layer2[y]
        if edge.any():
            out["rim"][y] = [(a_, b_) for a_, b_ in _runs(xs_u, edge) if b_ - a_ > 0.6]
    return out
