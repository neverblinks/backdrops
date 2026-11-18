"""The Brooklyn Bridge at magenta dusk: the build scene.

Seen from DUMBO looking south-west: the Brooklyn tower stands in the laptop's left margin, turned ~20 degrees so its
twin pointed arches show sky; the main cables sweep down across the picture toward Manhattan; the sun sets on the right
beside One World Trade Center. The rider rides the elevated promenade toward the sun, on a loop. Roadway traffic
glints through the deck truss below him. Scale 10.5 units a metre (the rider is drawn ~3x life size).
(Since 2021 bikes use a roadway lane and the promenade is for walkers: the promenade is kept for the picture.)
"""
from __future__ import annotations

import math
import random

from bridges import BAND, H, XL, XR, Motion, col, cycle, hgrad, hstops, rgrad, rider_ride, slide, swell, vgrad
from svglib import cloud, poly, polys

K = 10.5
Y_D = 880                       # the promenade, at the camera's eye level (the horizon)
SHORE = Y_D + 70                # Manhattan's waterfront
TX0 = 4                         # the tower's left edge
SIDE_W = 177                    # the face toward us (18 m at cos 20)
ARCH_W = 154                    # the arched face, turned away (43 m at sin 20)
TX1 = TX0 + SIDE_W              # the corner between them
TX2 = TX1 + ARCH_W              # the right edge
T_TOP = Y_D - round(43 * K)     # cornice (428)
SUN = (1838, 792)
WTC = 1712
CARD = False


def sky(m, defs, body, rng):
    defs.append(vgrad("bk-sky", [(0, "#1d1a36"), (0.3, "#2a2440"), (0.6, "#3a2c58"), (0.85, "#46305e"), (1, "#52345f")], 0, SHORE))
    defs.append(rgrad("bk-sun", SUN[0], SUN[1], 640, [(0, "#ffe0b0", 1), (0.06, "#ffbf86", 0.95), (0.16, "#f07a5a", 0.7),
                                                     (0.3, "#e88a9a", 0.32), (0.5, "#b85a80", 0.1), (1, "#b85a80", 0)], sy=0.55))
    # the haze lane along the horizon: warm in the margins, a faint lift behind the rider in the column
    defs.append(hstops("bk-lane", ((XL, "#b85a80", .3), (160, "#b85a80", .26), (360, "#8a4a78", .07), (1560, "#8a4a78", .07),
                                   (1760, "#f07a5a", .4), (XR, "#e88a9a", .45))))
    defs.append(vgrad("bk-lane-v", [(0, "#fff", 0), (0.6, "#fff", 1), (1, "#fff", 1)], Y_D - 170, SHORE))
    defs.append(f'<mask id="bk-lane-m"><rect x="{XL}" y="{Y_D - 170}" width="{XR - XL}" height="{SHORE - Y_D + 170}" fill="url(#bk-lane-v)"/></mask>')
    x0, sw = XL, XR - XL
    body.append(f'<rect x="{x0}" width="{sw}" height="{SHORE + 2}" fill="url(#bk-sky)"/>')
    if not CARD:
        body.append(f'<rect x="{x0}" y="{Y_D - 170}" width="{sw}" height="{SHORE - Y_D + 172}" fill="url(#bk-lane)" mask="url(#bk-lane-m)"/>')
    body.append(f'<rect x="{x0}" y="{SUN[1] - 420}" width="{sw}" height="{H - SUN[1] + 420}" fill="url(#bk-sun)"/>')
    st = [[], []]
    for i in range(0 if CARD else 60):
        x, y = rng.uniform(XL, XR), rng.uniform(70, 330)
        if math.hypot(x - SUN[0], (y - SUN[1]) * 1.8) < 900 or BAND[0] - 120 < x < BAND[1] + 120:
            continue
        st[i % 2].append(f"M{x:.0f} {y:.0f}h.4")
    if st[0]:
        body.append(f'<path stroke="#efe4ff" stroke-width="2" stroke-linecap="round" opacity=".45" d="{"".join(st[0])}"/>')
    if st[1]:
        body.append(f'<path class="{swell(m, "bkst", 40, .15, .6, steps=10)}" opacity=".15" stroke="#efe4ff" stroke-width="2" stroke-linecap="round" d="{"".join(st[1])}"/>')
    # magenta cloud streaks: lit pink near the sun, plum over the column
    defs.append(hstops("bk-cloud", ((XL, "#7a4472", 1), (400, "#5a3a66", 1), (1400, "#5a3a66", 1), (1700, "#e88a9a", 1), (XR, "#f09a8a", 1))))
    shapes = [cloud(rng, cx, cy, ln, th) for cx, cy, ln, th in
              (((1500, 560, 1300, 12), (1000, 380, 1100, 10), (2100, 660, 900, 9)) if CARD else
               ((1500, 560, 1300, 12), (1000, 380, 1100, 10), (2100, 660, 900, 9), (400, 300, 900, 9), (1800, 250, 1000, 8), (700, 640, 800, 7)))]
    if not CARD:
        body.append(f'<path fill="url(#bk-cloud)" opacity=".6" d="{polys(shapes)}"/>')
    body.append(f'<circle cx="{SUN[0]}" cy="{SUN[1]}" r="40" fill="#fff0cf"/><circle cx="{SUN[0]}" cy="{SUN[1]}" r="60" fill="#ffd0a0" opacity=".3"/>')


