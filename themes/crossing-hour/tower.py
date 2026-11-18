"""Tower Bridge, London, at sunset: the build scene.

Seen side-on from downstream, looking west into the low sun. The bridge sits right of centre: the north tower,
floodlit warm, stands in the laptop's right margin; the south tower is a backlit silhouette behind the text.
The sun sets behind the Shard on the left; the rider rides out of the sunset across the bridge, on a loop.
Brightness lives in the margins; the column holds deep sky and a soft horizon haze he reads against.
Scale 10.6 units a metre (the rider is drawn ~2.8x life size so his pedalling reads).
"""
from __future__ import annotations

import math
import random

from bridges import BAND, H, XL, XR, Motion, cycle, rgrad, rider_ride, slide, swell, vgrad
from svglib import cloud, poly, polys

K = 10.6
Y_W = 1000                       # high-water line = the far bank's horizon
Y_D = Y_W - round(8.6 * K)       # roadway (909)
HW = 84                          # tower half-width (slim, as the real towers)
GAP = round(61 * K)              # bascule opening (647)
TN = 1740                        # north tower (right margin on the laptop), floodlit
TS = TN - 2 * HW - GAP           # south tower (behind the text), backlit
CORNICE = Y_W - round(50 * K)    # 470
WALK_B = Y_W - round(42.5 * K)   # walkway bottom (549)
WALK_T = WALK_B - 40
SUN = (100, 874)   # clear of the chain's dip (the hangers would stripe the disc)
SHARD_X = 70
CARD = False                     # the /themes card build: same picture, no fine detail, no motion

# palette: column sky #1b1c40 -> #3b3168, horizon <= #5a4478, silhouettes #24214d / #2e2a5c;
# margins #ff9a5c, #ffb86b, #c96a7a
SIL, SIL_D = "#2e2a5c", "#24214d"


def col(x):
    """1 inside the laptop text column, 0 in the margins, smooth between (for dimming at the source)."""
    a, b = BAND
    if x < a - 200 or x > b + 200:
        return 0.0
    if a <= x <= b:
        return 1.0
    t = (a - x) / 200 if x < a else (x - b) / 200
    t = max(0.0, min(1.0, t))
    return 1 - t * t * (3 - 2 * t)


# ------------------------------------------------------------------ sky, sun, clouds

