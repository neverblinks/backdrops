"""Bixby Creek Bridge, Big Sur, at sunset: the build scene.

Camera inland, low on Old Coast Road, looking west down the canyon on a June evening. The deck runs level across
the upper middle against open sky; the open-spandrel arch hangs below it, backlit, with the sun half-set on the sea
inside the arch opening. Interlocking canyon spurs with fog between them fall to a wedge of sea, a beach and surf.
On the left Highway 1 runs on to its bench under the orange road cut and Hurricane Point's hazy ridge; the rider rides
north (left to right) toward the sun, on a loop. Scale 10.5 units a metre (the rider ~2.7x life size).
"""
from __future__ import annotations

import math
import random

from bridges import H, XL, XR, Motion, cycle, hstops, rgrad, rider_ride, slide, swell, vgrad
from svglib import cloud, poly, polys

Y_D = 500                      # the roadway
GIRDER = 18
HORIZON = 880
SUN = (1800, 880)
ARCH = (1400, 515)             # centre x, half span
CROWN, SPRING = 535, 925
PIERS = ((785, 885), (1915, 2015))
PIER_FOOT = 1040
CARD = False

CONC, CONC_D, CONC_FAR, RIM = "#4f4a78", "#37325a", "#3d3862", "#ffc890"


def arch_y(x):
    t = (x - ARCH[0]) / ARCH[1]
    return CROWN + (SPRING - CROWN) * t * t


def ridge(points, base):
    """A filled silhouette through points (cosine-smoothed), closed down to `base`."""
    out = []
    for (xa, ya), (xb, yb) in zip(points, points[1:]):
        n = max(2, int(abs(xb - xa) / 24))
        for i in range(n):
            t = i / n
            u = (1 - math.cos(math.pi * t)) / 2
            out.append((xa + (xb - xa) * t, ya + (yb - ya) * u))
    out.append(points[-1])
    # taper: the end away from the frame edge slopes down to the base instead of cutting straight down
    (x_end, y_end), (x_start, _) = points[-1], points[0]
    run = (base - y_end) * 0.9 * (1 if x_end > x_start else -1)
    return out + [(x_end + run, base), (x_start, base)]


# ------------------------------------------------------------------ sky, sun, fog bank, sea

