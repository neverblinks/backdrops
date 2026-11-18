"""The Atlantic Ocean Road (Storseisundet), Norway, at Nordic blue hour: the build scene.

The postcard view from a knoll above the road: the road sweeps in big from the bottom left, bends right across the
picture and curls left up the hump of Storseisundet bridge, whose crest ends in the sky against the last afterglow.
The rider rides AWAY along it on a 96 s loop, shrinking from ~100 units to a speck, his view turning from side-on to
three-quarter rear; in the gap a car comes over the hump toward us. Stemshesten's flat top on the left, skerries,
a lantern hut, Hurtigruten on the horizon, a falu-red naust. Cold palette; the warmth only right of x 1650.
"""
from __future__ import annotations

import math
import random

from bridges import BEAT, H, POSES, XL, XR, Motion, Rider, _runs_path, _same, hstops, rgrad, rider_rows, rider_rows_view, slide, swell, vgrad
from svglib import cloud, poly, polys

HORIZON = 600
GLOW = (1840, 590)
CARD = False
# road centreline control points: (x, y, road width, rider height, time s)
P = [(-400, 1130, 150, 100, 0), (60, 1092, 118, 90, 6), (520, 1046, 88, 70, 12), (1000, 992, 60, 50, 19),
     (1420, 915, 40, 36, 27), (1720, 832, 27, 26, 35), (1880, 720, 18, 20, 44), (1860, 610, 11, 15, 54), (1782, 512, 6, 12, 66)]
LOOP = 96.0


def spline(u):
    """Catmull-Rom through P at parameter u in [0, len(P)-1]: (x, y, width, rider height, time)."""
    n = len(P) - 1
    u = max(0.0, min(n - 1e-9, u))
    i = int(u)
    t = u - i
    p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, n)]
    out = []
    for k in range(5):
        a, b, c, d = p0[k], p1[k], p2[k], p3[k]
        if k < 2:
            out.append(0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t ** 3))
        else:
            out.append(b + (c - b) * t)
    return out


def road_samples(n=240):
    return [spline((len(P) - 1) * i / n) for i in range(n + 1)]


def at_time(t):
    """The rider's (x, y, height, heading dx, dy) at time t along the road (piecewise-linear time between knots)."""
    for i in range(len(P) - 1):
        if P[i][4] <= t <= P[i + 1][4]:
            u = i + (t - P[i][4]) / (P[i + 1][4] - P[i][4])
            x, y, w, h, _ = spline(u)
            x2, y2, *_ = spline(min(u + 0.02, len(P) - 1))
            return x, y, h, x2 - x, y2 - y
    x, y, w, h, _ = spline(len(P) - 1)
    return x, y, h, 0, -1


# ------------------------------------------------------------------ sky, sea, land