def sky(m, defs, body, rng):
    defs.append(vgrad("tb-sky", [(0, "#151a3e"), (0.3, "#1a1f48"), (0.58, "#2c2a5c"), (0.78, "#4a3a6a"), (0.92, "#6a4462"), (1, "#8a4a5a")], 0, Y_W))   # dusk, rose at the horizon
    # the sunset as a radial glow round the sun in the left margin, falling off before the text column
    defs.append(rgrad("tb-sun", SUN[0], SUN[1], 600, [(0, "#ffd9a0", 1), (0.06, "#ffb86b", 0.95), (0.16, "#ff9a5c", 0.62),
                                                      (0.3, "#c96a7a", 0.24), (0.5, "#7a4a78", 0.07), (1, "#7a4a78", 0)], sy=0.55))
    # a second, low warm haze along the horizon: strongest in the margins, a faint lane behind the rider in the column
    defs.append(f'<linearGradient id="tb-lane" x1="{XL}" x2="{XR}" gradientUnits="userSpaceOnUse">'
                + "".join(f'<stop offset="{(x - XL) / (XR - XL):.3f}" stop-color="{c}" stop-opacity="{o}"/>' for x, c, o in
                          ((XL, "#ff9a5c", .55), (160, "#ff9a5c", .45), (340, "#a8607a", .16), (700, "#8a5a86", .15), (1300, "#8a5a86", .15),
                           (1580, "#a8607a", .18), (1900, "#d07870", .42), (XR, "#c96a7a", .35))) + '</linearGradient>')
    defs.append(vgrad("tb-lane-v", [(0, "#fff", 0), (0.55, "#fff", 1), (1, "#fff", 1)], Y_D - 160, Y_W))
    defs.append(f'<mask id="tb-lane-m"><rect x="{XL}" y="{Y_D - 160}" width="{XR - XL}" height="{Y_W - Y_D + 160}" fill="url(#tb-lane-v)"/></mask>')
    x0, sw = XL, XR - XL
    body.append(f'<rect x="{x0}" width="{sw}" height="{Y_W + 2}" fill="url(#tb-sky)"/>')
    if not CARD:
        body.append(f'<rect x="{x0}" y="{Y_D - 160}" width="{sw}" height="{Y_W - Y_D + 162}" fill="url(#tb-lane)" mask="url(#tb-lane-m)"/>')
    body.append(f'<rect x="{x0}" y="{SUN[1] - 420}" width="{sw}" height="{H - SUN[1] + 420}" fill="url(#tb-sun)"/>')
    # stars high in the deep blue, sparse, a few twinkling
    st = [[], []]
    for i in range(0 if CARD else 110):
        x, y = rng.uniform(XL, XR), rng.uniform(70, 200)
        if math.hypot(x - SUN[0], y - SUN[1]) < 1000:
            continue   # none in the sunset
        st[i % 2].append(f"M{x:.0f} {y:.0f}h.4")
    stars = f'<path stroke="#e8e2ff" stroke-width="2" stroke-linecap="round" opacity=".45" d="{"".join(st[0])}"/>' if st[0] else ""
    if st[1]:
        stars += f'<path class="{swell(m, "tbst", 40, .15, .6, steps=10)}" opacity=".15" stroke="#e8e2ff" stroke-width="2" stroke-linecap="round" d="{"".join(st[1])}"/>'
    body.append(stars)
    # long thin clouds, lit from below near the sun, violet over the column; a slow breath on the lit undersides
    shapes, lit = [], []
    for cx, cy, ln, th in ((380, 640, 1100, 13), (1050, 430, 1300, 12), (1500, 300, 1100, 9)) if CARD else ((380, 640, 1100, 13), (-80, 520, 900, 10), (1050, 430, 1300, 12), (1900, 560, 1000, 11),
                           (700, 760, 900, 8), (2150, 380, 800, 9), (1500, 300, 1100, 9)):
        c = cloud(rng, cx, cy, ln, th)
        shapes.append(c)
        lit.append([(x, y + th * 0.35) for x, y in c[len(c) // 2:]][::-1] + [(x, y) for x, y in c[len(c) // 2:]])
    defs.append(f'<linearGradient id="tb-cloud" x1="{XL}" x2="{XR}" gradientUnits="userSpaceOnUse">'
                + "".join(f'<stop offset="{(x - XL) / (XR - XL):.3f}" stop-color="{c}"/>' for x, c in
                          ((XL, "#e38a72"), (300, "#d9806e"), (600, "#6e4a78"), (1500, "#4e3a6e"), (1900, "#8a5a7a"), (XR, "#9a6078"))) + '</linearGradient>')
    if not CARD:
        body.append(f'<path fill="url(#tb-cloud)" opacity=".55" d="{polys(shapes)}"/>')
    if not CARD:
      body.append(f'<path class="{swell(m, "tbcl", 96, .25, .6, steps=24)}" fill="#ffb07a" d="{polys(lit)}" opacity=".4" mask="url(#tb-sunside)"/>')
    defs.append(f'<radialGradient id="tb-sunside-g" gradientUnits="userSpaceOnUse" cx="{SUN[0]}" cy="{SUN[1]}" r="900"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
                f'<mask id="tb-sunside"><rect x="{XL}" width="{XR - XL}" height="{Y_W}" fill="url(#tb-sunside-g)"/></mask>')
    # the sun itself, low over the far bank, half behind the wharves
    body.append(f'<circle cx="{SUN[0]}" cy="{SUN[1]}" r="44" fill="#ffe7bc"/>')
    body.append(f'<circle class="{swell(m, "tbsh", 160, .25, .5, steps=32)}" cx="{SUN[0]}" cy="{SUN[1]}" r="64" fill="#ffd090" opacity=".35"/>' if not CARD else
                f'<circle cx="{SUN[0]}" cy="{SUN[1]}" r="64" fill="#ffd090" opacity=".35"/>')


# ------------------------------------------------------------------ the far bank: wharves, the City, the Shard

def far_bank(m, defs, body, rng):
    """The far bank, real London: the Shard behind the wharves in haze, City Hall's leaning egg and
    HMS Belfast on the south bank (left); the White Tower and the City's towers on the north bank (right). Low, even
    wharves between, so the column stays quiet."""
    haze = "#4a3a6c"
    # the Shard: a hazy glass spire behind everything on the bank, its tip splintered, its base dissolving into haze
    sx, base, tip = SHARD_X, Y_W, 300
    defs.append(vgrad("tb-shard", [(0, "#4a3a6c"), (0.75, "#4a3a6c"), (1, "#6a4a6e", 0)], tip, base))
    body.append(f'<path fill="url(#tb-shard)" d="{poly([(sx - 70, base), (sx - 28, tip + 130), (sx - 9, tip + 30), (sx - 6, tip), (sx - 2, tip + 22), (sx + 2, tip + 8), (sx + 7, tip + 36), (sx + 28, tip + 140), (sx + 68, base)])}"/>')
    body.append(f'<path fill="#5a4470" opacity=".7" d="{poly([(sx + 2, tip + 8), (sx + 7, tip + 36), (sx + 28, tip + 140), (sx + 68, base), (sx + 8, base), (sx, tip + 60)])}"/>')
    body.append(f'<path fill="none" stroke="#ffb86b" stroke-width="2" opacity=".75" d="M{sx + 7} {tip + 36}L{sx + 28} {tip + 140}L{sx + 50} {tip + 400}"/>')
    if not CARD:
        gl = []
        for yy in range(tip + 70, base - 120, 9):
            f = (yy - tip) / (base - tip)
            for xx in range(int(sx - 66 * f + 4), int(sx + 64 * f - 4), 7):
                if rng.random() < 0.14:
                    gl.append(f"M{xx} {yy}h2")
        body.append(f'<path stroke="#ffd7a6" stroke-width="1.6" opacity=".4" d="{"".join(gl)}"/>')
        body.append(f'<circle class="{m.use(m.keyframes("tbav", [(0, "opacity:1"), (0.3, "opacity:.15"), (1, "opacity:.15")]), 2)}" cx="{sx - 6}" cy="{tip - 2}" r="3" fill="#ff5050"/>')
    # the City on the north bank, behind the right approach: Gherkin, Walkie-Talkie, Cheesegrater, 22 Bishopsgate, Scalpel
    city, lights = [], []
    for cx, wd, h, kind in ((1850, 52, 250, "scalpel"), (1915, 58, 330, "cheese"), (1985, 70, 360, "bulk"), (2060, 50, 230, "gherkin"),
                            (2130, 56, 250, "walkie"), (2200, 44, 170, "slab"), (2262, 50, 140, "slab")):
        top = Y_W - h
        if kind == "gherkin":
            pts = [(cx - wd / 2 * math.sin(math.pi * (0.12 + 0.88 * t)), Y_W - h * t) for t in [i / 12 for i in range(0, 13)]]
            pts = pts + [(2 * cx - x, y) for x, y in pts[::-1]]
        elif kind == "walkie":
            pts = [(cx - wd / 2, Y_W), (cx - wd / 2 - 8, top + 40), (cx - wd / 2 - 4, top + 6), (cx, top - 6), (cx + wd / 2 + 6, top + 4), (cx + wd / 2 + 10, top + 40), (cx + wd / 2, Y_W)]
        elif kind == "cheese":     # the wedge, sloping down toward St Paul's (left)
            pts = [(cx - wd / 2, Y_W), (cx - wd / 2, top + 150), (cx + wd / 2, top), (cx + wd / 2, Y_W)]
        elif kind == "scalpel":    # a slanted blade
            pts = [(cx - wd / 2, Y_W), (cx - wd / 2, top + 60), (cx + wd / 4, top), (cx + wd / 2, top + 30), (cx + wd / 2, Y_W)]
        elif kind == "bulk":       # 22 Bishopsgate: a broad flat-topped mass with set-back corners
            pts = [(cx - wd / 2, Y_W), (cx - wd / 2, top + 14), (cx - wd / 2 + 8, top), (cx + wd / 2 - 8, top), (cx + wd / 2, top + 14), (cx + wd / 2, Y_W)]
        else:
            pts = [(cx - wd / 2, Y_W), (cx - wd / 2, top + 8), (cx - wd / 2 + 6, top), (cx + wd / 2, top), (cx + wd / 2, Y_W)]
        city.append(pts)
        if not CARD:
            for yy in range(int(top + 16), Y_W - 10, 11):
                for xx in range(int(cx - wd / 2 + 5), int(cx + wd / 2 - 5), 8):
                    if rng.random() < 0.14:
                        lights.append(f"M{xx} {yy}h2.5")
    body.append(f'<path fill="#56406e" d="{polys(city)}"/>')
    if lights:
        body.append(f'<path stroke="#ffd7a0" stroke-width="2" opacity=".45" d="{"".join(lights)}"/>')
    # low, even wharves along both banks: one haze layer, then a nearer darker one; a few warm windows
    defs.append(f'<linearGradient id="tb-near" x1="{XL}" x2="{XR}" gradientUnits="userSpaceOnUse">'
                + "".join(f'<stop offset="{(x - XL) / (XR - XL):.3f}" stop-color="{c}"/>' for x, c in
                          ((XL, "#6a4466"), (350, "#5a3c62"), (700, "#3a2c5c"), (1500, "#36295a"), (XR, "#46325e"))) + '</linearGradient>')
    for fill, hmin, hmax, wmin, seed in ((haze, 16, 34, 70, 1), ("url(#tb-near)", 8, 20, 50, 2)):
        r = random.Random(seed)
        pts = [(XL, Y_W + 2)]
        x = XL
        while x < XR:
            w = r.uniform(wmin, wmin * 2.2)
            h = r.uniform(hmin, hmax)
            pts += [(x, Y_W - h), (x + w, Y_W - h)]
            x += w
        pts += [(XR, Y_W + 2)]
        body.append(f'<path fill="{fill}" d="{poly(pts)}"/>')
    # City Hall's leaning egg, south bank
    ex, ey = 252, Y_W - 6
    body.append(f'<path fill="#3e3062" d="M{ex - 34} {ey}c-4-30 6-48 28-50c18-1 36 14 34 50z"/>')
    if not CARD:
        body.append(f'<path fill="none" stroke="#ffc890" stroke-width="1.2" opacity=".5" d="M{ex - 30} {ey - 14}h58M{ex - 28} {ey - 28}h50"/>')
    # HMS Belfast moored off the south bank: grey hull, superstructure, two raked funnels, two masts
    bx, by = 380, Y_W - 2
    ship = [(bx, by), (bx + 220, by), (bx + 228, by - 14), (bx + 150, by - 14), (bx + 150, by - 24), (bx + 70, by - 24), (bx + 70, by - 14), (bx - 6, by - 14)]
    body.append(f'<path fill="#3a2f5c" d="{poly(ship)}"/>')
    body.append(f'<path fill="#3a2f5c" d="{poly([(bx + 88, by - 24), (bx + 92, by - 36), (bx + 100, by - 36), (bx + 98, by - 24)])}{poly([(bx + 118, by - 24), (bx + 122, by - 35), (bx + 130, by - 35), (bx + 128, by - 24)])}"/>')
    body.append(f'<path stroke="#3a2f5c" stroke-width="2" d="M{bx + 60} {by - 14}l4-26M{bx + 166} {by - 14}l3-24M{bx - 4} {by - 12}l60 -26M{bx + 228} {by - 14}l-58-22"/>')
    # the White Tower on the north bank: a square keep, four turrets with ogee caps
    wx, wy = 1975, Y_W - 6
    body.append(f'<path fill="#3e3062" d="{poly([(wx, wy), (wx, wy - 26), (wx + 80, wy - 26), (wx + 80, wy)])}"/>')
    for tx in (wx, wx + 26, wx + 54, wx + 80):
        body.append(f'<path fill="#3e3062" d="M{tx - 5} {wy - 26}v-6h10v6zM{tx - 5} {wy - 32}q5-10 10 0z"/>')


# ------------------------------------------------------------------ the river

def river(m, defs, body, rng):
    defs.append(vgrad("tb-river", [(0, "#4a3866"), (0.07, "#33295a"), (0.4, "#1d1b42"), (1, "#0e1028")], Y_W, H))
    defs.append(rgrad("tb-river-sun", SUN[0], Y_W, 420, [(0, "#ff9a5c", 0.65), (0.3, "#c96a7a", 0.3), (1, "#c96a7a", 0)], sy=0.6))
    x0, sw = XL, XR - XL
    body.append(f'<rect x="{x0}" y="{Y_W}" width="{sw}" height="{H - Y_W}" fill="url(#tb-river)"/>')
    if not CARD:
        body.append(f'<rect x="{x0}" y="{Y_W}" width="{sw}" height="{H - Y_W}" fill="url(#tb-river-sun)"/>')
    # broad faint ripples everywhere
    rip = "".join(f"M{rng.uniform(XL, XR):.0f} {rng.uniform(Y_W + 6, H):.0f}h{rng.randint(30, 120)}" for _ in range(0 if CARD else 150))
    body.append(f'<path stroke="#6a5a90" stroke-width="1.4" opacity=".28" d="{rip}"/>')
    # the sun's path: three phased glint groups widening toward us, in the left margin
    sets = [[], [], []]
    for y in range(Y_W + 4, H, 10 if CARD else 5):
        spread = 16 + (y - Y_W) * 0.42
        for _ in range(1 if CARD else 3):
            x = SUN[0] + rng.gauss(0, spread)
            if col(x) > 0.5:
                continue
            sets[0 if CARD else rng.randrange(3)].append(f"M{x:.0f} {y}h{rng.randint(6, 30)}")
    kg = m.keyframes("tbgl", [(0, "opacity:.95"), (0.33, "opacity:.25"), (0.66, "opacity:.6"), (1, "opacity:.95")])
    for i, s in enumerate(sets):
        if not s:
            continue
        body.append(f'<path class="{m.use(kg, 1.5, -0.5 * i)}" stroke="#ffd29a" stroke-width="2.4" d="{"".join(s)}"/>')
    # the floodlit north tower's reflection: a soft warm column under it, breathing with the floodlight, then broken streaks
    defs.append(vgrad("tb-refl", [(0, "#d99a74", .3), (1, "#d99a74", 0)], Y_W, H))
    body.append(f'<rect x="{TN - 90}" y="{Y_W}" width="180" height="{H - Y_W}" fill="url(#tb-refl)"/>')
    if not CARD:
        body.append(f'<rect class="{swell(m, "tbfl", 112, 0, .16, steps=28)}" opacity="0" x="{TN - 70}" y="{Y_W}" width="140" height="{H - Y_W}" fill="url(#tb-refl)"/>')
    # the floodlit north tower's reflection: warm broken streaks under it, two groups
    rs = [[], []]
    for y in range(Y_W + 8, H, 14 if CARD else 6):
        for _ in range(1 if CARD else 2):
            x = TN + rng.gauss(0, 50 + (y - Y_W) * 0.12)
            rs[rng.randrange(2)].append(f"M{x:.0f} {y}h{rng.randint(6, 22)}")
    kr = m.keyframes("tbrf", [(0, "opacity:.55"), (0.5, "opacity:.2"), (1, "opacity:.55")])
    for i, s in enumerate(rs):
        body.append(f'<path class="{m.use(kr, 2, -1 * i)}" stroke="#f0b47c" stroke-width="2" d="{"".join(s)}"/>')


def riverboat(m, defs, body):
    """A river bus (catamaran) heading downstream, right to left, every ~90 s: dark hull, a lit cabin band."""
    L = 300
    hull = poly([(0, 0), (L - 30, 0), (L, -10), (L - 6, -16), (12, -16), (0, -8)])
    cabin = poly([(40, -16), (L - 70, -16), (L - 92, -40), (60, -40)])
    inner = (f'<path fill="#171634" d="{hull}"/><path fill="#22204a" d="{cabin}"/>'
             f'<path stroke="#ffd59a" stroke-width="3.4" opacity=".6" stroke-dasharray="9 8" d="M70 -28H{L - 90}"/>'
             f'<path stroke="#e9e4ff" stroke-width="1.6" opacity=".5" d="M2 -1H{L - 30}"/>'
             f'<path fill="none" stroke="#ffffff" stroke-width="1.6" opacity=".25" d="M{L} -2q60 4 140 2"/>')
    g, beats = slide(m, "tbboat", inner, XR + 60, XL - L - 300, Y_W + 70, -4)
    body.append(g)


# ------------------------------------------------------------------ the bridge

def tower(m, defs, body, cx, lit):
    """A main tower in side elevation: cream stone, corner turrets running past the cornice to
    tall pointed caps, an upper storey with a stepped central gable, and the steep pavilion roof that out-tops the
    turrets with its flat crest and finial. Framed triple lights in three stages, a balcony at walkway level.
    lit=True: the floodlit north tower; False: the backlit south one (outline and dim windows only)."""
    l, r = cx - HW, cx + HW
    tw = 32
    UP = 406                       # top of the upper storey (eaves of the pavilion roof)
    TUR = 415                      # turret shafts end, caps begin
    if lit:
        defs.append(vgrad("tb-flood", [(0, "#b89a94"), (0.35, "#d9b48c"), (1, "#f3d6a4")], UP, Y_D))
        stone, roof, roof_d, win, trim, frame = "url(#tb-flood)", "#4c4668", "#36324f", "#3a2734", "#f6dcae", "#c49a7c"
    else:
        stone, roof, roof_d, win, trim, frame = SIL, "#17152f", "#100f24", "#8a6448", "#3a3468", "#26224a"
    # pier below the roadway, granite, with its cutwater toward us
    body.append(f'<path fill="{"#3a2f52" if lit else "#1e1b3e"}" d="{poly([(l - 14, Y_D + 18), (r + 14, Y_D + 18), (r + 20, Y_W + 8), (l - 20, Y_W + 8)])}"/>')
    body.append(f'<path fill="{"#2c2444" if lit else "#18162f"}" d="{poly([(cx - 32, Y_D + 18), (cx + 32, Y_D + 18), (cx + 13, Y_W + 8), (cx - 13, Y_W + 8)])}"/>')
    if lit:
        body.append(f'<path fill="#e9a070" opacity=".3" d="{poly([(l - 14, Y_D + 18), (cx - 32, Y_D + 18), (cx - 13, Y_W + 8), (l - 20, Y_W + 8)])}"/>')
    body.append(f'<rect x="{l - 16}" y="{Y_D + 12}" width="{2 * HW + 32}" height="8" fill="{"#d8b48e" if lit else "#2a2550"}"/>')
    rl, rr = l + tw, r - tw
    # the shaft and the upper storey with its stepped central gable
    gable = [(rl - 2, Y_D + 14), (rl - 2, UP), (cx - 30, UP), (cx - 30, UP - 10), (cx - 18, UP - 10), (cx - 18, UP - 21), (cx + 18, UP - 21),
             (cx + 18, UP - 10), (cx + 30, UP - 10), (cx + 30, UP), (rr + 2, UP), (rr + 2, Y_D + 14)]
    body.append(f'<path fill="{stone}" d="{poly(gable)}"/>')
    # the pavilion roof: steep, truncated, flat crest, finial; it rises behind the gable and out-tops the turret caps
    crest = 305
    pav = [(rl + 4, UP), (rr - 4, UP), (cx + 12, crest), (cx - 12, crest)]
    body.insert(len(body) - 1, f'<path fill="{roof}" d="{poly(pav)}"/><path fill="{roof_d}" d="{poly([(cx, UP), (rr - 4, UP), (cx + 12, crest), (cx, crest)])}"/>')
    body.append(f'<path stroke="{trim}" stroke-width="2.4" d="M{cx} {crest}v-35"/><circle cx="{cx}" cy="{crest - 37}" r="3.2" fill="{trim}"/>')
    if not CARD:
        for dx in (-26, 26):   # dormers on the pavilion roof
            body.append(f'<path fill="{stone}" d="{poly([(cx + dx - 7, UP - 34), (cx + dx + 7, UP - 34), (cx + dx + 7, UP - 46), (cx + dx, UP - 54), (cx + dx - 7, UP - 46)])}"/>')
            body.append(f'<rect x="{cx + dx - 3}" y="{UP - 48}" width="6" height="12" rx="3" fill="{"#ffcf8a" if lit else "#8a6448"}" opacity="{.8 if lit else .45}"/>')
    # string courses across shaft and turrets; the cornice
    for y, h in ((CORNICE, 6), (UP, 5), (582, 5), (682, 5), (792, 5)):
        if CARD and y not in (CORNICE, UP):
            continue
        body.append(f'<rect x="{l - 3}" y="{y}" width="{2 * HW + 6}" height="{h}" fill="{trim}" opacity="{.8 if lit else .5}"/>')
    # windows: framed triple lights in three stages, a three-light window in the gable storey
    lights, frames = [], []
    for y0, h in ((600, 34), (700, 38), (808, 40)):
        frames.append(f"M{cx - 35} {y0 - 6}h70v{h + 12}h-70z")
        for dx in (-19, -5, 9):
            lights.append(f"M{cx + dx} {y0 + h}v{-h + 5}a5 5 0 0 1 10 0v{h - 5}z")
    for dx in (-14, -4, 6):
        lights.append(f"M{cx + dx} {UP + 50}v-22a4 4 0 0 1 8 0v22z")
    if not CARD:
        body.append(f'<path fill="{frame}" opacity="{.55 if lit else .4}" d="{"".join(frames)}"/>')
    body.append(f'<path fill="{win}" opacity="{1 if lit else .55}" d="{"".join(lights)}"/>')
    if lit:
        body.append(f'<path fill="#ffcf8a" opacity=".5" d="{"".join(lights[3:6])}"/>')   # one lit room
    # the balcony at walkway level
    body.append(f'<rect x="{rl - 6}" y="{WALK_B - 2}" width="{rr - rl + 12}" height="7" fill="{trim}" opacity="{.85 if lit else .5}"/>')
    if not CARD:
        body.append(f'<path stroke="{trim}" stroke-width="1.4" opacity="{.6 if lit else .35}" d="{"".join(f"M{x} {WALK_B - 2}v-12" for x in range(rl - 4, rr + 6, 7))}M{rl - 6} {WALK_B - 14}H{rr + 6}"/>')
    # the corner turrets: three-faceted shafts past the cornice, tall pointed caps with lucarnes and finials
    for x0 in (l, r - tw):
        body.append(f'<rect x="{x0}" y="{TUR}" width="{tw}" height="{Y_D + 16 - TUR}" fill="{stone}"/>')
        body.append(f'<rect x="{x0}" y="{TUR}" width="{tw / 3:.1f}" height="{Y_D + 16 - TUR}" fill="#000" opacity=".1"/>')
        body.append(f'<rect x="{x0 + 2 * tw / 3:.1f}" y="{TUR}" width="{tw / 3:.1f}" height="{Y_D + 16 - TUR}" fill="#000" opacity=".2"/>')
        body.append(f'<rect x="{x0 - 3}" y="{TUR}" width="{tw + 6}" height="6" fill="{trim}" opacity="{.85 if lit else .5}"/>')
        if not CARD:
            for y in (640, 742, 846):
                body.append(f'<rect x="{x0 + tw / 2 - 3}" y="{y}" width="6" height="24" rx="3" fill="{win}" opacity="{1 if lit else .5}"/>')
        tip = 330
        body.append(f'<path fill="{roof}" d="{poly([(x0 - 4, TUR), (x0 + tw + 4, TUR), (x0 + tw / 2 + 2, tip), (x0 + tw / 2 - 2, tip)])}"/>')
        body.append(f'<path fill="{roof_d}" d="{poly([(x0 + tw / 2, TUR), (x0 + tw + 4, TUR), (x0 + tw / 2 + 2, tip)])}"/>')
        if not CARD:
            body.append(f'<path fill="{trim}" opacity=".7" d="{poly([(x0 + tw / 2 - 5, TUR - 14), (x0 + tw / 2 + 5, TUR - 14), (x0 + tw / 2, TUR - 26)])}"/>')
        body.append(f'<path stroke="{trim}" stroke-width="1.6" d="M{x0 + tw / 2} {tip}v-16"/><circle cx="{x0 + tw / 2}" cy="{tip - 18}" r="2.2" fill="{trim}"/>')
    # rim: the sunward (left) edges catch the last light on the silhouette
    if not lit:
        body.append(f'<path fill="none" stroke="#ff9a5c" stroke-width="2" opacity=".55" d="M{l} {Y_D + 14}V{TUR}L{l + tw / 2 - 2} 330M{rl + 4} {UP}L{cx - 12} {crest}"/>')
    else:
        # floodlight breath: a warm wash over the stone, slow (in step with the reflection's)
        body.append(f'<path class="{swell(m, "tbfl", 112, 0, .16, steps=28)}" opacity="0" fill="#ffc890" d="{poly(gable)}"/>')


def walkways(m, body):
    """The two high-level walkways between the towers: lattice girders, blue with white lattice, a cornice."""
    x0, x1 = TS + HW - 2, TN - HW + 2
    y0, h = WALK_T, WALK_B - WALK_T
    body.append(f'<rect x="{x0}" y="{y0 - 10}" width="{x1 - x0}" height="8" fill="#2e2e5a"/>')   # the far walkway peeping above
    body.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{h}" fill="#2e3262"/>')
    lat = "" if CARD else "".join(f"M{x} {y0 + 5}l16 {h - 10}M{x + 16} {y0 + 5}l-16 {h - 10}" for x in range(x0 + 4, x1 - 16, 16))
    body.append(f'<path stroke="#56649c" stroke-width="1.5" opacity=".6" d="{lat}"/>')
    body.append(f'<rect x="{x0}" y="{y0 - 3}" width="{x1 - x0}" height="6" fill="#4c5690"/><rect x="{x0}" y="{y0 + h - 3}" width="{x1 - x0}" height="6" fill="#3a4478"/>')
    # a dotted row of lights along the walkway, slow twinkle (behind the text on the laptop: dim and small)
    if not CARD:
        body.append(f'<path class="{swell(m, "tbwl", 48, .35, .8, steps=12)}" opacity=".35" stroke="#ffd9a0" stroke-width="2.4" stroke-dasharray="2 22" d="M{x0 + 12} {y0 + 18}H{x1 - 12}"/>')
    # brackets under it into the towers
    for x, s in ((x0, 1), (x1, -1)):
        body.append(f'<path fill="#2e3262" d="{poly([(x, y0 + h), (x + s * 44, y0 + h), (x, y0 + h + 34)])}"/>')


def bus(m, body):
    """A red double-decker crossing right to left on the far lane (behind the rider), every ~75 s: the London nod
   . Drawn ~1.7x life like everything that shares the deck with the rider."""
    L, Hb = 200, 80
    r_ = 10
    shell = f"M0 {-Hb + r_}q0 {-r_} {r_} {-r_}H{L - 14}q14 0 14 14V-10H0z"
    win = "".join(f"M{x} {-Hb + 14}h{22}v18h-22z" for x in range(14, L - 30, 30))
    win += "".join(f"M{x} {-Hb + 48}h{22}v16h-22z" for x in range(44, L - 30, 30))
    inner = (f'<path fill="#a8323a" d="{shell}"/><path fill="#7a2230" d="M0 -10H{L}v-6H0z"/>'
             f'<path fill="#ffd59a" opacity=".75" d="{win}"/>'
             f'<path fill="#2a1a30" d="M6 {-Hb + 44}h{10}v34h-10z"/>'                       # the door at the front (left: it heads left)
             f'<path fill="#2a1a30" d="M{L - 40} {-Hb + 44}h26v20h-26z"/>'
             f'<rect x="2" y="{-Hb + 36}" width="40" height="7" fill="#1a1428"/>'            # destination blind band
             f'<rect x="4" y="{-Hb + 37}" width="30" height="5" fill="#ffcf6a" opacity=".85"/>'
             f'<circle cx="3" cy="-18" r="3.2" fill="#fff4d8"/>'
             f'<g fill="#120d1c"><circle cx="34" cy="-8" r="10"/><circle cx="{L - 40}" cy="-8" r="10"/></g>'
             f'<path fill="none" stroke="#ff9a6a" stroke-width="1.6" opacity=".6" d="M{r_} {-Hb}H{L - 14}"/>')
    g, _ = slide(m, "tbbus", inner, XR + 60, XL - L - 5200, Y_D, -14)
    body.append(g)


def flags(m, body):
    """The two flags on poles above the walkway's centre (Union flag, St George's cross): a two-pose flutter."""
    cx = (TS + TN) / 2
    out = []
    for pose in (0, 1):
        g = ""
        for dx, kind in ((-34, "union"), (34, "george")):
            px0, py0 = cx + dx, WALK_T - 50
            w = 26
            wav = 3 if pose else -3
            shape = f"M{px0} {py0}q{w / 2} {wav} {w} 0v16q{-w / 2} {wav} {-w} 0z"
            g += f'<path fill="#f4efe6" d="{shape}"/>'
            if kind == "george":
                g += f'<path stroke="#c8303a" stroke-width="3" d="M{px0 + w / 2} {py0 + 1 + wav / 2}v15M{px0} {py0 + 8 + wav / 2}h{w}"/>'
            else:
                g += f'<path fill="#1f3a8a" d="{shape}"/><path stroke="#f4efe6" stroke-width="3" d="M{px0} {py0 + 1}l{w} 15M{px0} {py0 + 16}l{w} -15M{px0 + w / 2} {py0 + wav / 2}v16M{px0} {py0 + 8 + wav / 2}h{w}"/>'
                g += f'<path stroke="#c8303a" stroke-width="1.4" d="M{px0 + w / 2} {py0 + wav / 2}v16M{px0} {py0 + 8 + wav / 2}h{w}"/>'
        out.append(g)
    poles = f'<path stroke="#2e3262" stroke-width="2" d="M{cx - 34} {WALK_T - 4}V{WALK_T - 52}M{cx + 34} {WALK_T - 4}V{WALK_T - 52}"/>'
    body.append(poles + (out[0] if CARD else cycle(m, "tbfg", 2, 3, out)))


def chain(body, x_top, x_end, y_top, y_low, y_end):
    """A side-span suspension chain: a lattice girder from the main tower, down to its low point at 68%
    of the span, a short rise to the abutment tower; segments deepest mid-length, tapering to the pins."""
    x_low = x_top + (x_end - x_top) * 0.68
    def at(t):
        if t <= 0.68:
            u = t / 0.68
            return x_top + (x_low - x_top) * u, y_low + (y_top - y_low) * (1 - u) ** 2
        u = (t - 0.68) / 0.32
        return x_low + (x_end - x_low) * u, y_low + (y_end - y_low) * u ** 2
    N = 24 if CARD else 80
    pts = [at(i / N) for i in range(N + 1)]
    pins = (0, 0.35, 0.68, 1.0)
    def depth(t):
        for a, b in zip(pins, pins[1:]):
            if a <= t <= b:
                return 10 + 18 * math.sin(math.pi * (t - a) / (b - a))
        return 10
    dep = [depth(i / N) for i in range(N + 1)]
    up = [(x, y - d / 2) for (x, y), d in zip(pts, dep)]
    dn = [(x, y + d / 2) for (x, y), d in zip(pts, dep)]
    body.append(f'<path fill="#2c3466" d="{poly(up + dn[::-1])}"/>')
    lat = "" if CARD else "".join(f"M{up[i][0]:.0f} {up[i][1]:.0f}L{dn[i + 1][0]:.0f} {dn[i + 1][1]:.0f}M{dn[i][0]:.0f} {dn[i][1]:.0f}L{up[i + 1][0]:.0f} {up[i + 1][1]:.0f}" for i in range(N))
    hi = (f'<path stroke="#9ab0e2" stroke-width="1.3" opacity=".6" d="{lat}"/>' if lat else "") + \
         f'<path fill="none" stroke="#c4d2f2" stroke-width="2" opacity=".8" d="M{up[0][0]:.0f} {up[0][1]:.0f}' + "".join(f"L{x:.0f} {y:.0f}" for x, y in up[1:]) + '"/>'
    body.append(hi)
    hang = "".join(f"M{x:.0f} {y + d / 2:.0f}V{Y_D - 2}" for (x, y), d in list(zip(pts, dep))[1:-1:2 if CARD else 3] if y + d / 2 < Y_D - 12)
    body.append(f'<path stroke="#4a5690" stroke-width="2" d="{hang}"/>')


def shore_tower(body, cx):
    """The smaller abutment tower where a side span lands (south side, on the far left)."""
    w = 110
    top = Y_D - 150
    body.append(f'<rect x="{cx - w / 2}" y="{top}" width="{w}" height="{Y_W - top}" fill="{SIL}"/>')
    for x0 in (cx - w / 2 - 4, cx + w / 2 - 24):
        body.append(f'<rect x="{x0}" y="{top - 20}" width="28" height="{Y_W - top + 20}" fill="{SIL_D}"/>')
        body.append(f'<path fill="#201d42" d="{poly([(x0 - 3, top - 20), (x0 + 31, top - 20), (x0 + 14, 684)])}"/>')
    body.append(f'<path fill="{SIL_D}" d="M{cx - 34} {Y_D + 2}V{Y_D - 60}a34 34 0 0 1 68 0V{Y_D + 2}z" opacity=".0"/>')
    body.append(f'<path fill="none" stroke="#ff9a5c" stroke-width="2" opacity=".6" d="M{cx - w / 2 - 4} {Y_W}V{top - 20}L{cx - w / 2 + 10} 684"/>')


def deck(m, defs, body):
    # the roadway girder across the whole picture, the bascule leaves between the towers
    x0, sw = XL, XR - XL
    body.append(f'<rect x="{x0}" y="{Y_D}" width="{sw}" height="18" fill="#221f46"/>')
    body.append(f'<rect x="{x0}" y="{Y_D + 18}" width="{sw}" height="5" fill="#16142f"/>')
    body.append(f'<rect x="{TS + HW}" y="{Y_D}" width="{GAP}" height="22" fill="#2a2752"/>')
    # the bascules' arched soffit: deep at the piers, shallow at the meeting point
    x0b, x1b, mid = TS + HW, TN - HW, (TS + TN) / 2
    soff = [(x0b, Y_D + 18)] + [(x0b + (x1b - x0b) * t, Y_D + 18 + 14 + 46 * (2 * t - 1) ** 2) for t in [i / 24 for i in range(25)]] + [(x1b, Y_D + 18)]
    body.append(f'<path fill="#3a4478" d="{poly(soff)}"/>')
    if not CARD:
        lat = "".join(f"M{x:.0f} {Y_D + 20}V{Y_D + 18 + 14 + 46 * (2 * (x - x0b) / (x1b - x0b) - 1) ** 2 - 2:.0f}" for x in range(int(x0b) + 20, int(x1b), 26))
        body.append(f'<path stroke="#525ea0" stroke-width="1.6" opacity=".7" d="{lat}"/>')
    body.append(f'<path stroke="#4a4a80" stroke-width="1.2" d="M{mid} {Y_D}v22"/>')


def railing_and_lamps(m, body):
    """The roadway's cast-iron parapet (open lattice, so the rider's wheels show through), and lamp standards."""
    ry = Y_D - 13
    posts = "" if CARD else "".join(f"M{x} {Y_D}V{ry}" for x in range(XL, XR, 9))
    body.append(f'<path stroke="#3a3a70" stroke-width="1.2" opacity=".85" d="{posts}"/>')
    body.append(f'<path stroke="#5a5a94" stroke-width="2.4" d="M{XL} {ry}H{XR}"/><path stroke="#3a3a70" stroke-width="1.6" d="M{XL} {Y_D - 4}H{XR}"/>')
    lamps = [x for x in range(XL + 30, XR, 140) if (not CARD or col(x) < .5) and not (TS - HW - 24 < x < TS + HW + 24 or TN - HW - 24 < x < TN + HW + 24)]
    body.append(f'<path stroke="#1d1a3c" stroke-width="3" d="{"".join(f"M{x} {Y_D}v-58" for x in lamps)}"/>')
    body.append(f'<path stroke="#1d1a3c" stroke-width="7" stroke-linecap="round" d="{"".join(f"M{x} {Y_D - 62}h0" for x in lamps)}"/>')
    halo = "" if CARD else "".join(f'<circle cx="{x}" cy="{Y_D - 62}" r="16"/>' for x in lamps)
    cores = "".join(f'<circle cx="{x}" cy="{Y_D - 62}" r="3.6"/>' for x in lamps)
    if halo:
        body.append(f'<g fill="#ffcf8a" opacity=".3">{halo}</g>')
    body.append(f'<g fill="#ffe6b8" class="{swell(m, "tblp", 24, .82, 1, steps=8)}">{cores}</g>')


# ------------------------------------------------------------------ foreground frames (margins only)

def foreground(m, body, rng):
    # right: a moored Thames barge and two buoys at the bottom
    bx, by = 1660, 1150
    body.append(f'<path fill="#121534" d="{poly([(bx, by), (bx + 300, by), (bx + 330, by - 26), (bx + 320, by - 34), (bx + 10, by - 34), (bx - 20, by - 18)])}"/>')
    body.append(f'<path fill="#16193c" d="{poly([(bx + 60, by - 34), (bx + 190, by - 34), (bx + 180, by - 62), (bx + 70, by - 62)])}"/>')
    body.append(f'<path stroke="#121534" stroke-width="3" d="M{bx + 230} {by - 34}V{by - 120}M{bx + 230} {by - 116}L{bx + 300} {by - 40}"/>')
    body.append(f'<circle class="{m.use(m.keyframes("tbbg", [(0, "opacity:1"), (0.15, "opacity:.2"), (1, "opacity:.2")]), 3)}" cx="{bx + 230}" cy="{by - 124}" r="3.2" fill="#ff5a4a"/>')
    body.append(f'<path fill="none" stroke="#ff9a5c" stroke-width="1.4" opacity=".35" d="M{bx - 20} {by - 18}L{bx + 10} {by - 34}H{bx + 320}"/>')
    for x, y in ((1560, 1172), (1500, 1110)):
        body.append(f'<path fill="#121534" d="M{x - 12} {y}a12 9 0 0 1 24 0zM{x - 3} {y - 9}h6v-14h-6z"/>')


# ------------------------------------------------------------------ gulls

def gulls(m, body, rng):
    """Three gulls wheeling over the right margin: two wing poses each, swapped every other beat, drifting."""
    def gull(x, y, s, up):
        dy = -0.5 * s if up else 0.35 * s
        return f"M{x - s:.0f} {y + dy:.0f}Q{x - s / 2:.0f} {y - 0.4 * s:.0f} {x:.0f} {y:.0f}Q{x + s / 2:.0f} {y - 0.4 * s:.0f} {x + s:.0f} {y + dy:.0f}"
    birds = [(1700, 360, 12), (1790, 330, 9), (1620, 300, 8)]
    a = "".join(gull(x, y, s, True) for x, y, s in birds)
    b = "".join(gull(x, y, s, False) for x, y, s in birds)
    pair = cycle(m, "tbgu", 2, 2, [f'<path d="{a}"/>', f'<path d="{b}"/>'])
    inner = f'<g fill="none" stroke="#1a1838" stroke-width="2.4" stroke-linecap="round">{pair}</g>'
    g, _ = slide(m, "tbgw", inner, 160, -260, 0, -2, extra_y=40)
    body.append(g)


# ------------------------------------------------------------------ the rider

def rider(m, body):
    # tail light blinks (the series' signature); he rides left to right, entering from the sunset
    g, info = rider_ride(m, Y_D, XL, XR, scale=30, step=11, name="tbr", rim="#ffb86b", rest_x=232)
    body.append(g)
    return info


def scene(m: Motion):
    rng = random.Random(23)
    defs, body = [], []
    sky(m, defs, body, rng)
    far_bank(m, defs, body, rng)
    river(m, defs, body, rng)
    if not CARD:
        riverboat(m, defs, body)
        gulls(m, body, rng)
    if not CARD:
        shore_tower(body, -60)
    # the chains dip to just above the rider's helmet (Y_D - 75): lower and he'd be lost against the dark lattice
    # low points at 68% of each side span: just above the rider's helmet; the abutment ends at y 789
    chain(body, TS - HW + 4, -60 + 50, WALK_B + 20, Y_D - 68, Y_D - 120)
    chain(body, TN + HW - 4, TN + HW + 870, WALK_B + 20, Y_D - 68, Y_D - 120)
    deck(m, defs, body)
    if not CARD:
        bus(m, body)
    if CARD:
        x, y = 232, Y_D   # a mini rider: wheels, frame, body (he is ~4 pt tall on the card)
        body.append(f'<g fill="none" stroke="#15111d" stroke-width="2.4"><circle cx="{x}" cy="{y - 10}" r="9"/><circle cx="{x + 30}" cy="{y - 10}" r="9"/>'
                    f'<path d="M{x} {y - 10}l12 0 10-14H{x + 7}l5 14M{x + 30} {y - 10}l-6-17" /><path stroke-width="6" stroke-linecap="round" d="M{x + 7} {y - 28}l13-12M{x + 9} {y - 26}l4 14"/>'
                    f'<circle cx="{x + 23}" cy="{y - 44}" r="4" fill="#15111d"/></g>')
        info = {}
    else:
        info = rider(m, body)
    railing_and_lamps(m, body)
    walkways(m, body)
    flags(m, body)
    tower(m, defs, body, TS, lit=False)
    tower(m, defs, body, TN, lit=True)
    if not CARD:
        foreground(m, body, rng)
    return defs, body, info