def sky(m, defs, body, rng):
    defs.append(vgrad("bx-sky", [(0, "#171735"), (250 / HORIZON, "#2e2a57"), (500 / HORIZON, "#5e4e7c"), (700 / HORIZON, "#684e78"), (1, "#6c4a70")], 0, HORIZON))   # the band is navy, not black
    defs.append(rgrad("bx-sun", SUN[0], SUN[1], 420, [(0, "#ffe9b8", 1), (0.08, "#ffb877", 0.9), (0.22, "#f0806a", 0.5), (0.42, "#b05a80", 0.14), (0.7, "#b05a80", 0.03), (1, "#b05a80", 0)], sy=0.7))
    x0, sw = XL, XR - XL
    body.append(f'<rect x="{x0}" width="{sw}" height="{HORIZON + 4}" fill="url(#bx-sky)"/>')
    body.append(f'<rect x="{x0}" y="{SUN[1] - 480}" width="{sw}" height="{H - SUN[1] + 480}" fill="url(#bx-sun)"/>')
    # three thin cloud bars above y 380, warm undersides toward the sun
    if not CARD:
        defs.append(hstops("bx-cloud", ((XL, "#5a4a7c", 1), (1300, "#6a5080", 1), (1750, "#f0a08a", 1), (XR, "#e89a8a", 1))))
        bars = [cloud(rng, cx, cy, ln, th) for cx, cy, ln, th in ((1500, 330, 1500, 9), (900, 230, 1200, 7), (2000, 160, 1000, 6))]
        body.append(f'<path fill="url(#bx-cloud)" opacity=".55" d="{polys(bars)}"/>')
        st = []
        for i in range(70):
            x, y = rng.uniform(XL, 1300), rng.uniform(70, 260)
            if math.hypot(x - SUN[0], y - SUN[1]) < 1100:
                continue
            st.append(f"M{x:.0f} {y:.0f}h.4")
        body.append(f'<path class="{swell(m, "bxst", 40, .2, .6, steps=10)}" opacity=".2" stroke="#efe6ff" stroke-width="2" stroke-linecap="round" d="{"".join(st)}"/>')
    # the sun, half-set on the sea, and its slow halo
    body.append(f'<circle cx="{SUN[0]}" cy="{SUN[1]}" r="34" fill="#fff0c8"/>')
    halo = f'<circle cx="{SUN[0]}" cy="{SUN[1]}" r="58" fill="#ffd8a0" opacity=".3"/>'
    body.append(halo.replace("<circle ", f'<circle class="{swell(m, "bxsh", 160, .2, .45, steps=32)}" ') if not CARD else halo)
    # the offshore fog bank on the horizon, rose along its top toward the sun; two streaks across the disc
    defs.append(hstops("bx-fogtop", ((XL, "#5a4a7c", 1), (1560, "#5e4a7a", 1), (1720, "#f0a08a", 1), (XR, "#d88a8a", 1))))
    bank = [(XL, HORIZON + 2), (XL, 858)] + [(x, 846 + 8 * math.sin(x / 140) + 5 * math.sin(x / 47)) for x in range(XL, XR + 30, 30)] + [(XR, HORIZON + 2)]
    body.append(f'<path fill="#5a4a7c" d="{poly(bank)}"/>')
    top = [(x, 846 + 8 * math.sin(x / 140) + 5 * math.sin(x / 47)) for x in range(XL, XR + 30, 30)]
    body.append(f'<path fill="none" stroke="url(#bx-fogtop)" stroke-width="3" d="M{top[0][0]:.0f} {top[0][1]:.0f}' + "".join(f"L{x:.0f} {y:.0f}" for x, y in top[1:]) + '"/>')
    # the sun shows through the thin bank: redraw the disc's top, then two fog streaks over it
    body.append(f'<path fill="#fff0c8" d="M{SUN[0] - 34} {SUN[1]}a34 34 0 0 1 68 0z" opacity=".85"/>')
    body.append(f'<path stroke="#7a5a86" stroke-width="3" opacity=".7" d="M{SUN[0] - 70} 864h140M{SUN[0] - 60} 873h120"/>')


def canyon_floor(body, defs):
    """The canyon below the sea line: dark ground and creek-mouth fog, under the spurs."""
    # fog slabs are soft at top and bottom (a hard edge across the picture reads as a stripe)
    defs.append('<linearGradient id="bx-fog" x2="0" y2="1"><stop offset="0" stop-color="#5a4a7c" stop-opacity="0"/>'
                '<stop offset=".5" stop-color="#5a4a7c"/><stop offset="1" stop-color="#5a4a7c" stop-opacity="0"/></linearGradient>')
    body.append(f'<rect x="{XL}" y="1012" width="{XR - XL}" height="{H - 1012}" fill="#1d1838"/>')
    body.append(f'<rect x="{XL}" y="992" width="{XR - XL}" height="100" fill="url(#bx-fog)" opacity=".6"/>')


def sea(m, defs, body, rng):
    defs.append(vgrad("bx-sea", [(0, "#4a4470"), (1, "#2a2850")], HORIZON, 1020))
    body.append(f'<rect x="700" y="{HORIZON}" width="1620" height="140" fill="url(#bx-sea)"/>')
    sets = [[], [], []]
    for y in range(HORIZON + 4, 1010, 6 if not CARD else 12):
        for _ in range(1 if CARD else 3):
            x = SUN[0] + rng.gauss(0, 14 + (y - HORIZON) * 0.35)
            sets[0 if CARD else rng.randrange(3)].append(f"M{x:.0f} {y}h{rng.randint(6, 24)}")
    kg = m.keyframes("bxgl", [(0, "opacity:.95"), (0.33, "opacity:.3"), (0.66, "opacity:.65"), (1, "opacity:.95")])
    for i, s in enumerate(sets):
        if s:
            body.append(f'<path class="{m.use(kg, 1.5, -0.5 * i)}" stroke="#ffe0a8" stroke-width="2.2" d="{"".join(s)}"/>')