def skyline(m, defs, body, rng):
    """Lower Manhattan across the river: a low haze base, then named silhouettes above the truss in the far
    haze colour: 55 Water / 1 NY Plaza, 20 Exchange Place, 40 Wall Street, 70 Pine, 28 Liberty; Woolworth and the
    Municipal Building on the ultrawide right; One World Trade beside the sun."""
    far, mid = "#633c66", "#4c3560"
    # a low continuous haze base along the waterfront
    r = random.Random(31)
    pts = [(XL, SHORE + 2)]
    x = XL
    while x < XR:
        w = r.uniform(50, 120)
        h = r.uniform(30, 70) if abs(x - SUN[0]) > 120 else r.uniform(10, 24)
        pts += [(x, SHORE - h), (x + w, SHORE - h)]
        x += w
    pts += [(XR, SHORE + 2)]
    body.append(f'<path fill="{mid}" d="{poly(pts)}"/>')
    shapes = []
    def slab(x0, x1, top):
        shapes.append([(x0, SHORE), (x0, top), (x1, top), (x1, SHORE)])
    slab(760, 850, 760); slab(850, 960, 720); slab(700, 760, 800)                       # 55 Water, 1 New York Plaza
    shapes.append([(1066, SHORE), (1066, 700), (1074, 700), (1074, 672), (1082, 672), (1082, 640), (1098, 640), (1098, 672), (1106, 672), (1106, 700), (1114, 700), (1114, SHORE)])   # 20 Exchange Pl
    shapes.append([(1186, SHORE), (1186, 650), (1192, 650), (1192, 620), (1210, 596), (1228, 620), (1228, 650), (1234, 650), (1234, SHORE)])   # 40 Wall St
    shapes.append([(1310, SHORE), (1310, 660), (1316, 660), (1316, 620), (1322, 620), (1322, 595), (1327, 595), (1327, 570), (1333, 570), (1333, 595), (1338, 595), (1338, 620), (1344, 620), (1344, 660), (1350, 660), (1350, SHORE)])   # 70 Pine
    slab(1420, 1480, 650)                                                                # 28 Liberty
    slab(1520, 1600, 760); slab(980, 1040, 780); slab(1140, 1180, 770); slab(1250, 1300, 740); slab(1370, 1410, 760)
    shapes.append([(2040, SHORE), (2040, 700), (2052, 700), (2052, 660), (2062, 640), (2066, 610), (2070, 640), (2080, 660), (2080, 700), (2092, 700), (2092, SHORE)])   # Woolworth
    shapes.append([(2170, SHORE), (2170, 720), (2200, 720), (2200, 690), (2212, 670), (2224, 690), (2224, 720), (2254, 720), (2254, SHORE)])   # Municipal Building
    body.append(f'<path fill="{far}" d="{polys(shapes)}"/><path stroke="{far}" stroke-width="2" d="M1210 596V572M1330 570V552"/>')
    # windows twinkle in two sets (fewer behind the column)
    wins = []
    if not CARD:
        for sh in shapes:
            xs = [p[0] for p in sh]; ys = [p[1] for p in sh]
            for yy in range(int(min(ys)) + 12, SHORE - 6, 11):
                for xx in range(int(min(xs)) + 4, int(max(xs)) - 4, 8):
                    if rng.random() < 0.11 * (1 - 0.6 * col(xx)):
                        wins.append((xx, yy))
    if wins:
        k = m.keyframes("bkwin", [(0, "opacity:.6"), (0.4, "opacity:.25"), (0.6, "opacity:.6"), (1, "opacity:.6")])
        for i in range(2):
            d = "".join(f"M{x} {y}h3" for j, (x, y) in enumerate(wins) if j % 2 == i)
            body.append(f'<path class="{m.use(k, 6, -3 * i)}" stroke="#ffd2a0" stroke-width="2.2" d="{d}"/>')
    # One World Trade Center: roof y 520 (below the tower's cornice), mast to 440, parapet line, white strobe
    bx, base, top = WTC, SHORE, 520
    body.append(f'<path fill="#3e2c58" d="{poly([(bx - 44, base), (bx - 44, base - 80), (bx - 20, top), (bx + 20, top), (bx + 44, base - 80), (bx + 44, base)])}"/>')
    body.append(f'<path fill="#5a3a66" d="{poly([(bx, top), (bx + 20, top), (bx + 44, base - 80), (bx + 44, base), (bx, base)])}"/>')
    body.append(f'<path fill="none" stroke="#ffb89a" stroke-width="1.6" opacity=".7" d="M{bx + 20} {top}L{bx + 44} {base - 80}V{base}M{bx - 20} {top}h40"/>')
    body.append(f'<path stroke="#3e2c58" stroke-width="3" d="M{bx} {top}V440"/>')
    if not CARD:
        body.append(f'<circle class="{m.use(m.keyframes("bkst2", [(0, "opacity:1"), (0.08, "opacity:0"), (1, "opacity:0")]), 1.5)}" cx="{bx}" cy="438" r="3.2" fill="#ffffff" opacity="0"/>')

