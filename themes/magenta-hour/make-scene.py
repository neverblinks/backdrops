"""Magenta Hour: a synthwave Miami dusk over a violet bay, palms and a causeway. An original composition.

    python3 -I themes/magenta-hour/make-scene.py            (from the repository root; Python 3 only)

Writes plugins/magenta-hour/hooks/scene-magenta-hour.js (export const SCENE), cards/magenta-hour.svg (the
picker's live card, at most 20,000 characters) and, beside this file and not committed, scene-preview.svg
(same SVG), scene-still.svg (default frame, every animated group at rest), scene-lit.svg (every animated
group shown at once: the brightest any frame gets, for the contrast check) and scene-raw.svg (the picture
alone, for likeness). Prints the character count; the app draws one backdrop Svg of at most 131,072 characters.

The app's glass (#0c0720 at 0.58, set in look-magenta-hour.ts) dims the chat column and follows it when the
sidebar or the right panel opens; a highlight limiter in the scene caps the brightest lights behind the text.

App rules this follows (the Claude desktop app's backdrop limits):
- a root <svg> in CSS px holding the picture as one nested <svg viewBox> + xMidYMid slice in picture units,
  with the limiter in CSS px over it; attribute geometry only, no CSS geometry;
- animation only as the full shorthand with step-end, explicit ascending % stops, on a 0.125 s beat;
- only opacity and stroke-dashoffset animate, on ~30 groups (never per element), no masks or filters
  on anything animated; the default frame (attributes) is a complete picture;
- @media (prefers-reduced-motion) is the only media query.
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
from svglib import H, W, Palm, bez, cloud, poly, polys, tower_shape  # noqa: E402

ROOT = HERE.parent.parent
CAP = 131072
HEADROOM = 1500
BEAT = 0.125

# Wide picture: the original 1920 x 1248 scene stays untouched in the middle and
# PAD units of extra scene continue on each side, so a laptop window shows exactly what it did while a 21:9 window keeps
# ~82% of the height instead of 65%. The extension draws from its own random generators: no original draw changes.
PAD = 400
XL, XR = -PAD, W + PAD
LAMP_PERSPECTIVE = 0.5   # 1 = full perspective spacing (too sparse near, too dense far on this curve)
LAMP_EXTRA = 8            # lamps over the laptop's stretch beyond the original count

HORIZON = 772
SUN = (1836, 600)

# Text column in picture units, as measured in a 1512 pt laptop window (at most 963 pt wide, ~181 pt from each
# side): 1512 pt collapsed 349-1571, open 561-1690 (inferred), 1440 collapsed
# 318-1602, the 1000 pt pop-out 348-1572. BAND covers all of them; lights inside it are drawn quieter.
BAND = (340, 1580)
# The app's glass over the chat column, as plugins/magenta-hour/hooks/look-magenta-hour.ts sets it (blur 0). It
# follows the column when the sidebar or the right panel opens.
GLASS, GLASS_TINT = 0.58, "#0c0720"

# Detail knobs: the scene uses these; a small card preview thumbnail (THUMB) cuts them down to fit 18K.
FULL = dict(windows=1.0, ripples=300, glints=190, blades=1.0, fronds=1.0, grain=True, sway=True, clouds=1.0, extras=True, wide=True)
THUMB = dict(windows=0.0, ripples=4, glints=26, blades=0.58, fronds=0.53, grain=False, sway=False, clouds=0.3, extras=False, wide=False)
DETAIL = dict(FULL)


# ------------------------------------------------------------------ animation bookkeeping

def pct(x: float) -> str:
    s = f"{x:.3f}".rstrip("0").rstrip(".")
    return s + "%"


class Motion:
    """Keyframes and class rules, written in the form the app animates."""

    def __init__(self, lit=False):
        self.frames: dict[str, str] = {}
        self.rules: list[str] = []
        self.count = 0
        self.lit = lit     # build the 'every group shown' variant

    def keyframes(self, name, stops):
        """stops: [(fraction 0..1, 'prop:value'), ...] ascending, first 0, last 1."""
        assert stops[0][0] == 0 and stops[-1][0] == 1
        assert all(a[0] < b[0] for a, b in zip(stops, stops[1:])), name
        body = "".join(f"{pct(f * 100)}{{{v}}}" for f, v in stops)
        self.frames[name] = f"@keyframes {name}{{{body}}}"
        return name

    def use(self, name, seconds, delay=0.0):
        """A class running `name`; returns the class name. Durations and delays sit on the beat."""
        assert abs(seconds / BEAT - round(seconds / BEAT)) < 1e-6, seconds
        assert abs(delay / BEAT - round(delay / BEAT)) < 1e-6, delay
        cls = f"m{self.count}"
        self.count += 1
        self.rules.append(f".{cls}{{animation:{name} {seconds:g}s step-end infinite {delay:g}s}}")
        return cls

    def css(self):
        return ("<style>" + "".join(self.frames.values()) + "".join(self.rules)
                + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>")


def dash_flow(motion, name, period, beats, sign):
    """stroke-dashoffset 0 -> sign*period over `beats` steps (one per beat)."""
    stops = [(k / beats, f"stroke-dashoffset:{round(sign * period * k / beats)}") for k in range(beats + 1)]
    return motion.keyframes(name, stops)


# ------------------------------------------------------------------ gradients

def vgrad(gid, stops, y1, y2):
    s = "".join(f'<stop offset="{o}" stop-color="{c}"' + (f' stop-opacity="{a}"' if a != 1 else "") + "/>" for o, c, a in stops)
    return f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" y1="{y1}" x2="0" y2="{y2}">{s}</linearGradient>'


def rgrad(gid, cx, cy, r, stops, sy=1.0):
    s = "".join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in stops)
    tf = f' gradientTransform="matrix(1 0 0 {sy} 0 {round(cy * (1 - sy), 1)})"' if sy != 1 else ""
    return f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{cx}" cy="{cy}" r="{r}"{tf}>{s}</radialGradient>'


# The MacBook's picture area is 1512 x 949 pt (the window under the 33 pt menu bar), where the original 1920-wide picture fitted by WIDTH: 1512 / 1920 = 0.7875 pt a unit. The wide
# picture showed 1248 units of height and so fitted by height there (949 / 1248 = 0.760): everything 3.5% smaller.
# Showing 1205 units of height (21.5 trimmed top and bottom, as that view always cropped) fits by width again.
MAC_SCALE = 1512 / 1920                     # pt per picture unit on the MacBook (the 1512 pt window's width)
VIEW_H = round(949 / MAC_SCALE, 2)          # 1205.08: the picture height the scene shows
VIEW_Y = (1248 - VIEW_H) / 2


# Twins: bright copies of the quiet lights in the strip where the column edge can land on other screens, once shown
# beside the column through a screen mask, now retired. Each animated twin still registers its animation class, so
# the scene's CSS keeps the numbering it shipped with; dropping those calls renumbers the classes.
def in_strip(x):
    return 340 <= x <= 770 or 1150 <= x <= 1580


# Highlight limiter (proven in the app). Behind the column, a darken blend caps every pixel at CAP per
# channel: the sky behind the text stays under it (0.4% of its pixels clipped, ~6/255), so only lights brighter
# than the sky are capped (to luminance <= 0.0705, secondary text >= 4.6:1 at any magnification).
LIM_CAP = "#584270"   # (88, 66, 108)


def limiter():
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
    return (f'<defs><linearGradient id="mh-cap" x2="1">{s}</linearGradient></defs>'
            f'<rect x="50%" width="{width}" height="100%" transform="translate({left} 0)" fill="url(#mh-cap)" style="mix-blend-mode:darken"/>')


def card_band():
    """The card's band: the stops of the reading band the scene once drew over the column, every one at opacity 0.
    It draws nothing; it stays so the card is the one proven in the picker."""
    a, b = BAND
    ease = [(t / 2, 1 - (3 * (t / 2) ** 2 - 2 * (t / 2) ** 3)) for t in range(3)]
    stops = [0] + [a - 230 * t for t, _ in ease[::-1]] + [b + 210 * t for t, _ in ease] + [W]

    def short(v):
        return f"{v:.3f}".rstrip("0").rstrip(".").replace("0.", ".", 1) or "0"
    s = "".join(f'<stop offset="{short(x / W)}" stop-color="#0c0720" stop-opacity="0"/>' for x in stops)
    return f'<linearGradient id="mh-band" x2="1">{s}</linearGradient>'


# ------------------------------------------------------------------ scene parts

def span():
    """(left, width) of the picture: the wide one for the scene, the original for the card."""
    return (XL, XR - XL) if DETAIL["wide"] else (0, W)


def ext_ranges():
    """The two side strips the wide picture adds (empty for the card)."""
    return [(XL, 0), (W, XR)] if DETAIL["wide"] else []


def sky(defs, body, rng):
    # the base is the sky away from the sun (deep violet); the sunset's warmth comes from the glows at
    # the edges, so the part behind the transcript is naturally darker and needs less band (re-key, v0.2)
    defs.append(vgrad("mh-sky", [(0, "#231d4c", 1), (0.3, "#342c6b", 1), (0.55, "#473c83", 1), (0.76, "#5b4994", 1),
                                 (0.9, "#6c549d", 1), (1, "#7b5ca2", 1)], 0, HORIZON))
    defs.append(rgrad("mh-sun-glow", SUN[0], SUN[1], 720, [(0, "#ffe6b2", 1), (0.07, "#ffcb9e", 0.95), (0.2, "#fba79f", 0.72),
                                                            (0.4, "#e08db2", 0.4), (0.68, "#b07bb6", 0.12), (1, "#b07bb6", 0)], sy=0.62))
    defs.append(rgrad("mh-left-glow", -120, HORIZON - 30, 560, [(0, "#f6a6b4", 0.8), (0.5, "#c98abc", 0.3), (1, "#c283b9", 0)], sy=0.75))
    defs.append(vgrad("mh-haze", [(0, "#f2a3b4", 0), (1, "#f2a3b4", 0.16)], HORIZON - 150, HORIZON))
    x0, sw = span()
    body.append(f'<rect x="{x0}" width="{sw}" height="{HORIZON + 2}" fill="url(#mh-sky)"/>')
    body.append(f'<rect x="{x0}" width="{sw}" height="{HORIZON + 2}" fill="url(#mh-sun-glow)"/>')
    body.append(f'<rect x="{x0}" width="{sw}" height="{HORIZON + 2}" fill="url(#mh-left-glow)"/>')
    body.append(f'<rect x="{x0}" y="{HORIZON - 150}" width="{sw}" height="152" fill="url(#mh-haze)"/>')

    # cloud streaks: a violet body and a lit underside, warm only near the sun
    specs = [(330, 205, 720, 14), (990, 138, 1050, 11), (1560, 246, 840, 16), (1230, 330, 580, 8),
             (560, 330, 540, 7), (290, 470, 470, 9), (1720, 468, 640, 13), (780, 548, 430, 6),
             (1400, 590, 540, 6), (1080, 448, 400, 5), (170, 598, 320, 5), (1830, 378, 420, 7),
             (640, 90, 640, 8), (1500, 120, 520, 6), (1880, 560, 360, 7), (1580, 640, 300, 4)]
    specs = specs[: max(4, round(len(specs) * DETAIL["clouds"]))]
    clouds = [cloud(rng, cx, cy, ln, th, bumps=rng.randint(3, 7)) for cx, cy, ln, th in specs]
    if DETAIL["wide"]:   # the streaks carry on past both edges, from their own draws, wholly outside the laptop view
        ext = random.Random(711)
        side = [(-150, 250, 200, 9), (-160, 520, 160, 6), (2080, 180, 200, 10), (2070, 430, 180, 7)]
        clouds += [cloud(ext, cx, cy, ln, th, bumps=ext.randint(3, 5)) for cx, cy, ln, th in side]
        specs = specs + side
    soft = DETAIL["extras"]
    if soft:
        # static blurs (filters only on still content): a wide soft volume under each streak, then the
        # streak itself softened, so the clouds have body instead of reading as flat cut-outs
        defs.append('<filter id="mh-soft" x="-10%" y="-60%" width="120%" height="220%"><feGaussianBlur stdDeviation="4"/></filter>'
                    '<filter id="mh-softer" x="-10%" y="-60%" width="120%" height="220%"><feGaussianBlur stdDeviation="16"/></filter>')
        volume = [cloud(random.Random(i), cx, cy + th * 0.6, ln * 0.9, th * 2.6, bumps=3) for i, (cx, cy, ln, th) in enumerate(specs[:10])]
        body.append(f'<path fill="#6b55a3" opacity=".35" filter="url(#mh-softer)" d="{polys(volume)}"/>')
    flt = ' filter="url(#mh-soft)"' if soft else ""
    body.append(f'<path fill="#64519b" opacity=".55"{flt} d="{polys(clouds)}"/>')
    warm = [c for c, sp in zip(clouds, specs) if sp[0] - sp[2] * 0.5 > 1560]
    cool = [c for c, sp in zip(clouds, specs) if sp[0] - sp[2] * 0.5 <= 1560]
    body.append(f'<path fill="#ffbea6" opacity=".7"{flt} d="{polys([[(x + 7, y + 3) for x, y in c] for c in warm])}"/>')
    body.append(f'<path fill="#9a7cbc" opacity=".45"{flt} d="{polys([[(x + 7, y + 3) for x, y in c] for c in cool])}"/>')

    # the sun, cut by thin cloud bars
    defs.append(rgrad("mh-sun", SUN[0], SUN[1], 84, [(0, "#fffbea", 1), (0.55, "#ffe7b6", 1), (1, "#ffc595", 1)]))
    body.append(f'<circle cx="{SUN[0]}" cy="{SUN[1]}" r="84" fill="url(#mh-sun)"/>')
    bars = [cloud(rng, SUN[0] + rng.uniform(-50, 50), SUN[1] + dy, rng.uniform(260, 420), th)
            for dy, th in ((-34, 5), (2, 7), (30, 6), (56, 8))]
    body.append(f'<path fill="#e389a8" opacity=".82" d="{polys(bars)}"/>')


def birds(motion, rng, body):
    """A small flock; two wing poses swapped on the beat."""
    flock = [(560 + rng.uniform(-80, 80), 300 + rng.uniform(-40, 40), rng.uniform(8, 13)) for _ in range(6)]
    up = "".join(f"M{round(x - s)} {round(y)}q{round(s * .5)} {round(-s * .7)} {round(s)} 0q{round(s * .5)} {round(-s * .7)} {round(s)} 0" for x, y, s in flock)
    flat = "".join(f"M{round(x - s)} {round(y - 2)}q{round(s * .5)} {round(s * .25)} {round(s)} 2q{round(s * .5)} {round(-s * .25)} {round(s)} -2" for x, y, s in flock)
    k_up = motion.keyframes("mhw1", [(0, "opacity:1"), (0.5, "opacity:0"), (1, "opacity:1")])
    k_fl = motion.keyframes("mhw2", [(0, "opacity:0"), (0.5, "opacity:1"), (1, "opacity:0")])
    body.append(f'<g fill="none" stroke="#46386f" stroke-width="2.4" stroke-linecap="round">'
                f'<path class="{motion.use(k_up, 0.75)}" d="{up}"/>'
                f'<path class="{motion.use(k_fl, 0.75)}" opacity="{1 if motion.lit else 0}" d="{flat}"/></g>')


def deco_tower(x, w, h, ground):
    """A stepped art deco tower: body, three setbacks, a mast. Returns (silhouette, crown outline)."""
    top = ground - h
    steps = [(0.1, 34), (0.22, 26), (0.34, 20)]
    pts = [(x, ground), (x, top + 80)]
    y = top + 80
    for inset, rise in steps:
        pts += [(x + w * inset, y), (x + w * inset, y - rise)]
        y -= rise
    mid = x + w / 2
    pts += [(mid - 4, y), (mid - 4, y - 70), (mid + 4, y - 70), (mid + 4, y)]
    y2 = top + 80
    right = []
    for inset, rise in steps:
        right += [(x + w * (1 - inset), y2), (x + w * (1 - inset), y2 - rise)]
        y2 -= rise
    pts += right[::-1] + [(x + w, top + 80), (x + w, ground)]
    crown = pts[1:-1]
    return pts, crown


def skyline(motion, defs, body, rng):
    ground = HORIZON + 4
    layers = [  # fill, x0, x1, hmin, hmax, wmin, wmax
        ("#76699f", 640, 1990, 70, 210, 30, 72),
        ("#5b5294", 700, 1990, 110, 330, 34, 82),
        ("#463f80", 760, 1990, 60, 250, 40, 96),
    ]
    windows_static, windows_anim = [], [[], [], []]
    rims = []
    front_shapes = []
    ext = random.Random(712)   # the side strips' own towers and windows (the original draws stay as they were)
    for li, (fill, x0, x1, hmin, hmax, wmin, wmax) in enumerate(layers):
        shapes = []
        runs = [(rng, x0 + rng.uniform(0, 20), x1)]
        if DETAIL["wide"]:
            runs.append((ext, x1 - 30, XR + 30))
        for r_, x, x_end in runs:
          rng_ = r_
          while x < x_end:
            rng = rng_
            w = rng.uniform(wmin, wmax)
            peak = (0.45 + 0.55 * math.exp(-((x - 1290) / 280) ** 2)) * (1 - 0.55 * math.exp(-((x - SUN[0]) / 110) ** 2))
            h = hmin + (hmax - hmin) * peak * rng.uniform(0.4, 1.0)
            style = rng.choice(["setback", "flat", "flat", "spire", "slant", "round", "setback"])
            pts = tower_shape(rng, x, w, h, ground, style)
            shapes.append(pts)
            if li == 2:
                front_shapes.append(pts)
            if li >= 1 and w > 34:
                cols = max(1, int((w - 10) / 11))
                rows = max(1, int((h * 0.82) / 14))
                for r in range(rows):
                    for c in range(cols):
                        if rng.random() < (0.16 if li == 2 else 0.1) * DETAIL['windows']:
                            wx = round(x + 6 + c * 11)
                            wy = round(ground - 10 - r * 14)
                            (windows_static if rng.random() < 0.6 else windows_anim[rng.randrange(3)]).append((wx, wy))
            x += w + rng.uniform(-w * 0.3, w * 0.15) * (1 if li else 0.3)
        rng = runs[0][0]
        if li == 2:
            for pts in shapes:
                rim_col = "warm" if pts[0][0] > 1580 else ("pink" if pts[0][0] > 1150 else "cool")
                rims.append((rim_col, [(px + 4, py - 1) for px, py in pts]))
            body.append(f'<path fill="#ffcfae" d="{polys([p for c, p in rims if c == "warm"])}"/>')
            body.append(f'<path fill="#8572ad" d="{polys([p for c, p in rims if c == "cool"])}"/>')
            body.append(f'<path fill="#9b78b0" d="{polys([p for c, p in rims if c == "pink"])}"/>')
        body.append(f'<path fill="{fill}" d="{polys(shapes)}"/>')

    # landmark towers: a stepped deco tower with a cyan neon crown, a slim spire with a beacon,
    # and a block with coral neon fins at the right edge
    t1, crown1 = deco_tower(1702, 60, 410, ground)
    t3 = [(1062, ground), (1062, ground - 300), (1078, ground - 330), (1090, ground - 420), (1102, ground - 330),
          (1118, ground - 300), (1118, ground)]
    t2 = [(1872, ground), (1872, ground - 170), (1888, ground - 170), (1888, ground - 184), (1924, ground - 184),
          (1924, ground - 170), (1940, ground - 170), (1940, ground)]
    body.append(f'<path fill="#ffcfae" d="{polys([[(px + 4, py - 1) for px, py in p] for p in (t1, t2)])}"/>')
    body.append(f'<path fill="#51498f" d="{polys([t1, t2, t3])}"/>')
    fins = "".join(f"M{round(1702 + 60 * f)} {ground - 6}V{ground - 320}" for f in (0.3, 0.5, 0.7))
    body.append(f'<path stroke="#6f66ad" stroke-width="3" d="{fins}"/>')

    # windows: a steady set plus three sets that switch on and off slowly
    def wpath(pts):
        d = ""
        for wx, wy in sorted(pts, key=lambda p: (p[1], p[0])):
            d += f"M{wx} {wy}h3"
        return d
    def split(pts):
        return [q for q in pts if not BAND[0] - 20 < q[0] < BAND[1]], [q for q in pts if BAND[0] - 20 < q[0] < BAND[1]]
    out_w, in_w = split(windows_static)
    # behind the column the windows are dimmer: at 2560 pt one window fills a glyph-sized box
    body.append(f'<path stroke="#ffe3b6" stroke-width="2.6" opacity=".85" d="{wpath(out_w)}"/>'
                f'<path stroke="#b49a86" stroke-width="2.6" opacity=".6" d="{wpath(in_w)}"/>')
    kw = motion.keyframes("mhwin", [(0, "opacity:.9"), (0.3, "opacity:0"), (0.55, "opacity:.9"), (1, "opacity:.9")])
    for i, pts in enumerate(windows_anim):
        o, n = split(pts)
        if DETAIL["extras"] and any(in_strip(q[0]) for q in n):
            motion.use(kw, 12, -4 * i)   # a retired twin's class (see "Twins")
        body.append(f'<g class="{motion.use(kw, 12, -4 * i)}" stroke-width="2.6" opacity=".9"><path stroke="#ffe3b6" d="{wpath(o)}"/>'
                    f'<path stroke="#a18a7a" d="{wpath(n)}"/></g>')

    # neon: crown tubes on the deco tower (cyan), fins on the right block (coral), a red beacon
    crown_d = poly(crown1, closed=False)
    fins2 = f"M1884 {ground - 12}V{ground - 160}M1904 {ground - 12}V{ground - 160}M1872 {ground - 120}h68"
    kf = motion.keyframes("mhneon", [(0, "opacity:1"), (0.52, "opacity:.25"), (0.5417, "opacity:1"), (0.5625, "opacity:.35"),
                                     (0.5833, "opacity:1"), (0.86, "opacity:.6"), (0.875, "opacity:1"), (1, "opacity:1")])
    body.append(f'<g class="{motion.use(kf, 6)}" fill="none">'
                f'<path stroke="#62f0ff" stroke-width="12" opacity=".22" d="{crown_d}"/>'
                f'<path stroke="#c9fbff" stroke-width="3" d="{crown_d}"/></g>')
    body.append(f'<g class="{motion.use(kf, 6, -2.5)}" fill="none">'
                f'<path stroke="#ff6f8f" stroke-width="12" opacity=".25" d="{fins2}"/>'
                f'<path stroke="#ffd2dc" stroke-width="3" d="{fins2}"/></g>')
    kb = motion.keyframes("mhbeacon", [(0, "opacity:1"), (0.25, "opacity:.1"), (1, "opacity:.1")])
    body.append(f'<g class="{motion.use(kb, 2)}"><circle cx="1090" cy="{ground - 424}" r="7" fill="#ff4f6a" opacity=".22"/>'
                f'<circle cx="1090" cy="{ground - 424}" r="3" fill="#a8506a"/></g>')
    return front_shapes


def shore_hotels(body):
    """Low art deco hotels on the far left shore: shaded periwinkle fronts, cream-peach faces turned to
    the sun, a stepped parapet, dark window bands (bleached pastel facades, small)."""
    base = HORIZON - 12
    shade, lit, glass = [], [], []
    for x, w, h, d in [(6, 56, 58, 14), (72, 80, 82, 20), (168, 52, 48, 14), (228, 50, 64, 14)]:
        top = base - h
        shade.append([(x, base), (x, top + 8), (x + w * 0.35, top + 8), (x + w * 0.35, top), (x + w * 0.65, top),
                      (x + w * 0.65, top + 8), (x + w, top + 8), (x + w, base)])
        lit.append([(x + w, base), (x + w, top + 8), (x + w + d, top + 12), (x + w + d, base)])
        for r in range(top + 18, base - 6, 12) if DETAIL["extras"] else ():
            glass.append(f"M{round(x + 6)} {r}h{round(w - 12)}")
    body.append(f'<path fill="#8f86c9" d="{polys(shade)}"/><path fill="#f3c4b9" d="{polys(lit)}"/>'
                f'<path stroke="#6c62a6" stroke-width="3" d="{"".join(glass)}"/>')


def water(motion, defs, body, rng, front_city):
    defs.append(vgrad("mh-sea", [(0, "#77649f", 1), (0.07, "#655a9a", 1), (0.28, "#4f4b8d", 1), (0.6, "#3a3d7e", 1), (1, "#212455", 1)], HORIZON, H))
    defs.append(rgrad("mh-sea-glow", SUN[0], HORIZON, 640, [(0, "#ffd3aa", 0.85), (0.28, "#f3a0b0", 0.45), (0.7, "#c48ac0", 0.12), (1, "#c48ac0", 0)], sy=0.75))
    defs.append(rgrad("mh-sea-left", -140, HORIZON, 520, [(0, "#e897b6", 0.6), (0.5, "#b07bb6", 0.2), (1, "#b07bb6", 0)], sy=0.7))
    x0, sw = span()
    body.append(f'<rect x="{x0}" y="{HORIZON}" width="{sw}" height="{H - HORIZON}" fill="url(#mh-sea)"/>')
    body.append(f'<rect x="{x0}" y="{HORIZON}" width="{sw}" height="{H - HORIZON}" fill="url(#mh-sea-glow)"/>')
    body.append(f'<rect x="{x0}" y="{HORIZON}" width="{sw}" height="{H - HORIZON}" fill="url(#mh-sea-left)"/>')
    # the far shore on the left (in the wide picture it starts further out, on the same line), then the city's
    # reflection (the front towers flipped and squashed)
    shore = [(0, HORIZON + 2), (0, HORIZON - 14), (160, HORIZON - 20), (420, HORIZON - 9), (780, HORIZON - 5), (980, HORIZON), (980, HORIZON + 4)]
    if DETAIL["wide"]:
        shore = [(XL, HORIZON + 2), (XL, HORIZON - 9), (-120, HORIZON - 12)] + shore[1:] + [(0, HORIZON + 2)]   # keeps the laptop's bottom edge
    body.append(f'<path fill="#5b4f90" d="{poly(shore)}"/>')
    shore_hotels(body)
    if DETAIL["extras"]:
        body.append(f'<path fill="#463f80" opacity=".3" transform="matrix(1 0 0 -.42 0 {round(HORIZON * 1.42 + 2.5, 1)})" d="{polys(front_city)}"/>')

    # ripples: a steady set and three that twinkle in turn
    sets = [[], [], [], []]
    inner = [[], [], [], []]
    n_rip = DETAIL["ripples"]
    for i in range(n_rip):
        y = HORIZON + 6 + (i / n_rip) ** 1.6 * (H - HORIZON - 70)
        x = rng.uniform(-20, W)
        ln = 10 + (y - HORIZON) * 0.2 * rng.uniform(0.4, 1.2)
        (inner if BAND[0] - 40 < x < BAND[1] else sets)[i % 4].append(f"M{round(x)} {round(y)}h{round(ln)}")
    ext = random.Random(713)   # the side strips' ripples, from their own draws
    for lo, hi in ext_ranges():
        n_ext = round(n_rip * (hi - lo) / W)
        for i in range(n_ext):
            y = HORIZON + 6 + (i / n_ext) ** 1.6 * (H - HORIZON - 70)
            ln = 10 + (y - HORIZON) * 0.2 * ext.uniform(0.4, 1.2)
            x = ext.uniform(lo, hi - ln - 3) if lo < 0 else ext.uniform(lo + 3, hi)   # wholly inside its strip
            sets[i % 4].append(f"M{round(x)} {round(y)}h{round(ln)}")
    for i in range(4):
        sets[i] = sets[i] + [f'<path stroke="#8a72ad" stroke-width="2" d="{"".join(inner[i])}"/>']
    body.append(f'<g opacity=".3"><path stroke="#c6a3d2" stroke-width="2" d="{"".join(sets[0][:-1])}"/>{sets[0][-1]}</g>')
    kr = motion.keyframes("mhrip", [(0, "opacity:.45"), (0.1667, "opacity:.15"), (0.3333, "opacity:0"), (0.6667, "opacity:0"),
                                    (0.8333, "opacity:.2"), (1, "opacity:.45")])
    for i in range(1, 4 if DETAIL["extras"] else 1):
        body.append(f'<g class="{motion.use(kr, 3, -1 * (i - 1))}" opacity="{1 if motion.lit else .45}"><path stroke="#e7bdd6" stroke-width="2" d="{"".join(sets[i][:-1])}"/>{sets[i][-1]}</g>')
        if any(in_strip(float(seg[1:].split(" ", 1)[0])) for seg in inner[i]):
            motion.use(kr, 3, -1 * (i - 1))   # a retired twin's class (see "Twins")

    # sun glitter: a steady core and four sets that shimmer in turn
    gl = [[], [], [], [], []]
    dim_gl = []
    n_gl = DETAIL["glints"]
    for i in range(n_gl):
        dy = 5 + (i / n_gl) ** 1.5 * (H - HORIZON - 60)
        spread = 26 + dy * 0.5
        x = SUN[0] + rng.gauss(0, spread * 0.55)
        ln = 6 + dy * 0.11 * rng.uniform(0.5, 1.4)
        seg = f"M{round(x - ln / 2)} {round(HORIZON + dy)}h{round(ln)}"
        (dim_gl if x + ln / 2 < BAND[1] else gl[i % 5]).append(seg)
    body.append(f'<path stroke="#ffe0b6" stroke-width="3" opacity=".7" d="{"".join(gl[0])}"/>')
    # glints that fall under the text column stay steady and dim
    body.append(f'<path stroke="#b58cb8" stroke-width="3" opacity=".35" d="{"".join(dim_gl)}"/>')
    kg = motion.keyframes("mhglint", [(0, "opacity:1"), (0.25, "opacity:.45"), (0.5, "opacity:0"), (0.75, "opacity:.3"), (1, "opacity:1")])
    for i in range(1, 5 if DETAIL["extras"] else 1):
        body.append(f'<path class="{motion.use(kg, 1, -0.25 * (i - 1))}" stroke="#fff1d2" stroke-width="3" d="{"".join(gl[i])}"/>')


def causeway(motion, defs, body):
    P0, P1, P2 = (-90, 1082), (520, 814), (1240, 777)

    def speed(t):   # screen units per unit of t along the curve
        return math.hypot(2 * (1 - t) * (P1[0] - P0[0]) + 2 * t * (P2[0] - P1[0]), 2 * (1 - t) * (P1[1] - P0[1]) + 2 * t * (P2[1] - P1[1]))

    def perspective_ts(t_anchor, gap_anchor, size, t_far, x_near):
        """Positions along the causeway for things spaced evenly in the world (lamps, piers): on screen each gap
        is proportional to the thing's size there, so they draw closer together toward the far end and farther
        apart toward the viewer, as real lamps do. t_anchor keeps its exact place."""
        per_size = gap_anchor / size(t_anchor)
        ts, t_ = [t_anchor], t_anchor
        def step(t0, sign):   # the gap judged at the middle of the step, so both directions agree
            t1 = t0 + sign * per_size * size(t0) / speed(t0)
            for _ in range(3):
                tm = (t0 + t1) / 2
                t1 = t0 + sign * per_size * size(tm) / speed(tm)
            return t1
        while True:                                   # toward the far end
            t_ = step(t_, 1)
            if t_ > t_far:
                break
            ts.append(t_)
        t_ = t_anchor
        while True:                                   # toward the viewer
            t_ = step(t_, -1)
            if bez(P0, P1, P2, t_)[0] < x_near:
                break
            ts.insert(0, t_)
        return ts

    n = 64
    top, bottom = [], []
    for i in range(n + 1):
        t = i / n
        p = bez(P0, P1, P2, t)
        th = 72 * (1 - t) ** 1.7 + 3
        top.append(p)
        bottom.append((p[0], p[1] + th))
    # the wide picture: the same curve carried on outward (t < 0) until it is under the promenade, past the strip
    pre_top, pre_bottom = [], []
    if DETAIL["wide"]:
        for i in range(1, 15):
            t = -i / n
            p = bez(P0, P1, P2, t)
            th = 72 * (1 - t) ** 1.7 + 3
            pre_top.insert(0, p)
            pre_bottom.insert(0, (p[0], p[1] + th))
            if p[0] < XL - 40 or p[1] > 1240:
                break
    def causeway_lamp_ts():
        lamp_ts, tl = [], 0.015
        while tl < 0.93:
            lamp_ts.append(tl)
            tl += 0.032 + 0.1 * tl

        def lamp_h(tt):
            # the lamp's height, softened: full perspective put almost every lamp in the far, foreshortened half and
            # left the near end bare; gaps still shrink smoothly toward the far end, more gently (a painter's perspective)
            return (74 * (1 - tt) ** 1.6 + 6) ** LAMP_PERSPECTIVE
        # realistic spacing: anchored on the first lamp the laptop shows, the next gap as the laptop had it;
        # the far end stops where the lamps would be closer than a few units
        seen = [tt for tt in lamp_ts if bez(P0, P1, P2, tt)[0] >= 0]
        # as many lamps over the laptop's stretch as the original had (76 read as too many): the
        # anchor gap is chosen so the perspective spacing from the first visible lamp to the far end fits that count
        lo_gap, hi_gap = 10.0, 400.0
        for _ in range(40):
            gap = (lo_gap + hi_gap) / 2
            count = sum(1 for tt in perspective_ts(seen[0], gap, lamp_h, 0.93, 1e9) if tt >= seen[0])
            lo_gap, hi_gap = (gap, hi_gap) if count > len(seen) + LAMP_EXTRA else (lo_gap, gap)
        lamp_ts = [tt for tt in perspective_ts(seen[0], gap, lamp_h, 0.93, (XL - 40) if DETAIL["wide"] else -60)]
        if not DETAIL["extras"]:   # the card (176 pt wide): the far lamps are fractions of a point there
            lamp_ts = [tt for tt in lamp_ts if tt < 0.42]
        return lamp_ts

    def pier_w(tt):
        return 24 * (1 - tt) ** 1.6 + 2
    # piers stand under every other lamp (as on real causeways), so they keep the lamps' perspective rhythm
    pier_ts = causeway_lamp_ts()[::2]
    if not DETAIL["extras"]:   # the card: far piers are fractions of a point there
        pier_ts = [tt for tt in pier_ts if tt < 0.5]
    piers = []
    for tp in pier_ts:
        p = bez(P0, P1, P2, tp)
        th = 72 * (1 - tp) ** 1.7 + 3
        pw = pier_w(tp)
        ph = 130 * (1 - tp) ** 1.5 + 5
        piers.append([(p[0] - pw / 2, p[1] + th), (p[0] - pw / 2, p[1] + th + ph), (p[0] + pw / 2, p[1] + th + ph), (p[0] + pw / 2, p[1] + th)])
    # the deck's shading is pinned to the original span (-90 to 1240), so a longer deck doesn't restretch it
    defs.append('<linearGradient id="mh-deck" gradientUnits="userSpaceOnUse" x1="-90" x2="1240"><stop offset="0" stop-color="#5a4a8e"/><stop offset=".45" stop-color="#463c80"/><stop offset="1" stop-color="#4c4386"/></linearGradient>')
    body.append(f'<path fill="#3a3270" d="{polys(piers)}"/>')
    body.append(f'<path fill="url(#mh-deck)" d="{poly(pre_top + top + bottom[::-1] + pre_bottom[::-1])}"/>')
    # the parapet catches the sunset near us and fades to lilac with distance
    # the parapet catches the sunset near us and fades to lilac where the text column begins (a gradient, never a cut)
    a = BAND[0]
    rail = poly([(x, y - 1) for x, y in pre_top + top], closed=False)
    if DETAIL["extras"] and DETAIL["wide"]:
        # the lilac line, and the sunset-pink line over it (once faded by a screen mask; now the pink covers it)
        body.append(f'<path fill="none" stroke="#8f76b4" stroke-width="2.6" d="{rail}"/>'
                    f'<path fill="none" stroke="#efb7c2" stroke-width="2.6" d="{rail}"/>')
    else:
        defs.append(f'<linearGradient id="mh-parapet" gradientUnits="userSpaceOnUse" x1="{a - 150}" y1="0" x2="{a + 20}" y2="0">'
                    '<stop offset="0" stop-color="#efb7c2"/><stop offset=".5" stop-color="#c495c0"/><stop offset="1" stop-color="#8f76b4"/></linearGradient>')
        body.append(f'<path fill="none" stroke="url(#mh-parapet)" stroke-width="2.6" d="{rail}"/>')
    # lamp posts and their globes
    posts, glows, cores, dim_cores = [], [], [], []
    lamp_ts = causeway_lamp_ts()
    for tl in lamp_ts:
        p = bez(P0, P1, P2, tl)
        k = (1 - tl) ** 1.6
        lh = 74 * k + 6
        posts.append(f"M{round(p[0])} {round(p[1])}v{-round(lh)}")
        inside = BAND[0] - 20 < p[0] < BAND[1]
        glows.append(f'<circle cx="{round(p[0])}" cy="{round(p[1] - lh)}" r="{round((6 if inside else 16) * k + 3)}"/>')
        (dim_cores if inside else cores).append(f'<circle cx="{round(p[0])}" cy="{round(p[1] - lh)}" r="{max(1.2, round(5 * k + 1, 1))}"/>')
    body.append(f'<path stroke="#33295f" stroke-width="3" d="{"".join(posts)}"/>')
    body.append((f'<g fill="#ffd9a6" opacity=".22">{"".join(glows)}</g>' if DETAIL["extras"] else "") + f'<g fill="#fff0d0">{"".join(cores)}</g>'
                f'<g fill="#c4a6a6" opacity=".18">{"".join(dim_cores)}</g>')

    # traffic: tail lights going away, headlights coming in, in three depth bands, each flowing at
    # its own speed (stroke-dashoffset on the beat)
    period = 120
    bands = [  # slice of the deck, dasharray (sums to period), width, seconds, beats, opacity
        (slice(0, 19), "11 6 11 92", "9 5 9 97", 5, 1.25, 10, 1),
        (slice(18, 46), "7 4 7 102", "6 4 6 104", 3.8, 1.75, 14, 0.18),
        (slice(45, None), "3 2 3 112", "3 2 3 112", 2.2, 3, 24, 0.32),
    ]
    a = BAND[0]
    ramp = [(0, 1), (a - 150, 1), (a - 100, 0.8), (a - 50, 0.45), (a, 0.24), (a + 40, 0.18), (W, 0.18)]
    screen = DETAIL["extras"] and DETAIL["wide"]
    if not screen:   # the card fades the lights along the causeway; the scene draws them plain
        for gid, colour in (("mh-tail", "#ff4766"), ("mh-head", "#fff1d4")):
            defs.append(f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{W}" y2="0">'
                        + "".join(f'<stop offset="{max(0, x) / W:.3f}" stop-color="{colour}" stop-opacity="{k}"/>' for x, k in ramp) + '</linearGradient>')
    lanes = []
    for bi, (part, dash_tail, dash_head, width, secs, beats, op) in enumerate(bands):
        op = 1
        k_out = dash_flow(motion, f"mht{bi}o", period, beats, -1)
        k_in = dash_flow(motion, f"mht{bi}i", period, beats, 1)
        th = lambda t: 72 * (1 - t) ** 1.7 + 3  # noqa: E731
        tail = [(x, y - 0.24 * th(i / n) - 4) for i, (x, y) in enumerate(top) if i in range(*part.indices(len(top)))]
        head = [(x, y - 0.1 * th(i / n) - 2) for i, (x, y) in enumerate(top) if i in range(*part.indices(len(top)))]
        def lane_d(main, off):
            """The lane as path data. The laptop's stretch is written exactly as poly() wrote it; in the wide
            picture the same lane on the extended stretch comes first, and its first point is moved back along
            its segment so the added length is a whole number of dash periods: every dash lands where it did."""
            if not (bi == 0 and pre_top):
                return poly(main, closed=False)
            k = len(pre_top)
            pre = [(round(x), round(y - off(-(k - j) / n))) for j, (x, y) in enumerate(pre_top)]
            first_main = (round(main[0][0]), round(main[0][1]))
            chain = pre + [first_main]
            length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(chain, chain[1:]))
            extra = math.ceil(length / period) * period - length
            (x0, y0), (x1, y1) = chain[0], chain[1]
            seg = math.hypot(x0 - x1, y0 - y1)
            fx, fy = x0 + (x0 - x1) / seg * extra, y0 + (y0 - y1) / seg * extra
            lead = f"M{fx:.3f} {fy:.3f}L" + " ".join(f"{x} {y}" for x, y in chain[1:])
            rest = poly(main, closed=False)          # "M<x> <y>l<steps>": keep its steps, drop its move-to
            steps = rest[rest.index("l"):] if "l" in rest else ""
            return lead + steps
        tail_d = lane_d(tail, lambda tt: 0.24 * th(tt) + 4)
        head_d = lane_d(head, lambda tt: 0.1 * th(tt) + 2)
        tail_paint, head_paint = ("#ff4766", "#fff1d4") if screen else ("url(#mh-tail)", "url(#mh-head)")
        lanes.append(f'<path class="{motion.use(k_out, secs)}" fill="none" stroke="{tail_paint}" stroke-width="{width * 0.85:g}" stroke-linecap="round" '
                     f'stroke-dasharray="{dash_tail}" opacity="{op}" d="{tail_d}"/>')
        lanes.append(f'<path class="{motion.use(k_in, secs, -BEAT * 3)}" fill="none" stroke="{head_paint}" stroke-width="{width:g}" stroke-linecap="round" '
                     f'stroke-dasharray="{dash_head}" opacity="{op}" d="{head_d}"/>')
    body.append("".join(lanes))


PALMS = {
    # name: seed, base, height, lean, trunk, frond length, fronds, leaflets, crown colour, base colour, sway
    "C": (23, (-40, 1300), 640, 90, 26, 330, 13, 16, "#7a4f92", "#6a5f9e", False),
    "E": (22, (398, 1300), 820, -70, 28, 400, 13, 17, "#74478a", "#655a99", False),
    "D": (12, (1248, 1318), 560, -24, 22, 290, 12, 15, "#7a4f92", "#6a5f9e", False),
    "A": (21, (104, 1336), 1130, 176, 36, 540, 14, 19, "#5b2858", "#4a3a73", True),
    "B": (11, (1984, 1336), 1240, -74, 34, 520, 14, 19, "#5b2858", "#4a3a73", True),
}
PALM_LOOK = dict(droop=1.1, blade_len=0.28, leaf_width=0.55, leaf_angle=42, leaf_droop=0.75, hanging=0)


def palms(motion, defs, body, names):
    k0 = motion.keyframes("mhp0", [(0, "opacity:1"), (0.25, "opacity:0"), (0.5, "opacity:1"), (0.75, "opacity:0"), (1, "opacity:1")])
    kp = motion.keyframes("mhp1", [(0, "opacity:0"), (0.25, "opacity:1"), (0.5, "opacity:0"), (1, "opacity:0")])
    km = motion.keyframes("mhp2", [(0, "opacity:0"), (0.75, "opacity:1"), (1, "opacity:0")])
    for name in names:
        seed, base, h, lean, tw, fl, nf, bl, top_col, base_col, sway = PALMS[name]
        nf, bl = max(8, round(nf * DETAIL["fronds"])), max(6, round(bl * DETAIL["blades"]))
        sway = sway and DETAIL["sway"]
        p = Palm(seed, base, h, lean, tw, fl, n_fronds=nf, blades=bl, **PALM_LOOK)
        if DETAIL["extras"]:
            gid = f"mh-palm{name}"
            defs.append(vgrad(gid, [(0, top_col, 1), (0.45, top_col, 1), (1, base_col, 1)], base[1] - h - fl * 0.4, base[1]))
            fill = f"url(#{gid})"
        else:
            fill = top_col
        lo, sw = span()
        # fronds a laptop shows (tips within -60..W+40): exactly as before; fronds only the wide picture's side
        # strips show: their own still path in the same fill (the stacking can't change)
        ext_ids = {i for i in range(len(p.frond_specs)) if lo - 60 < p.tip(i)[0] < lo + sw + 40} - \
                  {i for i in range(len(p.frond_specs)) if -60 < p.tip(i)[0] < W + 40}

        # every frond the wide picture reaches, so crowns are complete: the ones the laptop used to
        # leave out show only their bases at its very edge
        if not sway:
            keep = {i for i in range(len(p.frond_specs)) if -60 < p.tip(i)[0] < W + 40}
            body.append(f'<path fill="{fill}" d="{polys([p.trunk()] + p.crown(which=keep), orient=True)}"/>')
            if ext_ids:
                body.append(f'<path fill="{fill}" d="{polys(p.crown(which=ext_ids, hub=False), orient=True)}"/>')
            continue
        # the fronds hanging out over the open margin sway, in two sets out of step; the rest stay put
        on_screen = [i for i in range(len(p.frond_specs)) if -60 < p.tip(i)[0] < W + 40]
        margin = (lambda x: x < BAND[0] + 110) if base[0] < W / 2 else (lambda x: x > BAND[1] - 110)
        movers = [i for i in on_screen if margin(p.tip(i)[0])]
        still = set(on_screen) - set(movers)
        body.append(f'<path fill="{fill}" d="{polys([p.trunk()] + p.crown(which=still), orient=True)}"/>')
        if ext_ids:
            body.append(f'<path fill="{fill}" d="{polys(p.crown(which=ext_ids, hub=False), orient=True)}"/>')
        for gi, ids in enumerate([set(movers[0::2]), set(movers[1::2])]):
            delay = -0.75 * gi
            for pose, key in ((0.0, k0), (1.3, kp), (-1.3, km)):
                crown = p.crown(pose=pose * (1 if gi == 0 else -1), which=ids, hub=False)
                op = "1" if (pose == 0.0 or motion.lit) else "0"
                body.append(f'<path class="{motion.use(key, 3, delay)}" fill="{fill}" opacity="{op}" d="{polys(crown, orient=True)}"/>')


def gator(motion, body):
    """A small surprise: a Florida gator in the sun glitter on the bay.
    It floats with its eyes and snout up, blinks, slips under for a few seconds, and comes back."""
    x, y = 1726, 1012   # in the sun glitter at the right edge, above the message box; y is the waterline
    # profile, facing left: snout with a nostril bump, the head rising to raised eye knobs, then the back
    # with its ridge of scutes trailing off to the right, all just breaking the surface
    head = [(x - 78, y + 1), (x - 74, y - 5), (x - 66, y - 6), (x - 62, y - 10), (x - 57, y - 6), (x - 34, y - 7),
            (x - 14, y - 9), (x - 9, y - 17), (x - 3, y - 19), (x + 2, y - 15), (x + 8, y - 12), (x + 22, y - 12),
            (x + 27, y - 19), (x + 33, y - 20), (x + 37, y - 14), (x + 46, y - 10)]
    for k in range(9):   # scutes along the back
        bx = x + 52 + k * 11
        head += [(bx - 4, y - 6 + k * 0.4), (bx, y - 12 + k * 0.6), (bx + 4, y - 6 + k * 0.4)]
    head += [(x + 152, y - 1), (x + 168, y + 1), (x + 168, y + 3), (x - 78, y + 3)]
    eyes = f"M{x - 4} {y - 15}h4M{x + 30} {y - 16}h4"
    ripples = f"M{x - 112} {y + 5}h40M{x + 172} {y + 6}h46M{x - 60} {y + 11}h110M{x + 60} {y + 14}h80"
    up = (f'<path fill="#2b2848" d="{poly(head)}"/>'
          f'<path fill="none" stroke="#6a5f9c" stroke-width="1.6" opacity=".9" d="{poly(head[1:16], closed=False)}"/>'
          f'<path stroke="#c6a3d2" stroke-width="2" opacity=".55" d="{ripples}"/>')
    blink_eyes = f'<path stroke="#ffcf5a" stroke-width="3" stroke-linecap="round" d="{eyes}"/>'
    if not DETAIL["extras"]:
        body.append(up + blink_eyes)
        return
    # Like a real gator: the back slips under first and the eyes and nostrils stay up a moment, watching;
    # coming back, the eyes break the surface first and the back follows. Opacity poses only (step-end).
    #   0-55% surfaced | 55-56% back going under | 56-60% eyes only | 60-76% gone, rings | 76-79% eyes only | 79-80% back up
    knobs = [[(x - 67, y + 1), (x - 63, y - 4), (x - 58, y + 1)],
             [(x - 11, y + 1), (x - 8, y - 7), (x - 2, y - 9), (x + 3, y - 5), (x + 5, y + 1)],
             [(x + 25, y + 1), (x + 28, y - 8), (x + 34, y - 10), (x + 38, y - 5), (x + 41, y + 1)]]
    peek = (f'<path fill="#2b2848" d="{"".join(poly(k) for k in knobs)}"/>'
            f'<path stroke="#ffcf5a" stroke-width="3" stroke-linecap="round" d="M{x - 4} {y - 5}h4M{x + 30} {y - 6}h4"/>'
            f'<path stroke="#c6a3d2" stroke-width="2" opacity=".5" d="M{x - 80} {y + 4}h30M{x - 20} {y + 4}h70"/>')
    k_up = motion.keyframes("mhgup", [(0, "opacity:1"), (0.55, "opacity:.5"), (0.5625, "opacity:0"),
                                      (0.7917, "opacity:.5"), (0.8, "opacity:1"), (1, "opacity:1")])
    k_peek = motion.keyframes("mhgpeek", [(0, "opacity:0"), (0.5625, "opacity:1"), (0.6042, "opacity:0"),
                                          (0.7569, "opacity:1"), (0.7917, "opacity:0"), (1, "opacity:0")])
    k_eye = motion.keyframes("mhgeye", [(0, "opacity:1"), (0.2, "opacity:0"), (0.2083, "opacity:1"), (0.4, "opacity:0"), (0.4083, "opacity:1"),
                                        (0.55, "opacity:0"), (0.8, "opacity:1"), (1, "opacity:1")])
    k_rings = motion.keyframes("mhgring", [(0, "opacity:0"), (0.6042, "opacity:.6"), (0.7, "opacity:.3"), (0.7569, "opacity:.45"),
                                           (0.8333, "opacity:.2"), (0.875, "opacity:0"), (1, "opacity:0")])  # fainter set as it rises
    # rings first, so the gator's body sits in front of their far half as it surfaces
    body.append(f'<path class="{motion.use(k_rings, 18)}" opacity="{1 if motion.lit else 0}" fill="none" stroke="#d6b4dc" stroke-width="2" '
                f'd="M{x - 40} {y}a50 7 0 1 0 100 0a50 7 0 1 0 -100 0M{x - 80} {y + 2}a90 12 0 1 0 180 0a90 12 0 1 0 -180 0"/>')
    body.append(f'<g class="{motion.use(k_up, 18)}">{up}</g>')
    body.append(f'<g class="{motion.use(k_peek, 18)}" opacity="{1 if motion.lit else 0}">{peek}</g>')
    body.append(f'<g class="{motion.use(k_eye, 18)}">{blink_eyes}</g>')


def promenade(body):
    """The promenade, its posts and rails. The laptop's shapes are written exactly as before; in the wide picture
    separate pieces continue them on the same lines past both edges (so the laptop's pixels can't change)."""
    body.append(f'<path fill="#241a40" d="{poly([(0, H), (0, 1194), (W, 1176), (W, H)])}"/>')
    posts = "".join(f"M{x} {round(1194 - 18 * x / W)}v-40" for x in range(14, W, 58)) if DETAIL["extras"] else ""
    body.append(f'<path d="{posts}M0 1156L{W} 1138M0 1190L{W} 1172" stroke="#241a40" stroke-width="8" fill="none"/>')
    body.append(f'<path d="M0 1153L{W} 1135" stroke="#c48bb6" stroke-width="2" opacity=".35"/>')
    if not DETAIL["wide"]:
        return

    def y(y0, x):   # the line through (0, y0) and (W, y0 - 18)
        return y0 - 18 * x / W

    def num(v):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    l, r = XL - 10, XR + 10
    fill = "".join(f"M{num(a)} {H}V{num(y(1194, a))}L{num(b)} {num(y(1194, b))}V{H}z" for a, b in ((l, 0), (W, r)))
    body.append(f'<path fill="#241a40" d="{fill}"/>')
    side_posts = "".join(f"M{x} {round(y(1194, x))}v-40" for x in range(14 - 58 * 5, XR, 58) if x < 0 or x >= W) if DETAIL["extras"] else ""
    rails = "".join(f"M{num(a)} {num(y(y0, a))}L{num(b)} {num(y(y0, b))}" for y0 in (1156, 1190) for a, b in ((l, 0), (W, r)))
    body.append(f'<path d="{side_posts}{rails}" stroke="#241a40" stroke-width="8" fill="none"/>')
    light = "".join(f"M{num(a)} {num(y(1153, a))}L{num(b)} {num(y(1153, b))}" for a, b in ((l, 0), (W, r)))
    body.append(f'<path d="{light}" stroke="#c48bb6" stroke-width="2" opacity=".35"/>')


def grain(defs, body, rng):
    """A fine film grain: a 64 unit tile of light and dark specks at low opacity."""
    light = "".join(f"M{rng.randrange(64)} {rng.randrange(64)}h1.4v1.4h-1.4z" for _ in range(26))
    dark = "".join(f"M{rng.randrange(64)} {rng.randrange(64)}h1.4v1.4h-1.4z" for _ in range(30))
    defs.append(f'<pattern id="mh-grain" width="64" height="64" patternUnits="userSpaceOnUse">'
                f'<path fill="#fff" opacity=".07" d="{light}"/><path fill="#000" opacity=".09" d="{dark}"/></pattern>')
    x0, sw = span()
    body.append(f'<rect x="{x0}" width="{sw}" height="{H}" fill="url(#mh-grain)"/>')


def build(lit=False, band=False):
    """The picture under one root viewBox: (svg, motion, parts), parts = (css, x0, sw, inside) for scene().
    `band`: the card's empty band (see card_band())."""
    rng = random.Random(7)
    motion = Motion(lit=lit)
    defs, body = [], []
    sky(defs, body, rng)
    if DETAIL["extras"]:
        birds(motion, rng, body)
    front_city = skyline(motion, defs, body, rng)
    water(motion, defs, body, rng, front_city)
    causeway(motion, defs, body)
    gator(motion, body)
    palms(motion, defs, body, ["C", "E", "D"] if DETAIL["extras"] else [])
    promenade(body)
    palms(motion, defs, body, ["A", "B"])
    if DETAIL["grain"]:
        grain(defs, body, rng)
    css = motion.css()
    x0, sw = span()
    if band:
        defs.append(card_band())
        body.append(f'<rect width="{W}" height="{H}" fill="url(#mh-band)"/>')
    inside = f'<defs>{"".join(defs)}</defs>{"".join(body)}'
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} 0 {sw} {H}" preserveAspectRatio="xMidYMid slice">'
           f'{css}{inside}</svg>')
    return svg, motion, (css, x0, sw, inside)