# ------------------------------------------------------------------ land: ridge, road cut, spurs, fog, beach

def land_back(m, defs, body, rng):
    # Hurricane Point's hazy ridge, left, cresting y 380 near x -200 and dropping below the deck by x 250
    body.append(f'<path fill="#5c4f80" d="{poly(ridge([(XL, 420), (-200, 380), (60, 450), (250, 520), (420, 600), (700, 720)], 1012))}"/>')
    # the north knoll on the far right (the ultrawide view), with two small cypresses
    body.append(f'<path fill="#4a4270" d="{poly(ridge([(2150, 760), (2240, 600), (XR, 560)], HORIZON + 40))}"/>')
    if not CARD:
        for cx, cy, s in ((2230, 606, 1.0), (2280, 590, .8)):
            body.append(f'<path fill="#2a2448" d="M{cx} {cy}c{-30 * s} -6 {-40 * s} -26 {-14 * s} -40c{20 * s} -10 {44 * s} -2 {52 * s} 14c{8 * s} 16 {-14 * s} 28 {-38 * s} 26z"/>')
    # spur fills: lighter on top, sinking into shadow below (depth); scrub texture on the slopes
    defs.append(vgrad("bx-far", [(0, "#4e4674"), (1, "#352e5a")], 560, 1050))
    defs.append(vgrad("bx-mid", [(0, "#3a325c"), (1, "#241e40")], 500, 1150))
    defs.append(vgrad("bx-near", [(0, "#262042"), (1, "#16122a")], 880, H))
    # the far spur pair, its tips reaching the sea: the wedge of ocean opens between x 1250 and 2150
    far_l = ridge([(XL, 700), (150, 650), (420, 610), (800, 760), (1100, 880), (1250, 990)], H + 10)
    body.append(f'<path fill="url(#bx-far)" d="{poly(far_l)}"/>')
    body.append(f'<path fill="url(#bx-far)" d="{poly(ridge([(XR, 640), (2250, 760), (2150, 900)], H + 10))}"/>')
    if not CARD:
        d = []
        for _ in range(240):
            x = rng.uniform(420, 1250)
            top = 600 + (x - 420) * 0.47
            y = rng.uniform(top + 8, min(1010, top + 260))
            d.append(f"M{x:.0f} {y:.0f}h{rng.randint(0, 6)}")
        body.append(f'<path stroke="#2e2850" stroke-width="6" stroke-linecap="round" opacity=".55" d="{"".join(d)}"/>')
        body.append('<path fill="none" stroke="#e8a878" stroke-width="1.4" opacity=".35" d="M800 760Q960 820 1100 880T1250 990"/>')
    # fog slab between the far and middle spurs (breathing)
    fog = f'<rect x="{XL}" y="880" width="{XR - XL}" height="110" fill="url(#bx-fog)" opacity=".35"/>'
    body.append(fog.replace("<rect ", f'<rect class="{swell(m, "bxf1", 240, .2, .45, steps=30)}" ') if not CARD else fog)


def beach(m, defs, body, rng):
    body.append(f'<path fill="#6a5070" d="{poly([(1540, 1014), (1580, 990), (1700, 984), (1880, 990), (1920, 1014)])}"/>')
    body.append('<path fill="#2a2448" d="M1620 994q12 -12 26 0z"/>')            # one low rock
    if not CARD:
        lines = []
        for i in range(3):
            y = 990 + 7 * i
            lines.append(f'<path fill="none" stroke="#f4e2cc" stroke-width="2" d="M{1570 + 12 * i} {y}q80 -5 160 0t160 0"/>')
        k = m.keyframes("bxsurf", [(0, "opacity:0"), (0.15, "opacity:.9"), (0.4, "opacity:.5"), (0.7, "opacity:0"), (1, "opacity:0")])
        body.append("".join(l.replace("<path ", f'<path class="{m.use(k, 6, -2 * i)}" opacity="0" ') for i, l in enumerate(lines)))