def river(m, defs, body, rng):
    defs.append(vgrad("bk-water", [(0, "#6a3e66"), (0.08, "#4a3260"), (0.4, "#2a2244"), (1, "#110f24")], SHORE, H))
    defs.append(rgrad("bk-water-sun", SUN[0], SHORE, 440, [(0, "#f07a5a", 0.6), (0.35, "#b85a80", 0.25), (1, "#b85a80", 0)], sy=0.6))
    x0, sw = XL, XR - XL
    body.append(f'<rect x="{x0}" y="{SHORE}" width="{sw}" height="{H - SHORE}" fill="url(#bk-water)"/>')
    if not CARD:
        body.append(f'<rect x="{x0}" y="{SHORE}" width="{sw}" height="{H - SHORE}" fill="url(#bk-water-sun)"/>')
    if not CARD:
        rip = "".join(f"M{rng.uniform(XL, XR):.0f} {rng.uniform(SHORE + 6, H):.0f}h{rng.randint(30, 110)}" for _ in range(130))
        body.append(f'<path stroke="#7a5a8a" stroke-width="1.4" opacity=".25" d="{rip}"/>')
    sets = [[], [], []]
    for y in range(SHORE + 4, H, 16 if CARD else 5):
        spread = 14 + (y - SHORE) * 0.38
        for _ in range(1 if CARD else 3):
            x = SUN[0] + rng.gauss(0, spread)
            if col(x) > 0.5:
                continue
            sets[0 if CARD else rng.randrange(3)].append(f"M{x:.0f} {y}h{rng.randint(6, 28)}")
    kg = m.keyframes("bkgl", [(0, "opacity:.95"), (0.33, "opacity:.25"), (0.66, "opacity:.6"), (1, "opacity:.95")])
    for i, s in enumerate(sets):
        if s:
            body.append(f'<path class="{m.use(kg, 1.5, -0.5 * i)}" stroke="#ffd09a" stroke-width="2.4" d="{"".join(s)}"/>')


