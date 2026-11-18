"""After Hours: a synthwave Miami night, city lights over the bay from a rooftop.
Original composition (no logo, characters, lettering or traced art). Sister of Magenta Hour.

    python3 -I themes/after-hours/make-scene.py            (from the repository root; Python 3 only)

Writes plugins/after-hours/hooks/scene-after-hours.js (export const SCENE), cards/after-hours.svg (the
picker's live card, at most 20,000 characters) and, beside this file and not committed, scene-preview.svg,
scene-still.svg (default frame), scene-lit.svg (every animated group at its brightest, for the contrast
check) and scene-raw.svg (the picture alone, for likeness).

The app's glass (#06050f at 0.57, set in look-after-hours.ts) dims the chat column and follows it when the sidebar
or the right panel opens; a highlight limiter in the scene caps the brightest lights behind the text.

App rules (the Claude desktop app's backdrop limits): a root <svg> in CSS px holding the picture as one
nested <svg viewBox> + slice in picture units, with the limiter in CSS px over it; animation as the full shorthand with
step-end and explicit ascending % stops on a 0.125 s beat; only opacity and stroke-dashoffset, on groups;
the default frame is a complete picture; the only media query is prefers-reduced-motion.
"""
from __future__ import annotations

import json
import math
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from svglib import H, W, Palm, cloud, poly, polys, tower_shape  # noqa: E402

ROOT = HERE.parent.parent
CAP = 131072
HEADROOM = 250   # the character count is exact, so a small margin under the 131,072 cap is enough
BEAT = 0.125

# Wide picture: the original 1920 x 1248 scene stays untouched in the middle
# and PAD units of extra scene continue on each side, so a laptop window (about the picture's own 1.54 shape) shows
# exactly what it did, while a 21:9 window keeps ~88% of the height instead of 65%. The extension draws from its
# own random generator, so no original shape or random draw changes.
PAD = 400
XL, XR = -PAD, W + PAD

HORIZON = 712           # where the city meets the bay
MOON = (1806, 145)   # clear of the window's title bar, still clearly above the spire
EDGE = 1128          # the rooftop edge and its cyan strip

# Text column in picture units, as measured in a 1512 pt laptop window: BAND
# covers 1512 pt collapsed 349-1571 and open 561-1690, 1440 pt 318-1602, the 1000 pt pop-out 348-1572.
BAND = (340, 1580)
# The app's glass over the chat column, as plugins/after-hours/hooks/look-after-hours.ts sets it (blur 0). It
# follows the column when the sidebar or the right panel opens.
GLASS, GLASS_TINT = 0.57, "#06050f"

# The MacBook's picture area is 1512 x 949 pt (the window under the 33 pt menu bar), where the original 1920-wide picture fitted by WIDTH: 1512 / 1920 = 0.7875 pt a unit. The wide
# picture showed 1248 units of height and so fitted by height there (949 / 1248 = 0.760): everything 3.5% smaller.
# Showing 1205 units of height (21.5 trimmed top and bottom, as that view always cropped) fits by width again.
MAC_SCALE = 1512 / 1920                     # pt per picture unit on the MacBook (the 1512 pt window's width)
VIEW_H = round(949 / MAC_SCALE, 2)          # 1205.08: the picture height the scene shows
VIEW_Y = (1248 - VIEW_H) / 2

# quiet: lights behind the text column drawn dimmer in the picture (inside()). The scene leaves that to the glass, so
# lights beside the column on a wide window keep their full brightness; the card keeps its quieter middle.
FULL = dict(windows=1.0, reflections=1.0, blades=1.0, fronds=1.0, grain=True, sway=True, extras=True, stars=1.0, wide=True,
            quiet=False)
# the card: less detail and no motion, but still the palms, the yacht and the speedboat
THUMB = dict(windows=0.2, reflections=0.13, blades=0.3, fronds=0.34, grain=False, sway=False, extras=False, stars=0.06, wide=False,
             quiet=True)
DETAIL = dict(FULL)


# ------------------------------------------------------------------ animation bookkeeping

def pct(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".") + "%"


class Motion:
    """Keyframes and class rules, written in the form the app animates."""

    def __init__(self, lit=False):
        self.frames: dict[str, str] = {}
        self.rules: list[str] = []
        self.shared: dict[tuple, str] = {}
        self.count = 0
        self.lit = lit

    def keyframes(self, name, stops):
        assert stops[0][0] == 0 and stops[-1][0] == 1
        assert all(a[0] < b[0] for a, b in zip(stops, stops[1:])), name
        sel = [f"{f * 100:.2f}".rstrip("0").rstrip(".") + "%" for f, v in stops]   # 2 decimals: 2 ms on the longest loop
        assert all(float(a[:-1]) < float(b[:-1]) for a, b in zip(sel, sel[1:])), name
        self.frames[name] = f"@keyframes {name}{{" + "".join(f"{s}{{{v}}}" for s, (f, v) in zip(sel, stops)) + "}"
        return name

    def use(self, name, seconds, delay=0.0):
        assert abs(seconds / BEAT - round(seconds / BEAT)) < 1e-6, seconds
        assert abs(delay / BEAT - round(delay / BEAT)) < 1e-6, delay
        # one class per distinct rule: elements with the same animation, length and delay share it (the speedboat's
        # strokes, matching palm poses); it renders exactly as one class each did
        key = (name, round(seconds / BEAT), round(delay / BEAT))
        if key in self.shared:
            return self.shared[key]
        cls = f"m{self.count}"
        self.count += 1
        self.shared[key] = cls
        self.rules.append(f".{cls}{{animation:{name} {seconds:g}s step-end infinite {delay:g}s}}")
        return cls

    def css(self):
        return ("<style>" + "".join(self.frames.values()) + "".join(self.rules)
                + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>")

    def hidden(self, default_visible: bool) -> str:
        """The opacity attribute of a group that animates: shown in the lit variant."""
        return "1" if (default_visible or self.lit) else "0"


def dash_flow(motion, name, period, beats, sign):
    stops = [(k / beats, f"stroke-dashoffset:{round(sign * period * k / beats)}") for k in range(beats + 1)]
    return motion.keyframes(name, stops)


def vgrad(gid, stops, y1, y2):
    s = "".join(f'<stop offset="{o}" stop-color="{c}"' + (f' stop-opacity="{a}"' if a != 1 else "") + "/>" for o, c, a in stops)
    return f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" y1="{y1}" x2="0" y2="{y2}">{s}</linearGradient>'


def rgrad(gid, cx, cy, r, stops, sy=1.0):
    s = "".join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in stops)
    tf = f' gradientTransform="matrix(1 0 0 {sy} 0 {round(cy * (1 - sy), 1)})"' if sy != 1 else ""
    return f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{cx}" cy="{cy}" r="{r}"{tf}>{s}</radialGradient>'


# Highlight limiter (proven in the app). Behind the column a darken blend caps every
# pixel at LIM_CAP per channel. The background behind the text stays under it (its 99.5th percentile is
# (67, 49, 87)); only lights brighter than that are capped, to luminance <= 0.0533 (secondary text >= 4.5:1 at any
# window size, where magnified windows used to fill a glyph's box).
LIM_CAP = "#463a68"   # (70, 58, 104)


def limiter(gid="ns-cap"):
    """The cap sits under the app's glass, so it is drawn at cap' = (cap - g tint) / (1 - g) per channel: under the
    glass that lands on LIM_CAP. It reaches through the text column's edge (366 CSS px) before it fades."""
    core, fade = 372, 12                       # CSS px from the window centre
    left, width = -(core + fade), 2 * (core + fade)
    def off(x):
        return f"{(x - left) / width:.4f}".rstrip("0").rstrip(".")
    rgb = lambda h: (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))
    cap = "#%02x%02x%02x" % tuple(max(0, min(255, round((c - GLASS * t) / (1 - GLASS))))
                                  for c, t in zip(rgb(LIM_CAP), rgb(GLASS_TINT)))
    s = (f'<stop offset="0" stop-color="{cap}" stop-opacity="0"/><stop offset="{off(-core)}" stop-color="{cap}"/>'
         f'<stop offset="{off(core)}" stop-color="{cap}"/><stop offset="1" stop-color="{cap}" stop-opacity="0"/>')
    return (f'<defs><linearGradient id="{gid}" x2="1">{s}</linearGradient></defs>'
            f'<rect x="50%" width="{width}" height="100%" transform="translate({left} 0)" fill="url(#{gid})" style="mix-blend-mode:darken"/>')


def span():
    """(left, width) of the picture: the wide one for the scene, the original for the card."""
    return (XL, XR - XL) if DETAIL["wide"] else (0, W)


def ext_ranges(pad_extra=0):
    """The two side strips the wide picture adds (empty for the card)."""
    return [(XL - pad_extra, 0), (W, XR + pad_extra)] if DETAIL["wide"] else []


def inside(x):
    return DETAIL["quiet"] and BAND[0] - 30 < x < BAND[1] + 20


# ------------------------------------------------------------------ sky