def land_front(m, defs, body, rng):
    # the middle spur pair, then fog, then the near pair (canyon walls), crest light on the sun-facing slopes
    mid_l = ridge([(XL, 700), (300, 760), (700, 900), (1150, 1080)], H + 10)
    mid_r = ridge([(XR, 820), (2150, 900), (1980, 1060)], H + 10)
    body.append(f'<path fill="url(#bx-mid)" d="{poly(mid_l)}"/><path fill="url(#bx-mid)" d="{poly(mid_r)}"/>')
    body.append('<path fill="none" stroke="#e8a878" stroke-width="1.6" opacity=".55" d="M700 900Q960 990 1150 1080"/>')
    fog = f'<rect x="{XL}" y="990" width="{XR - XL}" height="120" fill="url(#bx-fog)" opacity=".3"/>'
    body.append(fog.replace("<rect ", f'<rect class="{swell(m, "bxf2", 320, .15, .4, phase_beats=100, steps=32)}" ') if not CARD else fog)
    near_l = ridge([(XL, 880), (300, 940), (600, 1060), (900, H + 10)], H + 10)
    near_r = ridge([(XR, 980), (2000, 1080), (1700, H + 10)], H + 10)
    body.append(f'<path fill="url(#bx-near)" d="{poly(near_l)}"/><path fill="url(#bx-near)" d="{poly(near_r)}"/>')
    body.append(f'<path fill="none" stroke="#e8a878" stroke-width="1.4" opacity=".4" d="M1700 {H}Q1850 1110 2000 1080"/>')
    if not CARD:
        scrub = "".join(f"M{x:.0f} {y:.0f}h{rng.randint(0, 5)}" for x, y in [(rng.uniform(XL, 880), rng.uniform(900, H)) for _ in range(260)] if y > 880 + (x - XL) * 0.12)
        body.append(f'<path stroke="#1c1834" stroke-width="7" stroke-linecap="round" opacity=".7" d="{scrub}"/>')


# ------------------------------------------------------------------ the road on land, Highway 1 traffic

def road_cut(m, defs, body):
    # the orange road cut behind the road at the south end, then Highway 1 on its bench, running onto the bridge
    body.append(f'<path fill="#7a4a50" d="{poly(ridge([(30, Y_D + 2), (90, Y_D - 50), (180, Y_D - 70), (250, Y_D - 40), (300, Y_D + 2)], Y_D + 2))}"/>')
    if not CARD:
        body.append(f'<path fill="none" stroke="#a8665a" stroke-width="1.4" opacity=".6" d="M70 {Y_D - 20}q40 -30 90 -40M120 {Y_D - 8}q50 -30 110 -36"/>')
    bench = ridge([(XL, Y_D + 24), (100, Y_D + 8), (305, Y_D + 4)], Y_D + 40)   # a narrow shelf under the road
    body.append(f'<path fill="url(#bx-mid)" d="{poly(bench)}"/>')
    # the road grade climbing Hurricane Point (a thin line on the ridge) and cars on it
    grade = f"M{XL} 430Q-100 470 120 {Y_D - 6}"
    body.append(f'<path fill="none" stroke="#3a3260" stroke-width="5" d="{grade}"/>')
    if not CARD:
        car_down = '<circle r="3.2" fill="#fff2cc"/><circle cx="6" r="2.4" fill="#fff2cc" opacity=".8"/>'
        g1, _ = slide(m, "bxc1", car_down, XL + 10, 120, 432, 3, extra_y=Y_D - 438)
        car_up = '<circle r="2.6" fill="#ff5a5a"/>'
        g2, _ = slide(m, "bxc2", car_up, 100, XL + 20, Y_D - 8, -2, extra_y=-(Y_D - 8 - 434))
        body.append(g1 + g2)


# ------------------------------------------------------------------ the bridge