def ferry(m, body):
    """A commuter ferry heading up river, right to left: low white-ish hull in shadow, a lit cabin row."""
    L = 220
    inner = (f'<path fill="#1c1630" d="{poly([(0, 0), (L - 24, 0), (L, -12), (L - 4, -18), (8, -18), (0, -8)])}"/>'
             f'<path fill="#2a2140" d="{poly([(36, -18), (L - 50, -18), (L - 64, -38), (48, -38)])}"/>'
             f'<path stroke="#ffd59a" stroke-width="2.4" opacity=".3" stroke-dasharray="6 8" d="M54 -28H{L - 66}"/>'
             f'<path fill="none" stroke="#ffffff" stroke-width="1.4" opacity=".22" d="M{L} -2q50 4 120 2"/>')
    g, _ = slide(m, "bkfe", inner, XR + 40, XL - L - 260, SHORE + 120, -3)
    body.append(g)


def cables(m, defs, body):
    """The cable web: four main cables leaving the arched face under the cornice and converging toward
    Manhattan, LIGHTER than the sky (buff), suspenders every 24, diagonal stays every 48 reaching x ~1480, the land-span
    cables dropping off left. Necklace lights on the near cable."""
    low_x = TX1 + 40 + round(243 * K)
    starts = [(190, 5), (235, 4), (281, 3.5), (326, 3)]
    y0 = T_TOP + 4
    def y_at(x, xs, yl=Y_D - 16):
        t = (x - xs) / (low_x - xs)
        return yl - (yl - y0) * (1 - t) ** 2
    defs.append(hstops("bk-cab", ((XL, "#b87a74", 1), (200, "#b87a74", 1), (420, "#6c5282", 1), (1560, "#6c5282", 1), (1700, "#2a1e36", 1), (XR, "#2a1e36", 1))))
    defs.append(hstops("bk-thin", ((XL, "#9c6672", 1), (240, "#9c6672", 1), (420, "#604a78", 1), (1560, "#604a78", 1), (1700, "#3a2a48", 1), (XR, "#3a2a48", 1))))
    near = starts[0][0]
    # suspenders from the near cable every 24 (48 on the card), stays every 48 from the saddles
    sus = "".join(f"M{x} {y_at(x, near) + 3:.0f}V{Y_D - 4}" for x in range(near + 24, XR, 96 if CARD else 24))
    body.append(f'<path stroke="url(#bk-thin)" stroke-width="1.2" d="{sus}"/>')
    stays = "".join(f"M{near + 40} {y0 + 10}L{near + 40 + d} {Y_D - 4}" for d in range(60, 1290, 160 if CARD else 48))
    stays += "".join(f"M{TX0 + 30} {y0 + 10}L{TX0 + 30 - d} {Y_D - 4}" for d in range(60, 500, 160 if CARD else 48))
    body.append(f'<path stroke="url(#bk-thin)" stroke-width="1.3" d="{stays}"/>')
    # four main cables converging: each starts at its own x and meets 4-unit spacing by x 1500
    for i, (xs, w) in enumerate(starts):
        pts = []
        for x in range(xs, XR + 40, 30):
            spread = max(0.0, 1 - (x - xs) / (1500 - xs))
            pts.append((x, y_at(x, near) + i * (4 + 8 * spread)))
        body.append(f'<path fill="none" stroke="url(#bk-cab)" stroke-width="{w}" d="M{pts[0][0]:.0f} {pts[0][1]:.0f}' + "".join(f"L{x:.0f} {y:.0f}" for x, y in pts[1:]) + '"/>')
    land = [(x, y0 + (TX0 + 30 - x) * 0.55) for x in range(TX0 + 30, XL - 40, -30)]
    body.append(f'<path fill="none" stroke="url(#bk-cab)" stroke-width="5" d="M{land[0][0]:.0f} {land[0][1]:.0f}' + "".join(f"L{x:.0f} {y:.0f}" for x, y in land[1:]) + '"/>')
    lit = [(x, y_at(x, near)) for x in range(1700, XR + 40, 30)]
    body.append(f'<path fill="none" stroke="#ffb48a" stroke-width="1.6" opacity=".75" d="M{lit[0][0]:.0f} {lit[0][1] - 3:.0f}' + "".join(f"L{x:.0f} {y - 3:.0f}" for x, y in lit[1:]) + '"/>')
    # the necklace: lamps strung along the near cable, three sets breathing
    if not CARD:
        sets = [[], [], []]
        for j, x in enumerate(range(near + 60, XR, 60)):
            sets[j % 3].append(f"M{x} {y_at(x, near) + 1:.0f}h0")
        k = m.keyframes("bknk", [(0, "opacity:.95"), (0.33, "opacity:.45"), (0.66, "opacity:.75"), (1, "opacity:.95")])
        g = "".join(f'<path class="{m.use(k, 9, -3 * i)}" stroke="#ffe6b8" stroke-width="4.4" stroke-linecap="round" d="{"".join(st)}"/>' for i, st in enumerate(sets))
        body.append(g)