def sky(motion, defs, body, rng):
    # the night here is a luminous violet, not black (sky #524978 -> #82648a)
    defs.append(vgrad("ns-sky", [(0, "#272049", 1), (0.3, "#3a2f62", 1), (0.58, "#504178", 1), (0.8, "#685083", 1),
                                 (0.93, "#815d89", 1), (1, "#97688b", 1)], 0, HORIZON))
    defs.append(rgrad("ns-glow-r", 1760, HORIZON, 760, [(0, "#e07aa8", 0.62), (0.4, "#8a4c8c", 0.22), (1, "#8a4c8c", 0)], sy=0.5))
    defs.append(rgrad("ns-glow-l", 120, HORIZON, 640, [(0, "#d475a6", 0.56), (0.5, "#7d4886", 0.16), (1, "#7d4886", 0)], sy=0.5))
    defs.append(rgrad("ns-moon-glow", MOON[0], MOON[1], 170, [(0, "#d8ccff", 0.32), (0.4, "#9d8ad8", 0.1), (1, "#9d8ad8", 0)]))
    defs.append(vgrad("ns-cityglow", [(0, "#c25a9a", 0), (0.6, "#b85c98", 0.18), (1, "#e884b0", 0.34)], HORIZON - 260, HORIZON))
    x0, sw = span()
    for g in ("ns-sky", "ns-glow-r", "ns-glow-l"):
        body.append(f'<rect x="{x0}" width="{sw}" height="{HORIZON + 2}" fill="url(#{g})"/>')
    body.append(f'<rect x="{x0}" y="{HORIZON - 260}" width="{sw}" height="262" fill="url(#ns-cityglow)"/>')
    body.append(f'<circle cx="{MOON[0]}" cy="{MOON[1]}" r="170" fill="url(#ns-moon-glow)"/>')

    # stars: steady ones, and two sets that twinkle; none near the city glow
    sets = [[], [], []]
    for i in range(round(150 * DETAIL["stars"])):
        x, y = rng.uniform(0, W), rng.uniform(6, 400) ** 1.0
        if math.hypot(x - MOON[0], y - MOON[1]) < 60:
            continue
        sets[i % 3].append((x, f"M{round(x)} {round(y)}h.5"))
    ext = random.Random(911)   # the side strips' own stars (the original draws stay as they were)
    for lo, hi in ext_ranges():
        for i in range(round(0.4 * 150 * DETAIL["stars"] * (hi - lo) / W)):
            x, y = ext.uniform(lo, hi), ext.uniform(6, 400)
            sets[i % 3].append((x, f"M{round(x)} {round(y)}h.5"))
    def star_paths(group, op):
        out_ = "".join(d for x, d in group if not inside(x)); in_ = "".join(d for x, d in group if inside(x))
        return (f'<path stroke="#ece4ff" stroke-width="2.2" stroke-linecap="round" opacity="{op}" d="{out_}"/>'
                f'<path stroke="#ece4ff" stroke-width="2.2" stroke-linecap="round" opacity="{op * 0.45:.2f}" d="{in_}"/>')
    screen = DETAIL["extras"] and DETAIL["wide"]
    def all_stars(group, op):
        return f'<path stroke="#ece4ff" stroke-width="2.2" stroke-linecap="round" opacity="{op}" d="{"".join(d for x, d in group)}"/>'
    draw = all_stars if screen else star_paths
    stars = draw(sets[0], 0.5)
    if DETAIL["extras"]:
        ks = motion.keyframes("nstw", [(0, "opacity:.7"), (0.3, "opacity:.15"), (0.55, "opacity:.7"), (1, "opacity:.7")])
        for i in (1, 2):
            stars += f'<g class="{motion.use(ks, 5, -2.5 * (i - 1))}">{draw(sets[i], 0.7)}</g>'
    body.append(stars)

    # a crescent: the lit disc, then a disc of sky over it (same gradient, so it blends)
    # a true crescent (lit disc minus the offset disc), so the glow shows through the dark side:
    # the lit disc's far arc between the two circles' crossing points, back along the offset disc's arc
    mx, my, R, ox, oy, r2 = MOON[0], MOON[1], 30, MOON[0] - 12, MOON[1] - 7, 27
    d = math.hypot(ox - mx, oy - my)
    a = (R * R - r2 * r2 + d * d) / (2 * d)
    hh = math.sqrt(R * R - a * a)
    ux, uy = (ox - mx) / d, (oy - my) / d
    px, py = mx + a * ux, my + a * uy
    i1, i2 = (px - hh * uy, py + hh * ux), (px + hh * uy, py - hh * ux)
    def arc(cx, cy, rad, p_from, p_to, away):
        """Points on a circle from p_from to p_to, going round the side facing direction `away`."""
        t0, t1 = math.atan2(p_from[1] - cy, p_from[0] - cx), math.atan2(p_to[1] - cy, p_to[0] - cx)
        mid = math.atan2(away[1], away[0])
        for sweep in (((t1 - t0) % (2 * math.pi)), -((t0 - t1) % (2 * math.pi))):
            tm = t0 + sweep / 2
            if math.cos(tm - mid) > 0:
                return [(cx + rad * math.cos(t0 + sweep * k / 40), cy + rad * math.sin(t0 + sweep * k / 40)) for k in range(41)]
    outer = arc(mx, my, R, i1, i2, (-ux, -uy))          # the lit rim, away from the dark disc
    inner = arc(ox, oy, r2, i2, i1, (-ux, -uy))         # the terminator, the dark disc's edge facing the light
    ring = outer + inner[1:-1]   # written at 0.1 precision (whole units facet a 30-unit disc)
    body.append('<path fill="#f6eedd" d="M' + " ".join(f"{x:.1f} {y:.1f}" for x, y in ring[:1]) + "L"
                + " ".join(f"{x:.1f} {y:.1f}" for x, y in ring[1:]) + 'z"/>')

    # long night clouds, lit pink from below by the city
    specs = [(420, 190, 820, 16), (1180, 120, 900, 12), (1560, 300, 760, 18), (760, 360, 640, 10),
             (250, 470, 560, 12), (1250, 470, 600, 9), (1720, 560, 520, 10), (560, 590, 420, 7)]
    specs = specs[: max(4, round(len(specs) * (1 if DETAIL["extras"] else 0.5)))]
    clouds = [cloud(rng, cx, cy, ln, th, bumps=rng.randint(3, 7)) for cx, cy, ln, th in specs]
    if DETAIL["wide"]:   # the long night clouds carry on past both edges (their own random draws)
        ext = random.Random(912)
        side = [(-215, 300, 290, 12), (2135, 210, 300, 13)]   # wholly outside 0..1920 (blur included): the laptop view is untouched
        clouds += [cloud(ext, cx, cy, ln, th, bumps=ext.randint(3, 7)) for cx, cy, ln, th in side]
        specs = specs + side
    soft = DETAIL["extras"]
    if soft:
        defs.append('<filter id="ns-soft" x="-10%" y="-60%" width="120%" height="220%"><feGaussianBlur stdDeviation="4"/></filter>'
                    '<filter id="ns-softer" x="-10%" y="-60%" width="120%" height="220%"><feGaussianBlur stdDeviation="16"/></filter>')
        volume = [cloud(random.Random(i), cx, cy + th * 0.6, ln * 0.9, th * 2.6, bumps=3) for i, (cx, cy, ln, th) in enumerate(specs)]
        body.append(f'<path fill="#2c2354" opacity=".55" filter="url(#ns-softer)" d="{polys(volume)}"/>')
    flt = ' filter="url(#ns-soft)"' if soft else ""
    body.append(f'<path fill="#33295c" opacity=".8"{flt} d="{polys(clouds)}"/>')
    body.append(f'<path fill="#93598f" opacity=".35"{flt} d="{polys([[(x + 6, y + 4) for x, y in c] for c in clouds])}"/>')


# ------------------------------------------------------------------ city