def bridge(m, defs, body, rng):
    # approach bents (two columns with a tie), landing on the slopes at different heights
    def bent(x, foot, w=10):
        fill = CONC_D
        out = f'<path fill="{fill}" d="{poly([(x - 18, Y_D + GIRDER), (x - 18 + w, Y_D + GIRDER), (x - 16 + w, foot), (x - 20, foot)])}{poly([(x + 8, Y_D + GIRDER), (x + 8 + w, Y_D + GIRDER), (x + 10 + w, foot), (x + 6, foot)])}"/>'
        ties = "".join(f"M{x - 18} {y:.0f}h{36}" for y in [Y_D + GIRDER + (foot - Y_D) * f for f in (0.35, 0.7)] if y < foot - 20)
        return out + f'<path stroke="{fill}" stroke-width="6" d="{ties}"/>'
    for x, foot in ((465, 700), (625, 830), (2175, 820), (2335, 700)):
        body.append(bent(x, foot))
    # the far rib (darker, offset 8), its spandrel columns, cross-struts showing between the ribs
    def rib(off, depth_c, depth_s, fill):
        top, bot = [], []
        for i in range(61):
            x = ARCH[0] - ARCH[1] + 2 * ARCH[1] * i / 60
            t = (x - ARCH[0]) / ARCH[1]
            y = arch_y(x) - off
            d = depth_c + (depth_s - depth_c) * t * t
            top.append((x - off, y))
            bot.append((x - off, y + d))
        return top, bot
    ft, fb = rib(8, 16, 28, CONC_FAR)
    body.append(f'<path fill="{CONC_FAR}" d="{poly(ft + fb[::-1])}"/>')
    cols_x = [ARCH[0] + s * 86 * k for k in range(1, 6) for s in (-1, 1)]
    far_cols = "".join(poly([(x - 8 - 3.5, Y_D + GIRDER), (x - 8 + 3.5, Y_D + GIRDER), (x - 8 + 3.5, arch_y(x) - 6), (x - 8 - 3.5, arch_y(x) - 6)]) for x in cols_x)
    body.append(f'<path fill="{CONC_FAR}" d="{far_cols}"/>')
    struts = "".join(f"M{x - 8:.0f} {arch_y(x) - 8:.0f}L{x:.0f} {arch_y(x):.0f}" for x in range(ARCH[0] - ARCH[1] + 40, ARCH[0] + ARCH[1] - 30, 60))
    body.append(f'<path stroke="{CONC_FAR}" stroke-width="5" d="{struts}"/>')
    # the great piers: battered, a recessed panel, a heavier parapet block bayed out at deck level
    defs.append(vgrad("bx-pier", [(0, CONC), (1, CONC_D)], Y_D, PIER_FOOT))
    for a, b in PIERS:
        body.append(f'<path fill="url(#bx-pier)" d="{poly([(a, Y_D + GIRDER), (b, Y_D + GIRDER), (b + 10, PIER_FOOT), (a - 10, PIER_FOOT)])}"/>')
        body.append(f'<path fill="#2e2a50" opacity=".6" d="{poly([(a + 22, Y_D + 60), (b - 22, Y_D + 60), (b - 18, PIER_FOOT - 30), (a + 18, PIER_FOOT - 30)])}"/>')
        body.append(f'<rect x="{a - 8}" y="{Y_D - 22}" width="{b - a + 16}" height="{GIRDER + 30}" fill="{CONC}"/>')
        rim_op = 1.0 if a > 1500 else 0.35
        body.append(f'<path stroke="{RIM}" stroke-width="1.2" opacity="{rim_op}" d="M{b} {Y_D + GIRDER}L{b + 10} {PIER_FOOT}M{b + 8} {Y_D - 22}v{GIRDER + 30}"/>')
    # the near rib and its spandrel columns, ties on the two tallest each side
    nt, nb = rib(0, 16, 28, CONC)
    defs.append(vgrad("bx-rib", [(0, CONC), (1, CONC_D)], CROWN, SPRING + 30))
    body.append(f'<path fill="url(#bx-rib)" d="{poly(nt + nb[::-1])}"/>')
    near_cols = "".join(poly([(x - 3.5, Y_D + GIRDER), (x + 3.5, Y_D + GIRDER), (x + 3.5, arch_y(x) + 2), (x - 3.5, arch_y(x) + 2)]) for x in cols_x)
    body.append(f'<path fill="{CONC}" d="{near_cols}"/>')
    ties = "".join(f"M{x - 8 - 4:.0f} {(Y_D + arch_y(x)) / 2:.0f}H{x + 4:.0f}" for x in cols_x if abs(x - ARCH[0]) > 300)
    body.append(f'<path stroke="{CONC}" stroke-width="5" d="{ties}"/>')
    # the backlit rim on right-hand edges: full past x 1500, a third left of x 1000
    def rop(x):
        return 1.0 if x > 1500 else (0.35 if x < 1000 else 0.35 + 0.65 * (x - 1000) / 500)
    rims = {}
    for x in cols_x:
        rims.setdefault(round(rop(x + 3.5), 1), []).append(f"M{x + 3.5:.0f} {Y_D + GIRDER}V{arch_y(x):.0f}")
    seg = list(zip(nt, nt[1:]))
    for (xa, ya), (xb, yb) in seg:
        if xb > ARCH[0]:
            rims.setdefault(round(rop(xa), 1), []).append(f"M{xa:.0f} {ya:.0f}L{xb:.0f} {yb:.0f}")
    body.append("".join(f'<path stroke="{RIM}" stroke-width="1.2" opacity="{o}" d="{"".join(ds)}"/>' for o, ds in rims.items()))
    # the deck: slab and girder from the abutment (x 305) on past the right edge
    body.append(f'<rect x="305" y="{Y_D}" width="{XR - 305}" height="{GIRDER}" fill="{CONC}"/>')
    body.append(f'<rect x="305" y="{Y_D + GIRDER - 4}" width="{XR - 305}" height="4" fill="{CONC_D}"/>')
    body.append(f'<path stroke="#ffb88a" stroke-width="1.2" opacity=".35" d="M305 {Y_D + GIRDER}H{ARCH[0]}"/>')   # a faint warm line on the soffit
    body.append(f'<rect x="290" y="{Y_D - 6}" width="22" height="{GIRDER + 40}" fill="{CONC}"/>')                   # the abutment