def deck(m, defs, body):
    """The promenade (the rider's level), the deep open truss of the roadway below with cars glinting through: each car a
    pair of headlights and tail lights; the near roadway flows left (to Brooklyn), the far one right."""
    x0, sw = XL, XR - XL
    top, bot = Y_D + 6, Y_D + 86
    body.append(f'<rect x="{x0}" y="{Y_D}" width="{sw}" height="7" fill="#2a1f34"/>')
    body.append(f'<rect x="{x0}" y="{top + 8}" width="{sw}" height="{bot - top - 8}" fill="#24192e" opacity=".55"/>')
    if not CARD:
        P = 132
        k_l = m.keyframes("bkcl", [(i / 12, f"stroke-dashoffset:{11 * i}") for i in range(13)])      # dashes move left
        k_r = m.keyframes("bkcr", [(i / 12, f"stroke-dashoffset:{-11 * i}") for i in range(13)])     # dashes move right
        cl, cr = m.use(k_l, 1.5), m.use(k_r, 1.5)
        lane = []
        # far lane (y +50) heading right: tail lights left end, headlights right end of each car
        lane.append(f'<path class="{cr}" stroke="#ff5466" stroke-width="3" stroke-dasharray="4 {P - 4}" d="M{XL} {Y_D + 50}H{XR}"/>')
        lane.append(f'<path class="{cr}" stroke="#fff1d4" stroke-width="3.2" stroke-dasharray="0 22 4 {P - 26}" d="M{XL} {Y_D + 50}H{XR}"/>')
        # near lane (y +64) heading left: headlights left end, tail lights right end
        lane.append(f'<path class="{cl}" stroke="#fff1d4" stroke-width="3.6" stroke-dasharray="5 {P - 5}" d="M{XL + 60} {Y_D + 64}H{XR}"/>')
        lane.append(f'<path class="{cl}" stroke="#ff5466" stroke-width="3.2" stroke-dasharray="0 24 5 {P - 29}" d="M{XL + 60} {Y_D + 64}H{XR}"/>')
        body.append("".join(lane))
    body.append(f'<rect x="{x0}" y="{top}" width="{sw}" height="8" fill="#2c2038"/><rect x="{x0}" y="{bot - 8}" width="{sw}" height="10" fill="#2c2038"/>')
    lat = "".join(f"M{x} {top + 8}L{x + 34} {bot - 8}M{x + 34} {top + 8}L{x} {bot - 8}M{x} {top + 8}V{bot - 8}" for x in (range(0, 1960, 102) if CARD else range(XL, XR, 34)))
    body.append(f'<path stroke="#2c2038" stroke-width="2.4" d="{lat}"/>')