def scene(lit=False):
    """The backdrop: a root in CSS px holding the picture nested at the laptop framing, then the limiter in screen
    units over it. The app's glass dims the chat column; attribute geometry only, no CSS geometry."""
    _, motion, (css, x0, sw, inside) = build(lit)
    pic = f'<svg viewBox="{x0} {VIEW_Y:g} {sw} {VIEW_H}" preserveAspectRatio="xMidYMid slice">'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">{css}{pic}{inside}</svg>'
            f'{limiter()}</svg>'), motion


def thumbnail():
    """The card preview: the same scene at thumbnail detail, still, framed 16:9, no reading band."""
    import re
    DETAIL.update(THUMB)
    try:
        svg, _, _ = build(band=True)
    finally:
        DETAIL.update(FULL)
    svg = svg.replace(svg[svg.index("<style>"): svg.index("</style>") + 8], "")
    svg = re.sub(r' class="m\d+"', "", svg)
    # pose and flap groups hidden by default are dead weight in a still
    svg = re.sub(r'<path[^>]* opacity="0" d="[^"]*"/>', "", svg)
    # the card is too small for the traffic and parapet ramps: plain colours, and drop those gradients
    svg = re.sub(r'<linearGradient id="mh-(?:tail|head|parapet)".*?</linearGradient>', "", svg)
    svg = svg.replace("url(#mh-tail)", "#ff4766").replace("url(#mh-head)", "#fff1d4").replace("url(#mh-parapet)", "#b58dc2")
    from rescale import rescale_svg
    card = rescale_svg(svg, 704 / W, 0, 84, 704, 396, eps=0.6)   # y 84: the centred crop the app's slice shows
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
    """The live card preview: the still card plus the sunset breathing, so it reads at 176 x 99 pt: the sun's glow and its long reflection on the water swell and fade, and two wide sets of glitter
    sparkles on the sun path cross-fade, all on one 4 s loop (card units 704 x 396). Default frame = the still card."""
    rng = random.Random(42)
    k, oy = 704 / W, 84
    sets = [[], []]
    for i in range(64):
        dy = 6 + (i / 64) ** 1.25 * (H - HORIZON - 120)
        x = SUN[0] - 40 + rng.gauss(0, (40 + dy * 0.7) * 0.5)
        ln = 16 + dy * 0.12
        if x - ln / 2 < BAND[1] - 120:   # keep it to the bright right side, the sun's path
            continue
        sets[i % 2].append(f"M{round((x - ln / 2) * k)} {round((HORIZON + dy - oy) * k)}h{max(3, round(ln * k))}")
    sx, sy, hy = round(SUN[0] * k), round((SUN[1] - oy) * k), round((HORIZON - oy) * k)
    period = 32   # beats of 0.125 s: a 4 s loop, up 2 s and down 2 s (~9/255 a beat where brightest)
    style = ("<style>@keyframes mhcard{" + ramp_frames(16, 0, 16, period, 0.9) + "}"
             ".c0{animation:mhcard 4s step-end infinite 0s}.c1{animation:mhcard 4s step-end infinite -2s}"
             ".c2{animation:mhcard 4s step-end infinite -1s}"
             "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>")
    glow = ('<radialGradient id="mhcg"><stop offset="0" stop-color="#ffe2b4" stop-opacity=".75"/>'
            '<stop offset="1" stop-color="#ffc8a8" stop-opacity="0"/></radialGradient>'
            f'<g class="c2" opacity="0" fill="url(#mhcg)"><ellipse cx="{sx}" cy="{sy}" rx="96" ry="78"/>'
            f'<ellipse cx="{sx - 10}" cy="{hy + 70}" rx="48" ry="74"/></g>')
    layer = glow + "".join(f'<path class="c{i}" opacity="0" stroke="#fff6e0" stroke-width="3" stroke-linecap="round" d="{"".join(d)}"/>'
                           for i, d in enumerate(sets))
    head_end = card.index(">") + 1
    # under the foreground palms (the first palm path), above the water and the sun
    at = card.find('<path fill="#5b2858"')
    at = at if at > 0 else card.rindex("</svg>")
    return card[:head_end] + style + card[head_end:at] + layer + card[at:]