def balustrade(body):
    """Posts every 30 and six narrow round-arched slots per panel, 10 tall, from the abutment on; a low wall on land."""
    y0 = Y_D - 12
    x0 = 305
    rail = f'<rect x="{x0}" y="{y0 - 3}" width="{XR - x0}" height="4" fill="{CONC}"/>'
    slots = "".join(f"M{x + 2 + 4.2 * k:.1f} {Y_D}v-6a1.4 1.4 0 0 1 2.8 0v6z" for x in range(x0, XR, 30) for k in range(6)) if not CARD else ""
    panel = f'<path fill="{CONC}" fill-rule="evenodd" d="M{x0} {y0}H{XR}V{Y_D}H{x0}z{slots}"/>'
    body.append(rail + panel)
    body.append(f'<path stroke="{RIM}" stroke-width="1" opacity=".5" d="M1400 {y0 - 3}H{XR}"/>')
    body.append(f'<rect x="{XL}" y="{Y_D - 8}" width="{305 - XL}" height="8" fill="#3a3260"/>')


# ------------------------------------------------------------------ life: pelicans, condor; foreground, cypress, the cabin

def birds(m, body):
    def pelican(x, y, up):
        w = -3 if up else 2
        return f"M{x - 9} {y + w}q4 -4 9 0q4 -4 9 0"
    a = "".join(pelican(18 * i, -3 * i, True) for i in range(5))
    b = "".join(pelican(18 * i, -3 * i, False) for i in range(5))
    flap = cycle(m, "bxpf", 2, 4, [f'<path d="{a}"/>', f'<path d="{b}"/>'])
    inner = f'<g fill="none" stroke="#231e3c" stroke-width="2" stroke-linecap="round">{flap}</g>'
    g, _ = slide(m, "bxpe", inner, XR + 40, XL - 160, 812, -3, extra_y=-20)
    body.append(g)
    condor = '<path fill="#1c1830" d="M-30 0q15 -6 30 -2q15 -4 30 2l-4 3-6 -1-4 3-6-2-10 2-10-2-6 2-4-3-6 1z"/>'
    g2, _ = slide(m, "bxco", condor, -300, 900, 190, 1, extra_y=40)
    body.append(g2)