def railing_and_lamps(m, body):
    ry = Y_D - 15
    if not CARD:
        posts = "".join(f"M{x} {Y_D}V{ry}" for x in range(XL, XR, 12))
        body.append(f'<path stroke="#3a2c4c" stroke-width="1.4" d="{posts}"/>')
    body.append(f'<path stroke="#4a3a5e" stroke-width="2.6" d="M{XL} {ry}H{XR}M{XL} {Y_D - 5}H{XR}"/>')
    lamps = [x for x in range(XL + 50, XR, 190) if (x < TX0 - 20 or x > TX2 + 20) and (not CARD or col(x) < .5)]
    body.append(f'<path stroke="#241a30" stroke-width="3" d="{"".join(f"M{x} {Y_D}v-56" for x in lamps)}"/>')
    if not CARD:
        halo = "".join(f'<circle cx="{x}" cy="{Y_D - 60}" r="15" opacity="{.28 * (1 - col(x)) + .05:.2f}"/>' for x in lamps)
        body.append(f'<g fill="#ffcf8a">{halo}</g>')
    cores = "".join(f'<circle cx="{x}" cy="{Y_D - 60}" r="{4 - 2 * col(x):.1f}" opacity="{1 - .7 * col(x):.2f}"/>' for x in lamps)
    body.append(f'<g fill="#ffe6b8" class="{swell(m, "bklp", 24, .82, 1, steps=8)}">{cores}</g>')