def sky(m, defs, body, rng):
    defs.append(vgrad("cw-sky", [(0, "#0b1626"), (0.45, "#12304a"), (0.85, "#21506a"), (1, "#2b5f7a")], 0, HORIZON))
    defs.append(rgrad("cw-glow", GLOW[0], GLOW[1], 620, [(0, "#f2c79a", .95), (0.1, "#e8a66b", .7), (0.3, "#5fa3a8", .35), (0.6, "#2b5f7a", .12), (1, "#2b5f7a", 0)], sy=0.45))
    x0, sw = XL, XR - XL
    body.append(f'<rect x="{x0}" width="{sw}" height="{HORIZON + 2}" fill="url(#cw-sky)"/>')
    body.append(f'<rect x="{x0}" y="{GLOW[1] - 300}" width="{sw}" height="{H - GLOW[1] + 300}" fill="url(#cw-glow)"/>')
    # the afterglow strip low on the horizon, right of x 1650 only
    defs.append(hstops("cw-strip", ((XL, "#f2c79a", 0), (1600, "#f2c79a", 0), (1760, "#f2c79a", .7), (XR, "#f2c79a", .55))))
    body.append(f'<rect x="{x0}" y="{HORIZON - 26}" width="{sw}" height="22" fill="url(#cw-strip)"/>')
    if not CARD:
        st = []
        for _ in range(90):
            x, y = rng.uniform(XL, 1200), rng.uniform(70, 300)
            st.append(f"M{x:.0f} {y:.0f}h.4")
        body.append(f'<path class="{swell(m, "cwst", 40, .25, .7, steps=10)}" opacity=".25" stroke="#dfeaf2" stroke-width="2" stroke-linecap="round" d="{"".join(st)}"/>')
    # heavy blue stratus; warm undersides only toward the afterglow
    defs.append(hstops("cw-under", ((XL, "#2a4a62", .5), (1500, "#2a4a62", .5), (1750, "#e8a66b", .8), (XR, "#f2c79a", .7))))
    shapes, unders = [], []
    for cx, cy, ln, th in ((700, 210, 1600, 22), (1500, 330, 1500, 18), (300, 420, 1100, 14), (2000, 450, 900, 12), (1200, 500, 900, 9)) if not CARD else ((700, 210, 1600, 22), (1500, 330, 1500, 18)):
        c = cloud(rng, cx, cy, ln, th)
        shapes.append(c)
        unders.append(c[len(c) // 2:])
    body.append(f'<path fill="#183650" d="{polys(shapes)}"/>')
    body.append(f'<path fill="none" stroke="url(#cw-under)" stroke-width="3" d="{"".join("M" + "L".join(f"{x:.0f} {y:.0f}" for x, y in u) for u in unders)}"/>')


def far_land(m, defs, body, rng):
    # the pale far range along the horizon, then Stemshesten's flat-topped mass on the left with a dusting of snow
    rng2 = random.Random(5)
    far = [(XL, HORIZON + 2)] + [(x, HORIZON - 18 - 22 * math.sin(x / 260) ** 2 - rng2.uniform(0, 8)) for x in range(XL, XR + 40, 40)] + [(XR, HORIZON + 2)]
    body.append(f'<path fill="#294a62" d="{poly(far)}"/>')
    stem = [(240, HORIZON + 2), (360, 540), (500, 450), (600, 412), (900, 402), (1010, 416), (1130, 478), (1260, 560), (1330, HORIZON + 2)]
    body.append(f'<path fill="#16283a" d="{poly(stem)}"/>')
    # snow on the flat top's rim, and four tapered gullies below it (as thin 2.2-unit lines they read as scratches)
    body.append('<path fill="none" stroke="#5b7f97" stroke-width="2.2" opacity=".55" d="M600 413L900 403L1010 417"/>')
    body.append('<path fill="#5b7f97" opacity=".32" d="M636 412l9 0l-36 34zM716 409l8 0l-27 32zM816 405l9 0l-31 36zM926 406l9 0l12 30z"/>')
    # the low cloud bank resting behind the column's right half
    body.append(f'<path fill="#1a3044" d="{poly([(1240, HORIZON + 2), (1260, 572), (1330, 556), (1450, 552), (1560, 562), (1620, 580), (1666, 589), (1692, 594), (1708, HORIZON + 2)])}"/>')
    # horizon skerries, low and whale-backed
    sk = []
    for x, w, h in ((1500, 60, 6), (1640, 40, 5), (2060, 90, 9), (2200, 50, 6), (-300, 70, 7), (-120, 40, 5), (1950, 30, 4)):
        sk.append([(x - w / 2, HORIZON + 3)] + [(x - w / 2 + w * t, HORIZON + 3 - h * math.sin(math.pi * t) ** .6) for t in [i / 8 for i in range(1, 8)]] + [(x + w / 2, HORIZON + 3)])
    body.append(f'<path fill="#1a2a3a" d="{polys(sk)}"/>')


def sea(m, defs, body, rng):
    defs.append(vgrad("cw-sea", [(0, "#21506a"), (0.06, "#173a52"), (0.5, "#12304a"), (1, "#0e2233")], HORIZON, H))
    defs.append(rgrad("cw-sheen", GLOW[0], HORIZON + 10, 520, [(0, "#7fb6c4", .55), (0.3, "#5fa3a8", .25), (1, "#5fa3a8", 0)], sy=0.5))
    x0, sw = XL, XR - XL
    body.append(f'<rect x="{x0}" y="{HORIZON}" width="{sw}" height="{H - HORIZON}" fill="url(#cw-sea)"/>')
    body.append(f'<rect x="{x0}" y="{HORIZON}" width="{sw}" height="{H - HORIZON}" fill="url(#cw-sheen)"/>')
    # a sheen on the sound at the left margin (a weaker cloud-break)
    if not CARD:
        rip = "".join(f"M{rng.uniform(XL, XR):.0f} {rng.uniform(HORIZON + 6, H):.0f}h{rng.randint(20, 90)}" for _ in range(120))
        body.append(f'<path stroke="#2e5a74" stroke-width="1.4" opacity=".35" d="{rip}"/>')
    sets = [[], [], []]
    for y in range(HORIZON + 4, 780, 6 if not CARD else 12):
        for _ in range(1 if CARD else 3):
            x = GLOW[0] + rng.gauss(0, 30 + (y - HORIZON) * 0.6)
            if x < 1660:
                continue
            sets[0 if CARD else rng.randrange(3)].append(f"M{x:.0f} {y}h{rng.randint(6, 22)}")
    kg = m.keyframes("cwgl", [(0, "opacity:.9"), (0.33, "opacity:.3"), (0.66, "opacity:.6"), (1, "opacity:.9")])
    for i, s in enumerate(sets):
        if s:
            body.append(f'<path class="{m.use(kg, 1.5, -0.5 * i)}" stroke="#f4d9b0" stroke-width="2" d="{"".join(s)}"/>')
    # a lighter haze lane on the water behind the road where it crosses the text column (the rider reads against it)
    defs.append(rgrad("cw-lane", 950, 930, 900, [(0, "#2a5c78", .5), (0.6, "#2a5c78", .25), (1, "#2a5c78", 0)], sy=0.11))
    body.append('<rect x="0" y="820" width="1900" height="220" fill="url(#cw-lane)"/>')


def islets(m, defs, body, rng):
    """Middle islets with heather either side of the road, the naust on the left, the lantern hut on a skerry."""
    def blob(cx, cy, w, h):
        return [(cx - w / 2, cy)] + [(cx - w / 2 + w * t, cy - h * math.sin(math.pi * t) ** .7) for t in [i / 10 for i in range(1, 10)]] + [(cx + w / 2, cy)]
    mids = [blob(150, 790, 420, 60), blob(-260, 760, 300, 40), blob(780, 880, 380, 36), blob(2120, 700, 420, 40), blob(1400, 990, 300, 30)]
    body.append(f'<path fill="#111c29" d="{polys(mids)}"/>')
    if not CARD:
        heather = "".join(f"M{x:.0f} {y:.0f}h{rng.randint(1, 4)}" for x, y in [(rng.uniform(-40, 340), rng.uniform(745, 785)) for _ in range(60)])
        body.append(f'<path stroke="#4a2c46" stroke-width="5" stroke-linecap="round" opacity=".55" d="{heather}"/>')
    # the falu-red naust with white corner boards and one lit window
    nx, ny = 150, 752
    body.append(f'<path fill="#7a2620" d="{poly([(nx - 34, ny + 10), (nx - 34, ny - 14), (nx, ny - 36), (nx + 34, ny - 14), (nx + 34, ny + 10)])}"/>')
    body.append(f'<path fill="none" stroke="#c9ccd0" stroke-width="2" d="M{nx - 34} {ny + 10}V{ny - 14}L{nx} {ny - 36}L{nx + 34} {ny - 14}V{ny + 10}"/>')
    body.append(f'<rect x="{nx + 8}" y="{ny - 8}" width="9" height="9" fill="#ffcf8a"/>')
    # the lantern hut on a skerry: white, a red cap, a light occulting every 6 s
    hx, hy = 2050, 636
    body.append(f'<path fill="#1a2a3a" d="{poly(blob(hx, hy + 8, 120, 14))}"/>')
    body.append(f'<rect x="{hx - 7}" y="{hy - 14}" width="14" height="20" fill="#d8dde2"/><path fill="#b8302a" d="M{hx - 9} {hy - 14}h18l-9 -9z"/>')
    if not CARD:
        k = m.keyframes("cwoc", [(0, "opacity:1"), (0.75, "opacity:0"), (0.83, "opacity:1"), (1, "opacity:1")])
        body.append(f'<circle class="{m.use(k, 6)}" cx="{hx}" cy="{hy - 8}" r="4" fill="#fff2d0"/><circle class="{m.use(k, 6)}" cx="{hx}" cy="{hy - 8}" r="14" fill="#fff2d0" opacity=".25"/>')
        # swell breaking on three skerries: spray fans, staggered
        fans = []
        for i, (sx, sy) in enumerate(((2008, 640), (2110, 641), (1500, 604))):
            fan = f'<path fill="none" stroke="#dfeef2" stroke-width="2" stroke-linecap="round" d="M{sx} {sy}q-6 -10 -14 -12M{sx} {sy}q0 -12 -2 -18M{sx} {sy}q6 -10 14 -12"/>'
            kk = m.keyframes(f"cwsp{i}", [(0, "opacity:0"), (0.06, "opacity:.9"), (0.12, "opacity:.6"), (0.2, "opacity:0"), (1, "opacity:0")])
            fans.append(fan.replace("<path ", f'<path class="{m.use(kk, 7, -2.5 * i)}" opacity="0" ', 1))
        body.append("".join(fans))


def hurtigruten(m, body):
    """The coastal express crawling along the horizon in the right margin: a dark hull and a row of lit windows."""
    inner = ('<path fill="#0f1c28" d="M0 0h70l6-5H-4z"/><path fill="#0f1c28" d="M14 -5h40v-6H18z"/>'
             '<path stroke="#ffd9a0" stroke-width="1.6" stroke-dasharray="2 2" d="M2 -2.5h66M18 -7.5h34"/>')
    g, _ = slide(m, "cwhr", inner, 2400, 1640, HORIZON - 1, -1)
    body.append(g)


# ------------------------------------------------------------------ the road and the bridge

# the hump's far limb: a cubic from the crest along the near deck's tangent, landing on the ridge
FAR = ((1782, 512), (1768, 494), (1738, 498), (1664, 590))   # lands on the ridge's shoulder, not at its foot


def far_at(t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = FAR
    a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
    return a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3


def far_curve(n=40):
    return [far_at(i / n) for i in range(n + 1)]


def far_band(th0, th1, n=40):
    top = far_curve(n)
    return top + [(x, y + th0 + (th1 - th0) * i / n) for i, (x, y) in reversed(list(enumerate(top)))]


def bridge_and_road(m, defs, body, rng):
    S = road_samples(260)
    def edges(scale=1.0, lift=0.0):
        L, R = [], []
        for i, (x, y, w, h, t) in enumerate(S):
            x2, y2 = (S[i + 1] if i + 1 < len(S) else S[i])[:2]
            x1, y1 = (S[i - 1] if i > 0 else S[i])[:2]
            dx, dy = x2 - x1, y2 - y1
            n = math.hypot(dx, dy) or 1
            # the road lies on the ground: its width shows mostly vertically squashed (seen from slightly above)
            nx, ny = -dy / n, dx / n
            k = w * scale / 2
            L.append((x + nx * k * 0.6, y + ny * k * 0.6 - lift * h / 50))
            R.append((x - nx * k * 0.6, y - ny * k * 0.6 - lift * h / 50))
        return L, R
    # the hump's concrete girder and piers (the bridge part, x > 1640 along the climb), then the rock embankment
    bridge = [s for s in S if s[4] >= 33]
    girder = [(x, y + 4 + w * 0.6) for x, y, w, h, t in bridge]
    top = [(x, y + 2) for x, y, w, h, t in bridge]
    # piers first (behind the girder): slender, inside the curve, taller toward the crest, down to the water
    piers = []
    for frac in (0.18, 0.36, 0.54, 0.72, 0.86):
        x, y, w, h, t = bridge[int(len(bridge) * frac)]
        water = HORIZON + 6 + max(0.0, (y - HORIZON)) * 0.6
        foot = max(water, y + 30)
        piers.append([(x - w * 0.18 - 1, y + w * 0.5), (x + w * 0.18 + 1, y + w * 0.5), (x + w * 0.22 + 1.5, foot), (x - w * 0.22 - 1.5, foot)])
    body.append(f'<path fill="#2f4a5e" d="{polys(piers)}"/>')
    # the far side of the hump: over the crest the road drops back to the sea behind it (darker, farther), so the top
    # reads as a bridge going over rather than a road into the sky
    # One rounded hump: the far limb leaves on the near deck's tangent, peaks just past the crest and drops
    # short and steep (110 x 86, shorter than the near limb because it is farther), as a dark backlit silhouette with
    # an amber rim, two piers, landing on the extended ridge. Drawn under the near ribbon, which hides its start.
    body.append(f'<path fill="#213a4e" d="{poly(far_band(4.0, 2.5))}"/>')
    rim = far_curve(24)
    body.append(f'<path fill="none" stroke="#e8bf94" stroke-width=".9" opacity=".5" d="M{rim[0][0]:.1f} {rim[0][1]:.1f}' + "".join(f"L{x:.1f} {y:.1f}" for x, y in rim[1:15]) + '"/>')
    pz = []
    for t in (0.5, 0.75):
        x, y = far_at(t)
        pz.append([(x - 1.2, y + 3), (x + 1.2, y + 3), (x + 1.6, HORIZON + 3), (x - 1.6, HORIZON + 3)])
    body.append(f'<path fill="#213a4e" d="{polys(pz)}"/>')
    body.append(f'<path fill="#6f8ea3" d="{poly(top + girder[::-1])}"/>')
    body.append(f'<path fill="none" stroke="#f2c79a" stroke-width="1.2" opacity=".6" d="M{top[0][0]:.0f} {top[0][1]:.0f}' + "".join(f"L{x:.0f} {y:.0f}" for x, y in top[1:]) + '"/>')
    emb = [s for s in S if 30 <= s[4] <= 36]
    body.append(f'<path fill="#2a3846" d="{poly([(x, y + w * 0.2) for x, y, w, h, t in emb] + [(emb[-1][0] + 30, emb[-1][1] + 70), (emb[0][0] - 60, emb[0][1] + 60)])}"/>')
    # the road surface: asphalt ribbon, wet sheen on its far edge
    L, R = edges()
    body.append(f'<path fill="#1b2430" d="{poly(L + R[::-1])}"/>')
    body.append(f'<path fill="none" stroke="#33506a" stroke-width="2" opacity=".7" d="M{L[0][0]:.0f} {L[0][1]:.0f}' + "".join(f"L{x:.0f} {y:.0f}" for x, y in L[1::2]) + '"/>')
    # white edge lines and the dim yellow centre line (dashes shrinking with distance)
    body.append(f'<path fill="none" stroke="#9fb4c4" stroke-width="1.2" opacity=".7" d="M{R[0][0]:.0f} {R[0][1]:.0f}' + "".join(f"L{x:.0f} {y:.0f}" for x, y in R[1::2]) + '"/>')
    dashes = []
    acc = 0.0
    for i in range(len(S) - 1):
        (x, y, w, h, t), (x2, y2, *_ ) = S[i], S[i + 1]
        seg = math.hypot(x2 - x, y2 - y)
        period = max(6.0, w * 0.9)
        if (acc % period) < period * 0.45:
            dashes.append(f"M{x:.0f} {y:.0f}L{x2:.0f} {y2:.0f}")
        acc += seg
    body.append(f'<path fill="none" stroke="#c9a03a" stroke-width="1.6" opacity=".75" d="{"".join(dashes)}"/>')
    # guardrails (W-beam on posts) along both edges, and red-orange snow poles with reflector bands on the verge
    for side, pts in ((1, L), (-1, R)):
        rail = [(x, y - S[i][2] * 0.08) for i, (x, y) in enumerate(pts)]
        body.append(f'<path fill="none" stroke="#7c8c98" stroke-width="1.6" opacity=".8" d="M{rail[0][0]:.0f} {rail[0][1]:.0f}' + "".join(f"L{x:.0f} {y:.0f}" for x, y in rail[1::2]) + '"/>')
    posts, poles, refl = [], [], []
    step_acc = 0.0
    for i in range(0, len(S) - 1):
        x, y, w, h, t = S[i]
        step_acc += math.hypot(S[i + 1][0] - x, S[i + 1][1] - y)
        if step_acc > max(8, w * 0.9):
            step_acc = 0
            for pts in (L, R):
                px, py = pts[i]
                posts.append(f"M{px:.0f} {py:.0f}v{-w * 0.08:.1f}")
            px, py = R[i]
            hp = w * 0.35
            poles.append(f"M{px:.0f} {py:.0f}v{-hp:.1f}")
            refl.append(f"M{px:.0f} {py - hp * 0.8:.1f}v{hp * 0.15:.1f}")
    body.append(f'<path stroke="#5a6874" stroke-width="1.4" d="{"".join(posts)}"/>')
    body.append(f'<path stroke="#d2452f" stroke-width="2" d="{"".join(poles)}"/>')
    if not CARD:
        body.append(f'<path stroke="#f2f2f2" stroke-width="2.2" d="{"".join(refl)}"/>')


# ------------------------------------------------------------------ the rider riding away (transform path), the car

def view_groups(m, name, rows_list, beats_each):
    """A rider view: rows shared by all its poses drawn once, the rest as pose groups swapping by opacity."""
    n = len(rows_list)
    shared = {"body": {}, "rim": {}}
    own = [{"body": {}, "rim": {}} for _ in range(n)]
    for key in ("body", "rim"):
        for y in set().union(*(p[key].keys() for p in rows_list)):
            rows = [p[key].get(y, []) for p in rows_list]
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
            out += f'<path stroke="#0d111a" d="{_runs_path(rows["body"])}"/>'
        if rows["rim"]:
            out += f'<path stroke="#f6c592" opacity=".8" d="{_runs_path(rows["rim"])}"/>'
        return out
    key = m.keyframes(f"{name}p", [(0, "opacity:1"), (1 / n, "opacity:0"), (1, "opacity:0")])
    parts = [grp(shared)] + [f'<g class="{m.use(key, n * beats_each * BEAT, -i * beats_each * BEAT)}" opacity="{1 if i == 0 else 0}">{grp(own[i])}</g>' for i in range(n)]
    return f'<g fill="none" stroke-width="1.5">{"".join(parts)}</g>'


def mirror(rows):
    return {k: {y: [(-b, -a) for a, b in runs][::-1] for y, runs in v.items()} for k, v in rows.items()}


def rider(m, body):
    """Ride away along the road: an outer group translating along the path (a stop a beat near, every 2 beats far),
    an inner one scaling (a stop every 4 beats), three view groups switched by opacity at the turns."""
    BASE = 40                                 # drawn at 40 (~66 units tall), scaled 1.5x near to 0.18x at the crest
    base_h = 1.66 * BASE
    rd = Rider()
    side = [rider_rows(rd, -math.pi / 2 + i * 2 * math.pi / POSES, BASE) for i in range(POSES)]
    rear = [rider_rows_view(rd, -math.pi / 2 + i * math.pi / 2, BASE, 55) for i in range(4)]
    rear_l = [mirror(r) for r in rear[:2]]
    t_side, t_turn, t_end = 22.8, 44.0, 66.0
    def frac(tt):
        return tt / LOOP
    # view switching (opacity): side 0 -> 22.8 s, three-quarter rear right -> 44 s, mirrored -> 66 s, then hidden
    def window(a, b):
        st = [(0, "opacity:0")] if a > 0 else [(0, "opacity:1")]
        if a > 0:
            st.append((frac(a), "opacity:1"))
        st.append((frac(b), "opacity:0"))
        st.append((1, "opacity:0"))
        return st
    v1 = m.use(m.keyframes("cwv1", window(0, t_side)), LOOP)
    v2 = m.use(m.keyframes("cwv2", window(t_side, t_turn)), LOOP)
    v3 = m.use(m.keyframes("cwv3", window(t_turn, t_end)), LOOP)
    # positions: wheel contact on the road, the bike centred on its point (side view: origin is the rear wheel)
    stops_t, stops_s = [], []
    t = 0.0
    while t <= t_end + 1e-9:
        x, y, *_ = at_time(t)
        stops_t.append((frac(t), f"transform:translate({x:.1f}px,{y:.1f}px)"))
        t += BEAT if t < 27 else 2 * BEAT
    t = 0.0
    while t <= t_end + 1e-9:
        h = at_time(t)[2]
        stops_s.append((frac(t), f"transform:scale({h / base_h:.3f})"))
        t += 4 * BEAT
    last = stops_t[-1][1]
    stops_t.append((1, last))
    stops_s.append((1, stops_s[-1][1]))
    # dedupe equal fractions (float drift)
    def clean(st):
        out, seen = [], set()
        for f, v in st:
            k = round(f * 100, 3)
            if k in seen or (out and k <= round(out[-1][0] * 100, 3)):
                continue
            seen.add(k)
            out.append((f, v))
        out[-1] = (1, out[-1][1])
        return out
    go = m.keyframes("cwgo", clean(stops_t))
    sc = m.keyframes("cwsc", clean(stops_s))
    x0, y0, h0, *_ = at_time(8.0)                                    # the still frame: near, on the left
    g_side = view_groups(m, "cws", side, 1)
    g_rear = view_groups(m, "cwr", rear, 2)
    g_rl = view_groups(m, "cwl", rear_l, 2)
    off = -0.5 * BASE                                                # centre the side-view bike on its point
    # the tail light, seen once he turns away: placed in his scaled frame under the saddle, but counter-scaled so it
    # stays ~3 units on screen all the way up the hump (the series' blinking tail light; the marker that finds him)
    cs = []
    t = 0.0
    while t <= t_end + 1e-9:
        h = at_time(t)[2]
        cs.append((frac(t), f"transform:scale({base_h / h:.2f})"))
        t += 4 * BEAT
    cs.append((1, cs[-1][1]))
    counter = m.keyframes("cwcs", clean(cs))
    blink = m.keyframes("cwtl", [(0, "opacity:1"), (0.5, "opacity:.25"), (1, "opacity:1")])
    tail = (f'<g class="{v2}" opacity="0"><g transform="translate(0 {-0.78 * BASE:.0f})"><g class="{m.use(counter, LOOP)}">'
            f'<circle class="{m.use(blink, 1)}" r="2.6" fill="#ff4a3a"/><circle r="7" fill="#ff4a3a" opacity=".22"/></g></g></g>'
            f'<g class="{v3}" opacity="0"><g transform="translate(0 {-0.78 * BASE:.0f})"><g class="{m.use(counter, LOOP)}">'
            f'<circle class="{m.use(blink, 1)}" r="2.6" fill="#ff4a3a"/><circle r="7" fill="#ff4a3a" opacity=".22"/></g></g></g>')
    svg = (f'<g class="{m.use(go, LOOP)}" transform="translate({x0:.0f} {y0:.0f})">'
           f'<g class="{m.use(sc, LOOP)}" transform="scale({h0 / base_h:.3f})">'
           f'<g class="{v1}"><g transform="translate({off:.0f} 0)">{g_side}</g></g>'
           f'<g class="{v2}" opacity="0">{g_rear}</g>'
           f'<g class="{v3}" opacity="0">{g_rl}</g>'
           f'{tail}</g></g>')
    body.append(svg)


def car(m, body):
    """In the rider's gap a car comes over the hump toward us: two warm headlights growing, on the left lane."""
    stops_t = []
    # it first climbs the hump's far limb (seen over the top: one light crossing both limbs says "one road"),
    # 68-71 s once the rider has gone over, then comes down the near side toward us, 71-93 s
    t0, tc, t1 = 68.0, 71.0, 93.0
    hc = at_time(66)[2]
    t = t0
    while t <= t1 + 1e-9:
        if t < tc:
            b = 1 - (t - t0) / (tc - t0)                               # landing -> crest
            x, y = far_at(b)
            h = hc * (1 - 0.3 * b)
            x, y = x + h * 0.15, y + 1.2 + h * 0.12                 # sit on the far deck (cancel the near side's offset)
        else:
            u = (t - tc) / (t1 - tc)
            x, y, h, *_ = at_time(66 - u * 46)                      # retrace the road from the crest to x ~ 1100
        stops_t.append((t / LOOP, f"transform:translate({x - h * 0.15:.1f}px,{y - h * 0.12:.1f}px) scale({h / 40:.3f})"))
        t += 2 * BEAT
    first = stops_t[0][1]
    st = [(0, first)] + stops_t + [(1, stops_t[-1][1])]
    out, seen = [], set()
    for f, v in st:
        k = round(f * 100, 3)
        if k in seen:
            continue
        seen.add(k)
        out.append((f, v))
    out[-1] = (1, out[-1][1])
    k = m.keyframes("cwcar", out)
    vis = m.keyframes("cwcv", [(0, "opacity:0"), (t0 / LOOP, "opacity:1"), (t1 / LOOP, "opacity:0"), (1, "opacity:0")])
    lights = '<circle cx="-3" r="2.2" fill="#fff4d8"/><circle cx="3" r="2.2" fill="#fff4d8"/><ellipse cy="1" rx="9" ry="3" fill="#fff0c8" opacity=".25"/>'
    x, y, h, *_ = at_time(66)
    body.append(f'<g class="{m.use(vis, LOOP)}" opacity="0"><g class="{m.use(k, LOOP)}" transform="translate({x:.0f} {y:.0f})">{lights}</g></g>')


def foreground(m, defs, body, rng):
    # dark gneiss knolls in the corners, wind-bent grass at the bottom left, a cairn (varde) at the bottom right
    body.append(f'<path fill="#0a1119" d="{poly([(XL, H + 10), (XL, 1080), (-200, 1100), (60, 1150), (260, 1190), (420, H + 10)])}"/>')
    body.append(f'<path fill="#0a1119" d="{poly([(XR, H + 10), (XR, 1020), (2100, 1050), (1900, 1120), (1760, 1180), (1640, H + 10)])}"/>')
    if not CARD:
        grass = "".join(f"M{x:.0f} {y:.0f}q{rng.uniform(4, 10):.0f} {-rng.uniform(14, 30):.0f} {rng.uniform(16, 28):.0f} {-rng.uniform(20, 40):.0f}" for x, y in [(rng.uniform(XL, 300), rng.uniform(1120, 1240)) for _ in range(70)])
        body.append(f'<path fill="none" stroke="#18242e" stroke-width="2" d="{grass}"/>')
    cx, cy = 1830, 1150
    stones = [(cx, cy, 34, 12), (cx - 4, cy - 18, 28, 10), (cx + 2, cy - 33, 22, 9), (cx, cy - 46, 15, 8), (cx + 1, cy - 56, 9, 6)]
    body.append(f'<path fill="#121c26" d="{"".join(f"M{x - w} {y}a{w} {h} 0 1 0 {2 * w} 0a{w} {h} 0 1 0 {-2 * w} 0" for x, y, w, h in stones)}"/>')
    # the near guardrail sweeping along the bottom (the road's near edge as it leaves the frame)
    body.append(f'<path fill="none" stroke="#5a6874" stroke-width="5" d="M{XL} 1196Q200 1170 520 1112"/><path stroke="#5a6874" stroke-width="4" d="M-300 1200v-22M-60 1186v-22M180 1166v-20M400 1130v-18"/>')


def birds(m, body):
    eagle = '<path fill="#0c1520" d="M-34 0q16 -6 34 -2q18 -4 34 2l-5 3-6-1-5 3-6-2-12 2-12-2-6 2-5-3-6 1z"/>'
    g, _ = slide(m, "cwea", eagle, -300, 1100, 230, 1, extra_y=-30)
    body.append(g)


def scene(m: Motion):
    rng = random.Random(61)
    defs, body = [], []
    sky(m, defs, body, rng)
    far_land(m, defs, body, rng)
    sea(m, defs, body, rng)
    if not CARD:
        hurtigruten(m, body)
        birds(m, body)
    islets(m, defs, body, rng)
    bridge_and_road(m, defs, body, rng)
    if not CARD:
        car(m, body)
        rider(m, body)
        info = {"seconds": LOOP}
    else:
        x, y, h, *_ = at_time(8.0)
        s = h / 50
        body.append(f'<g transform="translate({x - 20 * s:.0f} {y:.0f}) scale({s:.2f})" fill="none" stroke="#0d111a" stroke-width="2.4"><circle cx="0" cy="-10" r="9"/><circle cx="30" cy="-10" r="9"/>'
                    f'<path d="M0 -10l12 0 10-14H7l5 14M30 -10l-6-17"/><path stroke-width="6" stroke-linecap="round" d="M7 -28l13-12M9 -26l4 14"/><circle cx="23" cy="-44" r="4" fill="#0d111a"/></g>')
        info = {"seconds": LOOP}
    foreground(m, defs, body, rng)
    return defs, body, info