def foreground(m, defs, body, rng):
    # the foreground slope, bottom left, and one wind-sheared Monterey cypress (top below y 560)
    body.append(f'<path fill="#17132a" d="{poly(ridge([(XL, 1020), (200, 1060), (500, 1150), (700, H + 10)], H + 10))}"/>')
    body.append('<g transform="translate(-130 330) scale(.72)">')   # smaller, further left: frames the edge
    tx, ty = 150, 1110
    body.append(f'<path fill="#120f22" d="M{tx - 6} {H}V{ty}q-2 -80 -30 -150q20 30 36 90q10 -70 60 -120q-30 70 -40 180V{H}z"/>')
    blobs = []
    for cx, cy, rx, ry in ((40, 600, 120, 34), (170, 572, 150, 30), (300, 600, 110, 26), (120, 640, 90, 26), (240, 640, 80, 22), (-40, 640, 80, 26)):
        blobs.append(f"M{cx - rx} {cy}q{rx * 0.3} {-ry} {rx} {-ry}q{rx * 0.7} 0 {rx} {ry}q{-rx * 0.4} {ry * 0.6} {-rx} {ry * 0.5}q{-rx * 0.6} 0 {-rx} {-ry * 0.5}z")
    body.append(f'<path fill="#120f22" d="{"".join(blobs)}"/>')
    body.append('<path fill="none" stroke="#120f22" stroke-width="7" d="M150 980Q120 760 60 640M150 900Q200 760 260 650M150 1000Q140 820 170 600"/>')
    body.append('</g>')
    # the nod: a cabin down in the canyon with one lit window and a thread of smoke
    cx, cy = 250, 1120
    body.append(f'<path fill="#0f0c1e" d="{poly([(cx - 26, cy + 18), (cx - 26, cy), (cx, cy - 16), (cx + 26, cy), (cx + 26, cy + 18)])}"/>')
    body.append(f'<rect x="{cx - 8}" y="{cy + 3}" width="9" height="8" fill="#ffcf8a"/>')
    if not CARD:
        smoke = f'<path fill="none" stroke="#6a5a80" stroke-width="2.4" stroke-linecap="round" opacity=".5" d="M{cx + 14} {cy - 14}q-8 -16 4 -30t-2 -34t6 -30"/>'
        body.append(smoke.replace("<path ", f'<path class="{swell(m, "bxsm", 64, .15, .5, steps=16)}" ', 1))


def scene(m: Motion):
    rng = random.Random(29)
    defs, body = [], []
    sky(m, defs, body, rng)
    sea(m, defs, body, rng)
    canyon_floor(body, defs)
    land_back(m, defs, body, rng)
    beach(m, defs, body, rng)
    if not CARD:
        birds(m, body)
    land_front(m, defs, body, rng)
    bridge(m, defs, body, rng)
    road_cut(m, defs, body)
    if CARD:
        x, y = 1650, Y_D
        body.append(f'<g fill="none" stroke="#15111d" stroke-width="2.4"><circle cx="{x}" cy="{y - 10}" r="9"/><circle cx="{x + 30}" cy="{y - 10}" r="9"/>'
                    f'<path d="M{x} {y - 10}l12 0 10-14H{x + 7}l5 14M{x + 30} {y - 10}l-6-17" /><path stroke-width="6" stroke-linecap="round" d="M{x + 7} {y - 28}l13-12M{x + 9} {y - 26}l4 14"/>'
                    f'<circle cx="{x + 23}" cy="{y - 44}" r="4" fill="#15111d"/></g>')
        info = {}
    else:
        g, info = rider_ride(m, Y_D, XL, XR, scale=30, step=11, name="bxr", rim=RIM, rest_x=1650)
        body.append(g)
    balustrade(body)
    foreground(m, defs, body, rng)
    return defs, body, info