def tower(m, defs, body):
    """The Brooklyn tower turned ~20 degrees: granite in magenta light. The face toward us in shade with
    stepped insets; the arched face with three buttresses and two pointed arches (dark recesses: no sky shows through
    17 m of stone at this angle), set-offs, a string course, a cornice that breaks forward round the buttresses, a parapet,
    buttress caps; a belt course at the roadway; the base sinking into dusk."""
    defs.append(vgrad("bk-shade", [(0, "#5a3c58"), (0.62, "#7c5068"), (1, "#3a2848")], T_TOP, H))
    defs.append(vgrad("bk-lit", [(0, "#b08a9c"), (0.33, "#d9a07e"), (0.55, "#e6a880"), (0.82, "#8a5a6c"), (1, "#4a3050")], T_TOP, H))
    defs.append(hgrad("bk-rec", [(0, "#2c1e3a"), (1, "#6a4660")], 0, 1).replace('gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="1" y2="0"', 'x2="1"'))
    # the face toward us (shade), its left edge stepping in 20 / 10 / 0; 10 wider below the belt course
    left = [(TX0 + 20, T_TOP), (TX0 + 20, 565), (TX0 + 10, 565), (TX0 + 10, 700), (TX0, 700), (TX0, 945), (TX0 - 10, 945), (TX0 - 10, H + 10)]
    body.append(f'<path fill="url(#bk-shade)" d="{poly(left + [(TX1, H + 10), (TX1, T_TOP)])}"/>')
    # the arched face: lit stone, then the buttress strips over it
    body.append(f'<path fill="url(#bk-lit)" d="{poly([(TX1, T_TOP), (TX2, T_TOP + 6), (TX2 + 10, 945), (TX2 + 10, H + 10), (TX1, H + 10)])}"/>')
    for a, b in ((206, 243), (273, 310)):           # the arches: dark recesses, apex 565, springing 640, down behind the truss
        cx = (a + b) / 2
        body.append(f'<path fill="url(#bk-rec)" d="M{a} 938V640Q{a} 590 {cx} 565Q{b} 590 {b} 640V938z"/>')
        body.append(f'<path fill="none" stroke="#f2b890" stroke-width="2" opacity=".55" d="M{b} 640Q{b} 590 {cx} 565"/>')
    for a, b in ((181, 206), (243, 273), (310, 335)):   # buttresses: lighter, a shaded left flank, set-offs at 565 and 700
        segs = [(T_TOP, 565, 8), (565, 700, 4), (700, H + 10, 0)]
        for y0, y1, inset in segs:
            body.append(f'<rect x="{a + inset}" y="{y0}" width="{b - a - 2 * inset}" height="{y1 - y0}" fill="#e0a884" opacity=".55"/>')
            body.append(f'<rect x="{a + inset}" y="{y0}" width="5" height="{y1 - y0}" fill="#8a5a6c" opacity=".7"/>')
        for y in (565, 700):
            body.append(f'<path fill="#f2b890" d="{poly([(a, y), (b, y), (b - 4, y - 6), (a + 4, y - 6)])}"/>')
    # string course, cornice breaking forward round the buttresses, parapet, buttress caps
    body.append(f'<rect x="{TX0 + 20}" y="520" width="{TX2 - TX0 - 20}" height="6" fill="#f2b890"/><rect x="{TX0 + 20}" y="526" width="{TX2 - TX0 - 20}" height="3" fill="#4a3050" opacity=".6"/>')
    body.append(f'<rect x="{TX0 + 14}" y="{T_TOP}" width="{TX2 - TX0 - 8}" height="24" fill="#d9a07e"/>')
    for a, b in ((181, 206), (243, 273), (310, 335)):
        body.append(f'<rect x="{a - 5}" y="{T_TOP - 2}" width="{b - a + 10}" height="28" fill="#f2b890"/>')
    body.append(f'<rect x="{TX0 + 26}" y="396" width="{TX2 - TX0 - 32}" height="{T_TOP - 396}" fill="#c4907e"/>')
    body.append(f'<rect x="{TX0 + 26}" y="396" width="{TX1 - TX0 - 26}" height="{T_TOP - 396}" fill="#6e4a62"/>')
    for a, b in ((181, 206), (243, 273), (310, 335)):
        body.append(f'<path fill="#f2b890" d="{poly([(a, 396), (b, 396), (b - 3, 388), (a + 3, 388)])}"/>')
    # belt course at the roadway
    body.append(f'<rect x="{TX0 - 18}" y="938" width="{TX2 - TX0 + 22}" height="14" fill="#a87a72"/>')
    # the sunlit corner and right edge
    body.append(f'<path stroke="#ffcf9a" stroke-width="2.4" opacity=".85" d="M{TX2} {T_TOP + 6}V886"/>')
    body.append(f'<path stroke="#ffcf9a" stroke-width="1.4" opacity=".5" d="M{TX1} {T_TOP}V886"/>')
    if not CARD:
        course = "".join(f"M{TX0 + 22} {y}H{TX1}" for y in range(T_TOP + 30, H, 26))
        body.append(f'<path fill="none" stroke="#3a2848" stroke-width="1" opacity=".35" d="{course}"/>')
        # sunset breath on the lit face
        body.append(f'<rect class="{swell(m, "bkbr", 160, 0, .25, steps=32)}" opacity="0" x="{TX1}" y="{T_TOP}" width="{TX2 - TX1 + 4}" height="{886 - T_TOP}" fill="#ffb07a"/>')
        # the flag on the tower top: two frames
        fx, fy = 258, 350
        a_ = f'<path fill="#f2efe8" d="M{fx} {fy}q11 3 22 0v13q-11 3-22 0z"/><path stroke="#b8323a" stroke-width="1.6" d="M{fx} {fy + 3}q11 3 22 0M{fx} {fy + 8}q11 3 22 0"/><rect x="{fx}" y="{fy}" width="9" height="7" fill="#2a3a7a"/>'
        b_ = f'<path fill="#f2efe8" d="M{fx} {fy}q11 -3 22 0v13q-11 -3-22 0z"/><path stroke="#b8323a" stroke-width="1.6" d="M{fx} {fy + 3}q11 -3 22 0M{fx} {fy + 8}q11 -3 22 0"/><rect x="{fx}" y="{fy}" width="9" height="7" fill="#2a3a7a"/>'
        body.append(f'<path stroke="#3a2848" stroke-width="2" d="M{fx} 388V{fy - 2}"/>' + cycle(m, "bkfg", 2, 3, [a_, b_]))