def window_patterns(defs, rng):
    """Window grids as patterns (cheap): sparse warm, sparse mixed, a dense lit office grid."""
    def tile(pid, w, h, cells, colours, offset):
        """A tile, plus a twin with smaller lights for towers behind the text column (at 2560 pt a
        full-size window fills a glyph-sized box; a smaller one at the same brightness doesn't)."""
        cells_at = []
        for _ in range(cells if DETAIL["extras"] else max(3, cells * 2 // 3)):
            cells_at.append((rng.randrange(0, w // 9) * 9 + 3, rng.randrange(0, h // 13) * 13 + 4, rng.choice(colours)))
        out = []
        for suffix, ww, hh, dx, dy in (("", 3.4, 5, 0, 0), ("s", 2.2, 3.4, 0.6, 0.8)):
            if suffix and not DETAIL["extras"]:
                continue
            rects = "".join(f'<rect x="{cx + dx:g}" y="{cy + dy:g}" width="{ww}" height="{hh}" fill="{c}"/>' for cx, cy, c in cells_at)
            out.append(f'<pattern id="{pid}{suffix}" width="{w}" height="{h}" patternUnits="userSpaceOnUse" '
                       f'patternTransform="translate({offset[0]} {offset[1]})">{rects}</pattern>')
        return "".join(out)
    warm, mixed = ["#ffd9a0", "#ffcf8a", "#ffe8c2"], ["#ffd9a0", "#eef3ff", "#a8f0e6", "#ffcf8a"]
    defs.append(tile("ns-w1", 54, 78, 9, warm, (2, 3)))
    defs.append(tile("ns-w2", 63, 91, 8, mixed, (5, 1)))
    defs.append(tile("ns-w3", 45, 65, 14, warm + ["#eef3ff"], (1, 6)))
    rows = "".join(f'<rect x="3" y="{y}" width="3.4" height="5" fill="#ffe2b0"/>' for y in (4, 17))
    defs.append(f'<pattern id="ns-w4" width="9" height="26" patternUnits="userSpaceOnUse">{rows}</pattern>')


def deco_crown(x, w, h, ground):
    top = ground - h
    pts = [(x, ground), (x, top + 70)]
    y = top + 70
    for inset, rise in ((0.1, 30), (0.22, 24), (0.34, 18)):
        pts += [(x + w * inset, y), (x + w * inset, y - rise)]
        y -= rise
    mid = x + w / 2
    pts += [(mid - 3, y), (mid - 3, y - 60), (mid + 3, y - 60), (mid + 3, y)]
    right, y2 = [], top + 70
    for inset, rise in ((0.1, 30), (0.22, 24), (0.34, 18)):
        right += [(x + w * (1 - inset), y2), (x + w * (1 - inset), y2 - rise)]
        y2 -= rise
    pts += right[::-1] + [(x + w, top + 70), (x + w, ground)]
    return pts, pts[1:-1]


def city(motion, defs, body, rng):
    window_patterns(defs, rng)
    ground = HORIZON + 2

    def height_at(x):
        right = math.exp(-((x - 1720) / 230) ** 2)
        left = 0.8 * math.exp(-((x - 190) / 190) ** 2)
        return 0.32 + 0.68 * max(right, left)

    layers = [("#3a2e62", 420, 0, 30, 70, None), ("#261e4a", 460, 0, 34, 80, ["ns-w2", "ns-w1", None]),
              ("#16122e", 330, 0, 40, 92, ["ns-w1", "ns-w3", "ns-w2", None])]
    front, front_ext = [], []
    ext = random.Random(913)   # the side strips' own towers (the original draws stay as they were)

    def towers(r, x, x_end, fill, hmax, wmin, wmax, pats, shapes, by_pat, fronts):
        while x < x_end:
            w = r.uniform(wmin, wmax)
            h = (50 + hmax * height_at(x) * r.uniform(0.45, 1.0))
            pts = tower_shape(r, x, w, h, ground, r.choice(["setback", "flat", "flat", "spire", "slant", "round", "setback"]))
            shapes.append(pts)
            if pats:
                pat = r.choice(pats)
                if pat and (DETAIL["windows"] >= 1 or r.random() < DETAIL["windows"]):
                    # columns of windows inside the walls only (a little in from each side and the top)
                    inner = [(px if px not in (x, x + w) else (px + 4 if px == x else px - 4), py) for px, py in pts]
                    by_pat.setdefault((pat, inside(x + w / 2)), []).append(inner)
            if fill == "#16122e":
                fronts.append(pts)
            x += w + r.uniform(-w * 0.25, w * 0.1)

    for fill, hmax, _, wmin, wmax, pats in layers:
        shapes, by_pat = [], {}
        towers(rng, -20 + rng.uniform(0, 20), W + 20, fill, hmax, wmin, wmax, pats, shapes, by_pat, front)
        for lo, hi in ext_ranges():   # the city carries on past both edges, lower away from the landmarks
            start = lo - 30 if lo < 0 else hi - (hi - lo) + 10
            towers(ext, start, (-25 if lo < 0 else hi + 20), fill, hmax, wmin, wmax, pats, shapes, by_pat, front_ext)
        body.append(f'<path fill="{fill}" d="{polys(shapes)}"/>')
        for (pat, dim), group in by_pat.items():
            # towers behind the text column keep their windows, dimmer (at 2560 pt one window fills a glyph's box)
            op = (0.55 if fill != "#16122e" else 0.85) * (0.75 if dim else 1)
            pid = pat + ("s" if dim and DETAIL["extras"] else "")
            body.append(f'<path fill="url(#{pid})" opacity="{op:.2f}" d="{polys(group)}"/>')

    # landmarks: a deco tower with a magenta crown and a cyan-banded block on the right, a tower with a
    # magenta light strip and a beacon spire on the left
    r1, crown1 = deco_crown(1716, 66, 480, ground)
    r2 = [(1812, ground), (1812, ground - 410), (1904, ground - 410), (1904, ground)]
    l1 = [(132, ground), (132, ground - 430), (150, ground - 452), (196, ground - 452), (214, ground - 430), (214, ground)]
    l2 = [(30, ground), (30, ground - 300), (52, ground - 330), (60, ground - 400), (68, ground - 330), (90, ground - 300), (90, ground)]
    r3 = [(1606, ground), (1606, ground - 340), (1626, ground - 372), (1632, ground - 430), (1638, ground - 372), (1658, ground - 340), (1658, ground)]
    body.append(f'<path fill="#130f29" d="{polys([r1, r2, l1, l2, r3])}"/>')
    body.append(f'<path fill="url(#ns-w4)" opacity=".8" d="{polys([[(1820, ground - 6), (1820, ground - 396), (1896, ground - 396), (1896, ground - 6)]])}"/>')
    body.append(f'<path fill="url(#ns-w3)" opacity=".85" d="{polys([[(1722, ground - 6), (1722, ground - 400), (1776, ground - 400), (1776, ground - 6)], [(138, ground - 6), (138, ground - 420), (208, ground - 420), (208, ground - 6)]])}"/>')

    kf = motion.keyframes("nsneon", [(0, "opacity:1"), (0.52, "opacity:.3"), (0.5417, "opacity:1"), (0.5625, "opacity:.4"),
                                     (0.5833, "opacity:1"), (0.86, "opacity:.65"), (0.875, "opacity:1"), (1, "opacity:1")])
    neon = [
        ("#ff4fb8", "#ffc4ec", poly(crown1, closed=False), 6, 0),
        ("#47e3ff", "#d2f8ff", f"M1812 {ground - 410}h92M1812 {ground - 396}h92M1812 {ground - 410}V{ground - 300}M1904 {ground - 410}V{ground - 300}", 6, -2.75),
        ("#ff4fb8", "#ffc4ec", f"M173 {ground - 440}V{ground - 40}M150 {ground - 452}h46", 8, -1.25),
    ]
    for glow, core, d, secs, delay in neon:
        body.append(f'<g class="{motion.use(kf, secs, delay)}" fill="none" stroke-linecap="round">'
                    f'<path stroke="{glow}" stroke-width="13" opacity=".24" d="{d}"/>'
                    f'<path stroke="{core}" stroke-width="3.2" d="{d}"/></g>')
    kb = motion.keyframes("nsbeacon", [(0, "opacity:1"), (0.25, "opacity:.08"), (1, "opacity:.08")])
    beacons = [(60, ground - 404), (1632, ground - 434), (1749, ground - 552)]
    body.append(f'<g class="{motion.use(kb, 2)}">' + "".join(
        f'<circle cx="{x}" cy="{y}" r="9" fill="#ff3b5c" opacity=".25"/><circle cx="{x}" cy="{y}" r="3.2" fill="{"#ff7a90" if not inside(x) else "#c4506a"}"/>'
        for x, y in beacons) + "</g>")

    # windows that switch on and off: single windows in the front towers' walls
    if DETAIL["extras"]:
        kw = motion.keyframes("nswin", [(0, "opacity:.95"), (0.35, "opacity:0"), (0.6, "opacity:.95"), (1, "opacity:.95")])
        groups = [[], [], [], []]
        for pts in front:
            xs = [p[0] for p in pts]
            x0, x1 = min(xs) + 6, max(xs) - 8
            top = min(p[1] for p in pts) + 16
            for _ in range(int((x1 - x0) * (ground - top) / 2600)):
                wx = round(rng.uniform(x0, x1) / 9) * 9
                wy = round(rng.uniform(top, ground - 10) / 13) * 13
                groups[rng.randrange(4)].append((wx, wy))
        for pts in front_ext:
            xs = [p[0] for p in pts]
            x0, x1 = min(xs) + 6, max(xs) - 8
            top = min(p[1] for p in pts) + 16
            for _ in range(int((x1 - x0) * (ground - top) / 3600)):   # the outer city: a little sparser
                wx = round(ext.uniform(x0, x1) / 9) * 9
                wy = round(ext.uniform(top, ground - 10) / 13) * 13
                groups[ext.randrange(4)].append((wx, wy))
        for i, g in enumerate(groups):
            outside = "".join(f"M{x} {y}v5" for x, y in g if not inside(x))
            within = "".join(f"M{x} {y + 1}v3" for x, y in g if inside(x))
            body.append(f'<g class="{motion.use(kw, 10, -2.5 * i)}" stroke-width="3.4">'
                        f'<path stroke="#ffe6b8" d="{outside}"/><path stroke="#a08870" stroke-width="2.2" d="{within}"/></g>')
    return front


# ------------------------------------------------------------------ bay

def bay(motion, defs, body, rng, front):
    defs.append(vgrad("ns-sea", [(0, "#3b2a5d", 1), (0.2, "#251c44", 1), (1, "#0e0b1e", 1)], HORIZON, 1100))
    defs.append(rgrad("ns-sea-glow", 1700, HORIZON, 700, [(0, "#b8609a", 0.35), (1, "#b8609a", 0)], sy=0.45))
    x0, sw = span()
    body.append(f'<rect x="{x0}" y="{HORIZON}" width="{sw}" height="{H - HORIZON}" fill="url(#ns-sea)"/>')
    body.append(f'<rect x="{x0}" y="{HORIZON}" width="{sw}" height="{H - HORIZON}" fill="url(#ns-sea-glow)"/>')

    # long broken reflections under the city: warm windows, the neon colours under the landmarks
    sources = [(1749, "#ff79c8", 70), (1858, "#6fe8ff", 90), (173, "#ff79c8", 60)]
    for _ in range(round(46 * DETAIL["reflections"])):
        sources.append((rng.uniform(-10, W + 10), rng.choice(["#ffcf8f", "#ffdca8", "#f0d2ff"]), rng.uniform(16, 60)))
    sets = [dict(), dict(), dict()]
    steady = dict()
    for sx, colour, width in sources:
        for k in range(int(26 * DETAIL["reflections"]) + 4):
            y = HORIZON + 6 + k * rng.uniform(5, 9)
            if y > 1040:
                break
            ln = width * rng.uniform(0.25, 1.0) * (1 - (y - HORIZON) / 520)
            x = sx + rng.gauss(0, width * 0.25)
            seg = f"M{round(x - ln / 2)} {round(y)}h{max(2, round(ln))}"
            dim = inside(x)
            target = steady if (rng.random() < 0.45 or not DETAIL["extras"]) else sets[rng.randrange(3)]
            if dim and abs(y - (HORIZON + 40)) < BOAT_LANE and DETAIL["extras"]:
                continue   # the speedboat's lane behind the text (after the draws, so no other streak moves)
            target.setdefault((colour, dim), []).append(seg)
    ext = random.Random(914)   # reflections under the side strips' towers, from their own draws
    for lo, hi in ext_ranges():
        for _ in range(round(0.34 * 46 * DETAIL["reflections"] * (hi - lo) / W)):   # a lower, sparser outer city
            sx, colour, width = ext.uniform(lo, hi), ext.choice(["#ffcf8f", "#ffdca8", "#f0d2ff"]), ext.uniform(16, 60)
            for k in range(int(26 * DETAIL["reflections"]) + 4):
                y = HORIZON + 6 + k * ext.uniform(5, 9)
                if y > 1040:
                    break
                ln = width * ext.uniform(0.25, 1.0) * (1 - (y - HORIZON) / 520)
                x = sx + ext.gauss(0, width * 0.25)
                target = steady if ext.random() < 0.45 else sets[ext.randrange(3)]
                target.setdefault((colour, False), []).append(f"M{round(x - ln / 2)} {round(y)}h{max(2, round(ln))}")

    screen = DETAIL["extras"] and DETAIL["wide"]
    def rel(segs):
        """'M{x} {y}h{l}' segments as one path: sorted by row, each move relative to the last end when shorter."""
        parsed = sorted((int(y), int(x), int(l)) for x, y, l in (re.match(r"M(-?\d+) (-?\d+)h(\d+)", s).groups() for s in segs))
        out, cx, cy = [], None, None
        for y, x, l in parsed:
            a = f"M{x} {y}h{l}"
            if cx is not None:
                dx, dy = x - cx, y - cy
                r = f"m{dx}{'' if dy < 0 else ' '}{dy}h{l}"
                a = r if len(r) < len(a) else a
            out.append(a)
            cx, cy = x + l, y
        return "".join(out)
    edges = (BAND[0] - 30, BAND[1] + 20)   # inside()'s bounds: where the "rf" mask steps
    def crosses(seg):
        x, _, l = (int(v) for v in re.match(r"M(-?\d+) (-?\d+)h(\d+)", seg).groups())
        return any(x < e < x + l for e in edges)
    def boundary(groups):
        """Streaks across the mask's step, plus any same-path streak they overlap (painted once in one path
        before; split across layers their overlap would be painted twice), grown until nothing more touches."""
        def ext(seg):
            x, y, l = (int(v) for v in re.match(r"M(-?\d+) (-?\d+)h(\d+)", seg).groups())
            return x, y, l
        out = set()
        for (c, dim), segs in groups.items():
            out |= {((c, dim), g) for g in segs if crosses(g)}
        grew = True
        while grew:
            grew = False
            for (c, dim), segs in groups.items():
                for g in segs:
                    if ((c, dim), g) in out:
                        continue
                    x, y, l = ext(g)
                    for (k2, h) in list(out):
                        if k2[0] != c:
                            continue
                        x2, y2, l2 = ext(h)
                        if abs(y - y2) < 2.6 and x < x2 + l2 and x2 < x + l:
                            out.add(((c, dim), g)); grew = True
                            break
        return out
    def paths(groups, straddle=False):
        if screen:   # one bright path per colour; the "rf" mask dims the ones behind the column
            edge = boundary(groups)
            if straddle:   # boundary streaks keep their own whole-streak look, unmasked (exact)
                return "".join(f'<path stroke="{c}" stroke-width="2.6" opacity="{".14" if dim else ".55"}" d="{rel(s)}"/>'
                               for (c, dim), segs in groups.items() if (s := [g for g in segs if ((c, dim), g) in edge]))
            merged = {}
            for (c, dim), segs in groups.items():
                merged.setdefault(c, []).extend(g for g in segs if ((c, dim), g) not in edge)
            return "".join(f'<path stroke="{c}" stroke-width="2.6" opacity=".55" d="{rel(segs)}"/>' for c, segs in merged.items() if segs)
        return "".join(f'<path stroke="{c}" stroke-width="2.6" opacity="{".14" if dim else ".55"}" d="{"".join(segs)}"/>'
                       for (c, dim), segs in groups.items())
    refl = paths(steady)
    across = paths(steady, True) if screen else ""
    if DETAIL["extras"]:
        kr = motion.keyframes("nsrip", [(0, "opacity:1"), (0.25, "opacity:.25"), (0.5, "opacity:0"), (0.75, "opacity:.4"), (1, "opacity:1")])
        for i, g in enumerate(sets):
            refl += f'<g class="{motion.use(kr, 1.5, -0.5 * i)}">{paths(g)}</g>'
            a = paths(g, True) if screen else ""
            across += f'<g class="{motion.use(kr, 1.5, -0.5 * i)}">{a}</g>' if a else ""
    if screen:
        body.append(refl + across)
    else:
        body.append(refl)


BOAT_SCALE = 1.4   # any smaller and the boat is hard to spot
BOAT_LANE = 14     # dim reflection streaks within this many units of the boat's waterline are left out behind the column


def yacht(motion, defs, body):
    """A long, low white superyacht, swept and raked, with dark tinted window bands,
    a hot-pink trim line, a cyan underwater glow, and its white hull broken up in the water below."""
    x, y = 140, 800            # bow tip x, waterline y
    L = 196
    defs.append(rgrad("ns-yacht-glow", x + 104, y + 5, 132, [(0, "#47d6ff", 0.34), (0.5, "#47d6ff", 0.1), (1, "#47d6ff", 0)], sy=0.2))
    defs.append(vgrad("ns-yacht-hull", [(0, "#e6e0f6", 1), (1, "#8f86b8", 1)], y - 22, y))
    defs.append(vgrad("ns-yacht-house", [(0, "#f2eefb", 1), (1, "#b4abd6", 1)], y - 40, y - 14))
    if DETAIL["extras"]:
        body.append(f'<ellipse cx="{x + 104}" cy="{y + 5}" rx="132" ry="26" fill="url(#ns-yacht-glow)"/>')
    # reflections: the white hull and the pink trim, broken into two shimmer poses
    poses = [[(x + 60, 40, "#d9d2ee", .35), (x + 120, 52, "#d9d2ee", .3), (x + 96, 26, "#ff5fb8", .45), (x + 150, 18, "#ffd9a0", .35)],
             [(x + 70, 46, "#d9d2ee", .3), (x + 130, 40, "#d9d2ee", .35), (x + 88, 22, "#ff5fb8", .4), (x + 160, 14, "#ffd9a0", .3)]]
    k_a = motion.keyframes("nsyra", [(0, "opacity:1"), (0.5, "opacity:0"), (1, "opacity:1")])
    k_b = motion.keyframes("nsyrb", [(0, "opacity:0"), (0.5, "opacity:1"), (1, "opacity:0")])
    for pose, key in zip(poses if DETAIL["extras"] else [], (k_a, k_b)):
        d = "".join(f'<path stroke="{c}" stroke-width="2" opacity="{o}" d="M{sx - w / 2} {y + 5 + 4 * k}h{w}"/>'
                    for k, (sx, w, c, o) in enumerate(pose))
        body.append(f'<g class="{motion.use(key, 1.5)}" opacity="{motion.hidden(key == k_a)}">{d}</g>')
    # hull: a sharp, raised bow sweeping back to a low transom; the hull's own dark window slit
    hull = [(x, y - 21), (x + 18, y - 13), (x + 40, y - 2), (x + 48, y + 1), (x + L - 4, y + 1), (x + L, y - 5), (x + L, y - 13),
            (x + 60, y - 15)]
    body.append(f'<path fill="url(#ns-yacht-hull)" d="{poly(hull)}"/>')
    body.append(f'<path fill="#1a1430" d="M{x + 70} {y - 9}L{x + L - 22} {y - 9}L{x + L - 24} {y - 6}L{x + 74} {y - 6}z"/>')
    body.append(f'<path stroke="#ff5fb8" stroke-width="1.6" d="M{x + 30} {y - 15.5}L{x + L - 2} {y - 13.5}"/>')   # neon trim
    # superstructure: main deck and upper deck, both with raked fronts; a hardtop with a radome
    main = [(x + 58, y - 15), (x + 84, y - 27), (x + 176, y - 27), (x + 186, y - 15)]
    upper = [(x + 92, y - 27), (x + 112, y - 36), (x + 164, y - 36), (x + 170, y - 27)]
    top = [(x + 122, y - 36), (x + 134, y - 41), (x + 160, y - 41), (x + 162, y - 36)]
    body.append(f'<path fill="url(#ns-yacht-house)" d="{polys([main, upper, top])}"/>')
    # tinted glass bands, raked with the fronts; a few warm-lit panes behind the tint
    glass = [[(x + 72, y - 18), (x + 86, y - 24), (x + 170, y - 24), (x + 172, y - 18)],
             [(x + 106, y - 29), (x + 116, y - 34), (x + 158, y - 34), (x + 160, y - 29)]]
    body.append(f'<path fill="#1a1430" d="{polys(glass)}"/>')
    lit = f"M{x + 100} {y - 23}h14v4h-14zM{x + 132} {y - 23}h18v4h-18zM{x + 126} {y - 33}h12v3h-12z"
    body.append(f'<path fill="#ffd9a0" opacity=".85" d="{lit}"/>')
    body.append(f'<circle cx="{x + 148}" cy="{y - 44}" r="3" fill="#e6e0f6"/><path stroke="#b4abd6" stroke-width="1.4" d="M{x + 140} {y - 41}v-8"/>')
    # anchor light: white, a soft blink
    kn = motion.keyframes("nsymast", [(0, "opacity:1"), (0.5, "opacity:.25"), (1, "opacity:1")])
    body.append(f'<circle class="{motion.use(kn, 3)}" cx="{x + 140}" cy="{y - 50}" r="1.8" fill="#fff4dc"/>')


def speedboat(motion, defs, body):
    """A go-fast boat out by the far shore, racing left to right with a white wake, one crossing every ~34 s.

    The app animates only opacity and stroke-dashoffset, so the boat moves the way the bridge traffic does:
    it is a stack of thin horizontal strokes, one dash each, all on lines spanning the bay and all shifted
    by the same dashoffset. A leading gap in each dash pattern places that stroke within the boat (the raked
    bow, the cockpit, the racing stripe, the wake). Small and far, so the striped build doesn't show."""
    if not DETAIL["extras"]:
        # the card: the boat standing still in the right margin, plain strokes
        bx, y = 1600, HORIZON + 40
        for start, length, dy, colour, width, opacity in ((-80, 80, 1.8, "#eeeaff", 2.0, .55), (-22, 22, -1.2, "#ffffff", 2.0, .7),
                                                           (6, 44, 0, "#8f86b8", 2.0, 1), (4, 50, -2, "#d9d2ee", 2.0, 1),
                                                           (5, 54, -4, "#f2eefb", 2.0, 1), (12, 30, -3, "#ff5fb8", 1.2, 1),
                                                           (20, 16, -6, "#1a1430", 2.0, 1)):
            body.append(f'<path stroke="{colour}" stroke-width="{width}" opacity="{opacity}" d="M{bx + start} {y + dy:g}h{length}"/>')
        return
    y = HORIZON + 40            # waterline: out in the bay, behind the yacht (it passes behind its superstructure)
    x0, x1 = (-PAD - 116, W + PAD + 116) if DETAIL["wide"] else (-120, 2080)   # each line runs past both edges; its length is the pattern's period
    period = x1 - x0
    step = 8                    # units per beat: 64 units/s, about a car's pace on the bridge
    beats = period // step
    key = motion.keyframes("nsboat", [(k / beats, f"stroke-dashoffset:{-step * k}") for k in range(beats + 1)])
    seconds = beats * BEAT
    # (start within the boat, length, dy, colour, width, opacity); the boat faces right, x grows toward the bow.
    # Stacked 2-unit strokes read as one solid shape; the white plume and bow wave set it apart from the
    # thin reflection streaks around it.
    parts = [
        (-56, 140, 0.4, "#07061a", 17, .26),     # the dark water the hull pushes aside, in two soft layers so its edge
        (-40, 122, 0.4, "#07061a", 9, .34),      # fades out: separates the boat from the streaks; it ends at the bow
        (-150, 120, 3.6, "#d9d2ee", 1.4, .25),  # long wake, fading behind
        (-80, 80, 1.8, "#eeeaff", 2.0, .55),    # near wake
        (-22, 22, -1.2, "#ffffff", 2.0, .7),    # spray plume off the transom (a rooster tail, lower and lower)
        (-14, 14, -3.2, "#ffffff", 2.0, .55),
        (-8, 8, -5.2, "#ffffff", 2.0, .35),
        (50, 10, 0.6, "#ffffff", 2.0, .7),      # bow wave
        (8, 44, 5.2, "#e6e0f6", 1.8, .22),      # its reflection
        (6, 44, 0.0, "#8f86b8", 2.0, 1),       # hull bottom
        (4, 50, -2.0, "#d9d2ee", 2.0, 1),       # hull side
        (5, 54, -4.0, "#f2eefb", 2.0, 1),       # sheer, flaring out to the bow
        (12, 30, -3.0, "#ff5fb8", 1.2, 1),      # racing stripe
        (20, 16, -6.0, "#1a1430", 2.0, 1),      # cockpit
        (32, 5, -6.6, "#9ff0ff", 1.4, .85),     # windshield glint
        (22, 10, -8.0, "#1a1430", 1.4, 1),      # a head above the cockpit rim
    ]
    strokes = []
    for start, length, dy, colour, width, opacity in parts:
        if colour != "#07061a":   # the shadow keeps its own size; the boat grows
            start, length, dy, width = start * BOAT_SCALE, length * BOAT_SCALE, dy * BOAT_SCALE, width * BOAT_SCALE
        start, length, dy, width = round(start), round(length), round(dy, 1), round(width, 1)
        gap = start + 260       # the boat starts out of view, left of the bay
        if colour == "#07061a":
            # round caps: a pattern that opens with a 0-length dash draws a round dot there (the "black circle
            # following the boat"). Same dash, one period earlier on a longer line instead.
            dash, sx, cap = f"{length} {period - length}", x0 + gap - period, ' stroke-linecap="round"'
        else:
            dash, sx, cap = f"0 {gap} {length} {period - gap - length}", x0, ""
        strokes.append(f'<path stroke="{colour}" stroke-width="{width:g}"{cap} '
                       f'opacity="{opacity}" stroke-dasharray="{dash}" d="M{sx} {y + dy:g}H{x1}"/>')
    # one animated group: stroke-dashoffset inherits, so every stroke slides with it exactly as when each had the class
    body.append(f'<g class="{motion.use(key, seconds)}" fill="none">{"".join(strokes)}</g>')


def bridge(motion, defs, body):
    """A long bridge across the bay, lamps on posts, and two streams of traffic flowing on the beat."""
    yl, yr = 862, 826
    def y_at(x):
        return yl + (yr - yl) * x / W
    l, r = (XL - 20, XR + 20) if DETAIL["wide"] else (-20, W + 20)

    def along(xa, ya, xb, yb):
        """The laptop's line from (xa, ya) to (xb, yb), carried on to x = l and x = r on the same slope."""
        s = (yb - ya) / (xb - xa)
        return (l, ya + (l - xa) * s, r, yb + (r - xb) * s) if DETAIL["wide"] else (xa, ya, xb, yb)

    def num(v):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    top = [round(v) for v in (y_at(-20) - 4, y_at(W + 20) - 4)]
    bot = [round(v) for v in (y_at(-20) + 10, y_at(W + 20) + 10)]
    xa, ya, xb, yb = along(-20, top[0], W + 20, top[1])
    # the laptop's deck exactly as before (poly() of the same four corners); side pieces carry it on in the wide picture
    deck_d = poly([(-20, y_at(-20) - 4), (W + 20, y_at(W + 20) - 4), (W + 20, y_at(W + 20) + 10), (-20, y_at(-20) + 10)])
    deck_side = ""
    if DETAIL["wide"]:
        s_top = (top[1] - top[0]) / (W + 40)
        s_bot = (bot[1] - bot[0]) / (W + 40)
        for a, b in ((xa, -20), (W + 20, xb)):
            ya_, yb_ = top[0] + (a + 20) * s_top, top[0] + (b + 20) * s_top
            ya2_, yb2_ = bot[0] + (a + 20) * s_bot, bot[0] + (b + 20) * s_bot
            deck_side += f"M{num(a)} {num(ya_)}L{num(b)} {num(yb_)}L{num(b)} {num(yb2_)}L{num(a)} {num(ya2_)}z"
    step = 64 if DETAIL["extras"] else 128
    pier_step = 120 if DETAIL["extras"] else 240
    pier_xs = list(range(30, W, pier_step))
    if DETAIL["wide"]:   # the same spacing carried on past both edges
        pier_xs = [x for x in range(30 - pier_step * 3, XR, pier_step) if x < 30 or x >= W] + pier_xs
    piers = [[(x, y_at(x) + 10), (x, 1070), (x + 10, 1070), (x + 10, y_at(x) + 10)] for x in pier_xs]
    body.append(f'<path fill="#0d0a1d" d="{polys(piers)}"/><path fill="#140f28" d="{deck_d}"/>')
    if deck_side:   # separate elements: the laptop's deck and rail rasterise exactly as before
        body.append(f'<path fill="#140f28" d="{deck_side}"/>')
    rail = f"M-20 {round(y_at(-20) - 4)}L{W + 20} {round(y_at(W + 20) - 4)}"   # the laptop's rail, exactly as before
    body.append(f'<path stroke="#5a4a8a" stroke-width="2" d="{rail}"/>')
    if DETAIL["wide"]:
        s_top = (top[1] - top[0]) / (W + 40)
        rail = "".join(f"M{num(a)} {num(top[0] + (a + 20) * s_top)}L{num(b)} {num(top[0] + (b + 20) * s_top)}"
                        for a, b in ((xa, -20), (W + 20, xb)))
        body.append(f'<path stroke="#5a4a8a" stroke-width="2" d="{rail}"/>')
    lamp_xs = list(range(10, W, step))
    if DETAIL["wide"]:
        lamp_xs = [x for x in range(10 - step * 6, XR, step) if x < 10 or x >= W] + lamp_xs
    lamps_out, lamps_in = [], []
    for x in lamp_xs:
        (lamps_in if inside(x) else lamps_out).append(f"M{x} {round(y_at(x) - 4)}v-22")
    body.append(f'<path stroke="#0d0a1d" stroke-width="2" d="{"".join(lamps_out + lamps_in)}"/>')
    glows = "".join(f'<circle cx="{x}" cy="{round(y_at(x) - 27)}" r="{6 if inside(x) else 9}"/>' for x in lamp_xs) if DETAIL["extras"] else ""
    cores = "".join(f'<circle cx="{x}" cy="{round(y_at(x) - 27)}" r="{1.8 if inside(x) else 2.6}" opacity="{".2" if inside(x) else "1"}"/>' for x in lamp_xs)
    body.append(f'<g fill="#ffc77e" opacity=".25">{glows}</g><g fill="#ffe2b0">{cores}</g>')

    # traffic: the same flow in three spans; bright where the margins are, dim behind the column
    k_out = dash_flow(motion, "nsto", 120, 12, -1)
    k_in = dash_flow(motion, "nsti", 120, 12, 1)
    a, b = BAND[0] - 30, BAND[1] - 10
    ramp = [(0, 1), (a - 140, 1), (a - 70, 0.6), (a, 0.32), (a + 30, 0.26), (b - 30, 0.26), (b, 0.32), (b + 70, 0.6), (b + 140, 1), (W, 1)]
    screen = DETAIL["extras"] and DETAIL["wide"]
    if not screen:   # the card fades the lanes behind the column; the scene draws them in plain colours
        for gid, colour in (("ns-tail", "#ff4766"), ("ns-head", "#fff1d4")):
            defs.append(f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{W}" y2="0">'
                        + "".join(f'<stop offset="{max(0, x) / W:.3f}" stop-color="{colour}" stop-opacity="{k}"/>' for x, k in ramp) + '</linearGradient>')
    lanes = []
    for dy, gid, key, dash, width in ((-8, "ns-tail", k_out, "10 6 10 94", 4), (-2, "ns-head", k_in, "8 5 8 99", 4.4)):
        # the laptop's lane exactly as before; in the wide picture two more pieces on the same line: one exactly three
        # dash periods long ending where it starts (its dashes run straight on into it), and one from its end with
        # the pattern begun at the phase the laptop's lane ends on (a continuous stream)
        x0_, y0_, x1_, y1_ = -20, round(y_at(-20) + dy), W + 20, round(y_at(W + 20) + dy)
        paint = {"ns-tail": "#ff4766", "ns-head": "#fff1d4"}[gid] if screen else f"url(#{gid})"
        lanes.append(f'<g class="{motion.use(key, 1.5)}" fill="none" stroke="{paint}" stroke-width="{width}" stroke-linecap="round">')
        attrs = ""
        lanes.append(f'<path{attrs} stroke-dasharray="{dash}" d="M{x0_} {y0_}L{x1_} {y1_}"/>')
        if DETAIL["wide"]:
            ln = math.hypot(x1_ - x0_, y1_ - y0_)
            ux, uy = (x1_ - x0_) / ln, (y1_ - y0_) / ln
            lanes.append(f'<path{attrs} stroke-dasharray="{dash}" d="M{x0_ - 360 * ux:.3f} {y0_ - 360 * uy:.3f}L{x0_} {y0_}"/>')
            run = (r - x1_) / ux
            lanes.append(f'<path{attrs} stroke-dasharray="{rotate_dash(dash, ln % 120)}" '
                         f'd="M{x1_} {y1_}L{x1_ + run * ux:.3f} {y1_ + run * uy:.3f}"/>')
        lanes.append("</g>")
    body.append("".join(lanes))


def rotate_dash(dash, phase):
    """The dash pattern `dash` begun `phase` units in, written as a pattern that starts with a dash (0 if it
    starts in a gap); same period, so the animated offset moves it in step with the original."""
    parts = [float(v) for v in dash.split()]
    out, pos, first = [], 0.0, True
    seq = [(v, i % 2 == 0) for i, v in enumerate(parts)]
    # walk once round the pattern from `phase`
    for k in range(2 * len(seq)):
        length, is_dash = seq[k % len(seq)]
        lo, hi = pos, pos + length
        pos = hi
        if hi <= phase or lo >= phase + sum(parts):
            continue
        a, b = max(lo, phase), min(hi, phase + sum(parts))
        if first and not is_dash:
            out.append(0.0)
        first = False
        if out and ((len(out) % 2 == 1) != (not is_dash)):
            out[-1] += b - a           # same kind as the last entry: merge
        else:
            out.append(b - a)
    if len(out) % 2:
        out.append(0.0)
    assert abs(sum(out) - sum(parts)) < 1e-6, (out, parts)
    return " ".join(f"{v:.3f}".rstrip("0").rstrip(".") for v in out)


# ------------------------------------------------------------------ the helicopter over the left margin

def skylights(motion, defs, body):
    """Two searchlights from behind the right-hand towers, swinging across the sky (four frames)."""
    defs.append(vgrad("ns-sky-beam", [(0, "#d8c8ff", 0), (0.55, "#e2d6ff", 0.16), (1, "#efe6ff", 0.38)], 0, HORIZON - 120))
    base = [(1760, HORIZON - 120), (1860, HORIZON - 140)]
    angles = [(-14, 8), (-8, 14), (-2, 20), (-8, 14)]   # degrees from vertical, per frame, per beam
    frames = [(0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1)]
    for i, (pair, (lo, hi)) in enumerate(zip(angles, frames)):
        cones = []
        for (bx, by), a in zip(base, pair):
            t = math.radians(a)
            tx, ty = bx + math.sin(t) * 900, by - math.cos(t) * 900
            nx, ny = math.cos(t) * 46, math.sin(t) * 46
            cones.append([(bx - 3, by), (tx - nx, ty - ny), (tx + nx, ty + ny), (bx + 3, by)])
        if DETAIL["extras"]:
            stops = [(0, f"opacity:{1 if lo == 0 else 0}")] + ([(lo, "opacity:1")] if lo > 0 else []) + ([(hi, "opacity:0")] if hi < 1 else []) + [(1, f"opacity:{1 if lo == 0 else 0}")]
            key = motion.keyframes(f"nssky{i}", stops)
            body.append(f'<path class="{motion.use(key, 8)}" fill="url(#ns-sky-beam)" opacity="{motion.hidden(i == 0)}" d="{polys(cones)}"/>')
        elif i == 1:
            body.append(f'<path fill="url(#ns-sky-beam)" d="{polys(cones)}"/>')


def helicopter(motion, defs, body):
    hx, hy = 236, 236
    defs.append(vgrad("ns-beam", [(0, "#fff3d6", 0.34), (1, "#fff3d6", 0)], hy, HORIZON))
    targets = [(40, 150), (110, 230), (180, 300), (110, 230)]   # foot of the cone, left and right edge
    cones = [[(hx - 4, hy + 8), (a, HORIZON - 6), (b, HORIZON - 6), (hx + 4, hy + 8)] for a, b in targets]
    if DETAIL["extras"]:
        frames = [(0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1)]
        for i, cone in enumerate(cones):
            lo, hi = frames[i]
            stops = [(0, f"opacity:{1 if lo == 0 else 0}")]
            if lo > 0:
                stops.append((lo, "opacity:1"))
            if hi < 1:
                stops.append((hi, "opacity:0"))
            stops.append((1, f"opacity:{1 if lo == 0 else 0}"))
            key = motion.keyframes(f"nsbeam{i}", stops)
            body.append(f'<path class="{motion.use(key, 6)}" fill="url(#ns-beam)" opacity="{motion.hidden(i == 0)}" d="{poly(cone)}"/>')
    else:
        body.append(f'<path fill="url(#ns-beam)" d="{poly(cones[1])}"/>')
    heli = (f"M{hx - 22} {hy + 2}q0-14 18-16h12q12 0 16 10l26-3 10-9h4l-3 13-37 5q-4 8-14 8h-20q-12 0-12-8z"   # cabin, boom, fin
            f"M{hx - 46} {hy - 16}h96v3h-96zM{hx} {hy - 14}h4v4h-4z"                                         # rotor and mast
            f"M{hx - 20} {hy + 14}h34v2h-34zM{hx - 14} {hy + 10}h2v4h-2zM{hx + 6} {hy + 10}h2v4h-2z"               # skids
            f"M{hx + 56} {hy - 18}h2v18h-2z")                                                                       # tail rotor blade
    body.append(f'<circle cx="{hx + 57}" cy="{hy - 9}" r="9" fill="#0b0818" opacity=".35"/>'                    # tail rotor disc (spinning)
                f'<path fill="#0b0818" d="{heli}"/>'
                f'<path fill="#2a2450" opacity=".8" d="M{hx - 16} {hy}q2-8 12-9h6v8z"/>')                          # canopy glint
    kn = motion.keyframes("nsnav", [(0, "opacity:1"), (0.125, "opacity:0"), (1, "opacity:0")])
    body.append(f'<circle class="{motion.use(kn, 1)}" cx="{hx + 62}" cy="{hy - 18}" r="3" fill="#ff5a6e"/>')


# ------------------------------------------------------------------ the rooftop

PALMS = {
    "L": (31, (75, 1040), 470, -24, 22, 320, 15, 19, "#4c2d5e", "#181230", True),
    "R": (32, (1840, 1040), 460, 20, 22, 310, 15, 19, "#4c2d5e", "#181230", True),
}
PALM_LOOK = dict(droop=1.1, blade_len=0.28, leaf_width=0.55, leaf_angle=42, leaf_droop=0.75, hanging=0)


def palms(motion, defs, body):
    k0 = motion.keyframes("nsp0", [(0, "opacity:1"), (0.25, "opacity:0"), (0.5, "opacity:1"), (0.75, "opacity:0"), (1, "opacity:1")])
    kp = motion.keyframes("nsp1", [(0, "opacity:0"), (0.25, "opacity:1"), (0.5, "opacity:0"), (1, "opacity:0")])
    km = motion.keyframes("nsp2", [(0, "opacity:0"), (0.75, "opacity:1"), (1, "opacity:0")])
    for name, (seed, base, h, lean, tw, fl, nf, bl, top_col, base_col, sway) in PALMS.items():
        nf, bl = max(8 if DETAIL["extras"] else 7, round(nf * DETAIL["fronds"])), max(6 if DETAIL["extras"] else 5, round(bl * DETAIL["blades"]))
        sway = sway and DETAIL["sway"]
        p = Palm(seed, base, h, lean, tw, fl, n_fronds=nf, blades=bl, **PALM_LOOK)
        fill = top_col
        lo, sw = span()
        on_screen = [i for i in range(len(p.frond_specs)) if lo - 60 < p.tip(i)[0] < lo + sw + 40]
        if not sway:
            body.append(f'<path fill="{fill}" d="{polys([p.trunk()] + p.crown(which=set(on_screen)), orient=True)}"/>')
            continue
        margin = (lambda x: x < BAND[0] + 110) if base[0] < W / 2 else (lambda x: x > BAND[1] - 110)
        # fronds that reach only into the wide picture's side strips stay still: drawn once instead of in three
        # sway poses (22K); the ones a laptop window shows sway exactly as before
        movers = [i for i in on_screen if margin(p.tip(i)[0]) and -60 < p.tip(i)[0] < W + 40]
        still = set(on_screen) - set(movers)
        # the fronds a laptop shows: exactly as before; the ones only the wide picture's side strips show: their
        # own path (same colour, so the stacking can't change)
        old_view = {i for i in still if -60 < p.tip(i)[0] < W + 40}
        body.append(f'<path fill="{fill}" d="{polys([p.trunk()] + p.crown(which=old_view), orient=True)}"/>')

        # every frond the wide picture reaches, so crowns are complete; the ones the laptop used to
        # leave out are drawn still, with half the leaflets on the same spines (a laptop shows only their bases)
        extra = still - old_view
        if extra:
            light = Palm(seed, base, h, lean, tw, fl, n_fronds=nf, blades=max(6, bl // 2), **PALM_LOOK)
            body.append(f'<path fill="{fill}" d="{polys(light.crown(which=extra, hub=False), orient=True)}"/>')
        for gi, ids in enumerate([set(movers[0::2]), set(movers[1::2])]):
            for pose, key in ((0.0, k0), (1.3, kp), (-1.3, km)):
                crown = p.crown(pose=pose * (1 if gi == 0 else -1), which=ids, hub=False)
                body.append(f'<path class="{motion.use(key, 3.5, -0.875 * gi)}" fill="{fill}" opacity="{motion.hidden(pose == 0.0)}" d="{polys(crown, orient=True)}"/>')


def rooftop(motion, defs, body):
    edge = EDGE
    # glass balustrade: a faint sheet, a top rail and posts
    x0, sw = span()
    body.append(f'<rect x="{x0}" y="1066" width="{sw}" height="{edge - 1066}" fill="#7f8ce0" opacity=".05"/>')
    post_xs = [x for x in range(60 - 180 * 2, x0 + sw, 180) if x >= x0] if DETAIL["wide"] else list(range(60, W, 180))
    posts = "".join(f"M{x} 1066V{edge}" for x in post_xs)
    body.append(f'<path stroke="#2c2550" stroke-width="3" d="M{x0} 1066H{x0 + sw}{posts}"/>')
    # planters
    # planters: clearly boxes standing in front of the railing (top well above the rail, a lit rim),
    # so their edges never meet the rail line in a near-miss step
    # (drawn in planters(), after the palms, so each trunk grows out of its box)
    # floor and the cyan strip along its edge: bright in the margins, dim behind the column
    body.append(f'<rect x="{x0}" y="{edge}" width="{sw}" height="{H - edge}" fill="#0a0817"/>')
    # one continuous strip whose brightness eases down behind the column (no hard cut)
    a, b = BAND[0] - 30, BAND[1] - 10
    if not DETAIL["extras"]:   # the card: one plain line
        body.append(f'<path stroke="#7fd8ee" stroke-width="3" opacity=".7" d="M0 {edge}H{W}"/>')
        return
    ease = [(0, 1), (0.25, 0.86), (0.5, 0.7), (0.75, 0.52), (1, 0.4)]
    st = [(0, 1)] + [(a - 160 + 160 * t, k) for t, k in ease] + [(b + 160 * (1 - t), k) for t, k in ease] + [(W, 1)]
    st = sorted(st)
    if DETAIL["wide"]:   # the scene: the strip at full brightness all along
        body.append(f'<path stroke="#47d6ff" stroke-width="16" opacity=".22" d="M{x0} {edge}H{x0 + sw}"/>'
                    f'<path stroke="#c8f6ff" stroke-width="3" d="M{x0} {edge}H{x0 + sw}"/>')
    else:
        defs.append('<linearGradient id="ns-strip" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="1920" y2="0">'
                    + "".join(f'<stop offset="{x / W:.3f}" stop-color="#c8f6ff" stop-opacity="{k:.2f}"/>' for x, k in st) + '</linearGradient>')
        defs.append('<linearGradient id="ns-strip-glow" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="1920" y2="0">'
                    + "".join(f'<stop offset="{x / W:.3f}" stop-color="#47d6ff" stop-opacity="{.22 * k:.3f}"/>' for x, k in st) + '</linearGradient>')
        body.append(f'<path stroke="url(#ns-strip-glow)" stroke-width="16" d="M{x0} {edge}H{x0 + sw}"/>'
                    f'<path stroke="url(#ns-strip)" stroke-width="3" d="M{x0} {edge}H{x0 + sw}"/>')
    # the strip's light on the floor
    defs.append(vgrad("ns-floor", [(0, "#47d6ff", 0.16), (1, "#47d6ff", 0)], edge, edge + 70))
    body.append(f'<rect x="{x0}" y="{edge}" width="{sw}" height="70" fill="url(#ns-floor)"/>')


def planters(body):
    top, edge = 1026, EDGE
    body.append(f'<path fill="#120e24" d="M-10 {top}h190v{edge - top}h-190zM1768 {top}h162v{edge - top}h-162z"/>')
    body.append(f'<path fill="#1a1533" d="M-10 {top}h190v10h-190zM1768 {top}h162v10h-162z"/>')
    body.append(f'<path stroke="#5a4c96" stroke-width="2" d="M-10 {top}h190M1768 {top}h162"/>')


def grain(defs, body, rng):
    light = "".join(f"M{rng.randrange(64)} {rng.randrange(64)}h1.4v1.4h-1.4z" for _ in range(24))
    dark = "".join(f"M{rng.randrange(64)} {rng.randrange(64)}h1.4v1.4h-1.4z" for _ in range(28))
    defs.append(f'<pattern id="ns-grain" width="64" height="64" patternUnits="userSpaceOnUse">'
                f'<path fill="#fff" opacity=".06" d="{light}"/><path fill="#000" opacity=".1" d="{dark}"/></pattern>')
    x0, sw = span()
    body.append(f'<rect x="{x0}" width="{sw}" height="{H}" fill="url(#ns-grain)"/>')


def build(lit=False):
    """The picture under one root viewBox: (svg, motion, parts), parts = (css, x0, sw, inside) for scene()."""
    rng = random.Random(11)
    motion = Motion(lit=lit)
    defs, body = [], []
    sky(motion, defs, body, rng)
    skylights(motion, defs, body)
    front = city(motion, defs, body, rng)
    bay(motion, defs, body, rng, front)
    speedboat(motion, defs, body)
    yacht(motion, defs, body)
    bridge(motion, defs, body)
    helicopter(motion, defs, body)
    rooftop(motion, defs, body)
    palms(motion, defs, body)
    planters(body)
    if DETAIL["grain"]:
        grain(defs, body, rng)
    x0, sw = span()
    css = motion.css()
    inner = f'<defs>{"".join(defs)}</defs>{"".join(body)}'
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} 0 {sw} {H}" preserveAspectRatio="xMidYMid slice">'
           f'{css}{inner}</svg>')
    return svg, motion, (css, x0, sw, inner)


def scene(lit=False):
    """The backdrop: a root in CSS px holding the picture nested at the laptop framing, then the limiter in screen
    units over it, every id shortened. The app's glass dims the chat column; attribute geometry only."""
    _, motion, (css, x0, sw, inner) = build(lit)
    pic = f'<svg viewBox="{x0} {VIEW_Y:g} {sw} {VIEW_H}" preserveAspectRatio="xMidYMid slice">'
    svg = short_ids(f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">{css}{pic}{inner}</svg>'
                    f'{limiter()}</svg>')
    # the limiter as written, under its short id: short_ids() would also drop its offsets' leading zeros
    at = svg.rindex("<defs><linearGradient")
    gid = svg[at:].split('id="', 1)[1].split('"', 1)[0]
    return svg[:at] + limiter(gid) + "</svg>", motion


def short_ids(svg):
    """Rename every id (ns-sky, ns-w1s...) to a short one and its references with it: the scene renders exactly
    the same, ~1K smaller. Only the app's scene gets this; the card and the tools keep the readable names."""
    ids = re.findall(r'\bid="(ns-[^"]+)"', svg)
    assert len(ids) == len(set(ids)), "duplicate id"
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    names = [a for a in alphabet] + [a + b for a in alphabet for b in alphabet]
    for old_id, new in zip(sorted(ids, key=lambda i: -svg.count(f"#{i})")), names):
        svg = (svg.replace(f'id="{old_id}"', f'id="{new}"').replace(f"url(#{old_id})", f"url(#{new})")
               .replace(f'href="#{old_id}"', f'href="#{new}"'))
    assert "#ns-" not in svg and 'id="ns-' not in svg, "an id kept its old name"
    # numbers: no leading zero before a decimal point, no ".0" tail (same values, fewer characters)
    svg = re.sub(r'(?<=[="\s,(:-])0\.(?=\d)', ".", svg)
    svg = re.sub(r'(?<=\d)\.0(?![\d.])', "", svg)
    return svg


def strip_style(svg):
    return svg.replace(svg[svg.index("<style>"): svg.index("</style>") + 8], "")


def thumbnail():
    DETAIL.update(THUMB)
    try:
        svg, _, _ = build()
    finally:
        DETAIL.update(FULL)
    svg = re.sub(r' class="m\d+"', "", strip_style(svg))
    svg = re.sub(r'<path[^>]* opacity="0" d="[^"]*"/>', "", svg)
    svg = re.sub(r'<g[^>]* opacity="0">.*?</g>', "", svg)
    # the traffic too small for its column fades: plain colours
    svg = re.sub(r'<linearGradient id="ns-(?:tail|head)".*?</linearGradient>', "", svg)
    svg = svg.replace("url(#ns-tail)", "#ff4766").replace("url(#ns-head)", "#fff1d4")
    svg = svg.replace("url(#ns-yacht-hull)", "#cdc6e4").replace("url(#ns-yacht-house)", "#e2dcf2")   # flat at card size
    svg = svg.replace('fill="url(#ns-beam)"', 'fill="#fff3d6" opacity=".16"').replace('fill="url(#ns-sky-beam)"', 'fill="#e2d6ff" opacity=".14"')
    # definitions nothing on the card uses any more
    for m in list(re.finditer(r'<(linearGradient|radialGradient|pattern|mask)[^>]*id="([^"]+)".*?</\1>', svg, re.S)):
        if f"url(#{m.group(2)})" not in svg:
            svg = svg.replace(m.group(0), "")
    from rescale import rescale_svg
    card = rescale_svg(svg, 704 / W, 0, 84, 704, 396, eps=1.0)   # y 84: the centred crop the app's slice shows
    return live_card(card)


def ramp_frames(rise, hold, fall, period, peak=1.0):
    """Opacity stops for a cross-fade: up over `rise` beats, held, down over `fall`, off for the rest; one
    explicit stop per beat while it changes (step-end), so no step is bigger than peak/rise."""
    stops = [(0, 0.0)]
    stops += [(b / period, peak * b / rise) for b in range(1, rise + 1)]
    stops += [((rise + hold + b) / period, peak * (1 - b / fall)) for b in range(1, fall + 1)]
    stops += [(1, 0.0)]
    out, seen = [], set()
    for f, v in stops:
        if f not in seen:
            seen.add(f)
            out.append(f"{pct(f * 100)}{{opacity:{v:.3g}}}")
    return "".join(out)


def live_card(card):
    """The live card preview: the city's two searchlights sweeping through three angles, cross-fading on a
    4.5 s loop. The card's own beams are the middle angle; default frame = the still card."""
    k, oy = 704 / W, 84
    base = [(1760, HORIZON - 120), (1860, HORIZON - 140)]
    def cones(pair):
        out = []
        for (bx, by), a in zip(base, pair):
            t = math.radians(a)
            tx, ty = bx + math.sin(t) * 900, by - math.cos(t) * 900
            nx, ny = math.cos(t) * 46, math.sin(t) * 46
            pts = [(bx - 3, by), (tx - nx, ty - ny), (tx + nx, ty + ny), (bx + 3, by)]
            out.append("M" + "L".join(f"{x * k:.1f} {(y - oy) * k:.1f}" for x, y in pts) + "z")
        return "".join(out)
    still = 'fill="#e2d6ff" opacity=".14"'
    assert card.count(still) == 1, "the card's beams moved"
    card = card.replace(still, 'class="c1" ' + still)
    period = 36   # beats: each angle up 0.75 s, held 0.75 s, down 0.75 s; the next starts as one fades
    # brighter than the still card's .14 so the sweep reads at 176 x 99 pt (~8/255 a beat)
    style = ("<style>@keyframes nscard{" + ramp_frames(6, 6, 6, period, 0.3) + "}"
             ".c0{animation:nscard 4.5s step-end infinite 0s}.c1{animation:nscard 4.5s step-end infinite -3s}"
             ".c2{animation:nscard 4.5s step-end infinite -1.5s}"
             "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>")
    head_end = card.index(">") + 1
    beams = (f'<path class="c0" fill="#e2d6ff" opacity="0" d="{cones((-14, 8))}"/>'
             f'<path class="c2" fill="#e2d6ff" opacity="0" d="{cones((-2, 20))}"/>')
    at = card.index('class="c1"')
    at = card.rindex("<path", 0, at)
    return card[:head_end] + style + card[head_end:at] + beams + card[at:]


if __name__ == "__main__":
    svg, motion = scene()
    lit, _ = scene(lit=True)
    raw, _, _ = build()
    (HERE / "scene-preview.svg").write_text(svg)
    (HERE / "scene-still.svg").write_text(strip_style(svg))
    (HERE / "scene-lit.svg").write_text(lit)
    (HERE / "scene-raw.svg").write_text(strip_style(raw))
    (ROOT / "plugins/after-hours/hooks/scene-after-hours.js").write_text(
        "// Generated by themes/after-hours/make-scene.py: edit the generator, not this file.\n"
        f"export const SCENE = {json.dumps(svg)}\n")
    css_len = svg.index("</style>") - svg.index("<style>")
    print(f"scene {len(svg):,} chars (cap {CAP:,}, headroom {CAP - len(svg):,}); css {css_len:,}; "
          f"{motion.count} animated groups, {len(motion.frames)} keyframes")
    assert len(svg) <= CAP - HEADROOM, "over budget"
    thumb = thumbnail()
    (ROOT / "cards/after-hours.svg").write_text(thumb)   # the picker's live card (tools/build.py packs it)
    print(f"thumbnail {len(thumb):,} chars (card limit 20,000)")