if __name__ == "__main__":
    svg, motion = scene()
    lit, _ = scene(lit=True)
    still = svg.replace(svg[svg.index("<style>"): svg.index("</style>") + 8], "")
    (HERE / "scene-preview.svg").write_text(svg)
    (HERE / "scene-still.svg").write_text(still)
    (HERE / "scene-lit.svg").write_text(lit)
    raw, _, _ = build()   # the picture alone, for the likeness score
    (HERE / "scene-raw.svg").write_text(raw.replace(raw[raw.index("<style>"): raw.index("</style>") + 8], ""))
    (ROOT / "plugins/magenta-hour/hooks/scene-magenta-hour.js").write_text(
        "// Generated by themes/magenta-hour/make-scene.py: edit the generator, not this file.\n"
        f"export const SCENE = {json.dumps(svg)}\n")
    css_len = svg.index("</style>") - svg.index("<style>")
    print(f"scene {len(svg):,} chars (cap {CAP:,}, headroom {CAP - len(svg):,}); css {css_len:,}; "
          f"{motion.count} animated groups, {len(motion.frames)} keyframes")
    assert len(svg) <= CAP - HEADROOM, "over budget"
    thumb = thumbnail()
    (ROOT / "cards/magenta-hour.svg").write_text(thumb)   # the picker's live card (tools/build.py packs it)
    print(f"thumbnail {len(thumb):,} chars (card limit 20,000)")