def pilings(m, body, rng):
    """not pilings, which belong south of the bridge: a dark riprap bank along the bottom and, as the nod,
    Jane's Carousel in its glowing glass pavilion at the tower's foot."""
    pts = [(XL, H + 10), (XL, 1130)]
    for x in range(XL, XR + 40, 40):
        t = abs(x - 960) / 1360
        y = 1190 - 60 * t * t + rng.uniform(-6, 6)
        pts.append((x, y))
    pts += [(XR, 1130), (XR, H + 10)]
    body.append(f'<path fill="#140f22" d="{poly(pts)}"/>')
    rocks = "".join(f"M{x:.0f} {1185 - 55 * (abs(x - 960) / 1360) ** 2 + rng.uniform(-4, 10):.0f}q8 -8 16 0" for x in [rng.uniform(XL, XR) for _ in range(0 if CARD else 60)])
    if rocks:
        body.append(f'<path fill="none" stroke="#2a2038" stroke-width="2" d="{rocks}"/>')
    # Jane's Carousel: a glass box with a dark frame, warm panes, the carousel's canopy inside
    x0, x1, y0, y1 = 190, 330, 1120, 1200
    body.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="#1a1428"/>')
    panes = "".join(f"M{x} {y0 + 6}h{14}v{y1 - y0 - 12}h-14z" for x in range(x0 + 6, x1 - 10, 18))
    body.append(f'<path fill="#ffcf9a" opacity=".5" d="{panes}"/>')
    body.append(f'<path fill="#ffe2b8" opacity=".7" d="M{(x0 + x1) / 2 - 40} {y0 + 30}q40 -22 80 0z"/><path stroke="#ffe2b8" stroke-width="2" opacity=".6" d="M{(x0 + x1) / 2} {y0 + 30}V{y1 - 10}"/>')
    if not CARD:
        body.append(f'<rect class="{swell(m, "bkcar", 40, .15, .35, steps=10)}" opacity=".15" x="{x0 - 10}" y="{y0 - 6}" width="{x1 - x0 + 20}" height="{y1 - y0 + 6}" fill="#ffcf9a"/>')

def scene(m: Motion):
    rng = random.Random(41)
    defs, body = [], []
    sky(m, defs, body, rng)
    skyline(m, defs, body, rng)
    river(m, defs, body, rng)
    if not CARD:
        ferry(m, body)
    cables(m, defs, body)
    deck(m, defs, body)
    if CARD:
        x, y = 1660, Y_D
        body.append(f'<g fill="none" stroke="#15111d" stroke-width="2.4"><circle cx="{x}" cy="{y - 10}" r="9"/><circle cx="{x + 30}" cy="{y - 10}" r="9"/>'
                    f'<path d="M{x} {y - 10}l12 0 10-14H{x + 7}l5 14M{x + 30} {y - 10}l-6-17" /><path stroke-width="6" stroke-linecap="round" d="M{x + 7} {y - 28}l13-12M{x + 9} {y - 26}l4 14"/>'
                    f'<circle cx="{x + 23}" cy="{y - 44}" r="4" fill="#15111d"/></g>')
        info = {}
    else:
        g, info = rider_ride(m, Y_D, XL, XR, scale=30, step=11, name="bkr", rim="#ffb48a", rest_x=1790)
        body.append(g)
    railing_and_lamps(m, body)
    tower(m, defs, body)
    pilings(m, body, rng)
    return defs, body, info
