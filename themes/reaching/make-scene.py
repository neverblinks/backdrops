#!/usr/bin/env python3
"""Generate the two Reaching scenes and the theme's card:
plugins/reaching/hooks/scene-reaching.js, scene-reaching-classic.js and cards/reaching.svg.

    python3 -I themes/reaching/make-scene.py && python3 -I tools/build.py   (from the repo's root)

Every hand dot sits where a dot sits in the artwork (reference-dots.json: x, y, area, measured from @samdape's
piece and used with permission). Past the artwork's left and right edges, which only windows wider than a laptop
show, the forearms carry on in the same dots, traced from Michelangelo's public-domain fresco (fresco-arms.json,
made by trace-arms.py; that extension is ours, not the artist's).

A wave crest sweeps from the end of one forearm to the end of the other every 7.5 s, one wave at a time, and turns
the dots into ASCII as it passes. On the hands the crest lasts 8 beats (dot, edge + or #, peak * or %, edge, dot);
on the forearms it shows the peak for 4 beats only, so they read calmer than the hands.

Two versions, which differ only in how they keep the chat text readable:
  clear    the picture drawn once; the app's glass (#000, 0.72, blur 0) dims the chat column and follows it, and a
           limiter shaped like the old in-picture band caps the brightest dots behind the text. The default.
  classic  a dimmed band in the picture plus the app's glass (#000, 0.65).

Built for the Claude desktop app's backdrop, which is one SVG image (at most 131,072 characters):
  - the resting dots are one still layer; each crest band is ONE group, switched on a shared 0.125 s beat by
    stroke-dashoffset (see the crest windows below), never by opacity
  - the glyphs are our own vector strokes drawn as dashed row-runs: a run of same-kind glyphs in one row of one band
    is one dashed subpath per stroke family, whatever its length
  - no clips, masks or per-element animation (those froze the app)
  - animations written in the only form the app runs: full `animation:` shorthand, `step-end`, explicit ascending
    % stops
"""
import json
import math
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
HOOKS = ROOT / "plugins" / "reaching" / "hooks"

W, H = 2000, 1293                  # the artwork's proportions
SMALL_AREA_MAX = 20                # the artwork's dots are about 8 (light) or 44 (dense) px in area
DOT_R = {"s": 1.65, "b": 3.7}      # resting dot radii, as measured
CHARS = {"s": ("", "+", "*"), "b": ("", "#", "%")}   # edge and peak glyph per dot kind
WAVE_S = 7.5                       # seconds between crests
BEAT = 0.125                       # the app's beat: one crest band per beat
BANDS = 60                         # WAVE_S / BEAT
STEP, FIRST = 40, -5               # bands per unit of phase; the left arm's end is at phase -5/40

APP_ZOOM = 1.2 ** 1.5
LAPTOP_PX_PER_UNIT = (1512 / W) / APP_ZOOM   # a 1512 pt window, where the picture fits by width
HALF = 6000                        # screen-wide overlays: 12000 CSS px, centred on the window
PAD = 500
VIEW_H = 949 * W / 1512            # 1255.291...: full precision, or the laptop's dots shift a hair
VIEW_Y = (H - VIEW_H) / 2
FADE_IN, FADE_OUT, FADE_DARK = 575, 1460, 0.60   # the soft dark edge: clear to 575 CSS px, 0.6 dark from 1460

GLASS = 0.72                       # the clear version's glass opacity (black, no blur)
CAP = round(0x3f / (1 - GLASS))    # the limiter's cap behind the glass: #3f3f3f once the glass has dimmed it
LIM_CORE = 530                     # CSS px each side of the centre where the cap applies in full


def smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


# ---- the overlays

def edge_fade() -> str:
    """Darkens the window's far left and right, where the forearms run out, in screen units."""
    ease = [(i / 8, 3 * (i / 8) ** 2 - 2 * (i / 8) ** 3) for i in range(9)]
    pts = ([(-FADE_OUT + (FADE_OUT - FADE_IN) * u, 1 - k) for u, k in ease]
           + [(FADE_IN + (FADE_OUT - FADE_IN) * u, k) for u, k in ease])

    def off(x):
        return f"{(x + HALF) / (2 * HALF):.5f}".rstrip("0").rstrip(".")
    stops = ([f'<stop offset="0" stop-opacity="{FADE_DARK}"/>']
             + [f'<stop offset="{off(x)}" stop-opacity="{k * FADE_DARK:.3f}"/>' for x, k in pts]
             + [f'<stop offset="1" stop-opacity="{FADE_DARK}"/>'])
    return (f'<linearGradient id="edge" x2="1">{"".join(stops)}</linearGradient>'
            f'<rect x="50%" width="{2 * HALF}" height="100%" transform="translate({-HALF} 0)" fill="url(#edge)"/>')


def screen_gradient(points) -> str:
    """A band given in picture units at the laptop view, drawn in screen units so it follows the chat column at any
    window width and zoom instead of growing with the picture."""
    def off(x):
        return f"{((x - W / 2) * LAPTOP_PX_PER_UNIT + HALF) / (2 * HALF):.5f}".rstrip("0").rstrip(".")
    stops = ([(points[0][0] - 1e6, points[0][1])] if points[0][1] else []) + list(points)
    return ('<linearGradient id="mid" x2="1">'
            + "".join(f'<stop offset="{off(x) if x > -1e5 else 0}" stop-opacity="{o:.3f}"/>' for x, o in stops)
            + "</linearGradient>")


def classic_band() -> str:
    """Classic's band, 0.65 dark over the middle of the picture (fades in over .13-.247, out over .838-.95)."""
    a, b, c, d = 0.13, 0.247, 0.838, 0.95
    return screen_gradient([(a * W, 0), (b * W, 0.65), (c * W, 0.65), (d * W, 0)])


# the older in-picture band the clear version's limiter is shaped like: full over the chat text (x 366-1640 here,
# with the sidebar collapsed in a 1512 pt window), a little stronger under the first words of each line, then fades
CLEAR = {"dim": 0.72, "left_dim": 0.86, "text_x0": 366, "text_x1": 1640,
         "pad_left": 50, "pad_right": 10, "fade": 240, "left_hold_end": 520, "left_ease_end": 780}


def clear_points() -> list[tuple[float, float]]:
    c = CLEAR
    points = []
    full_left = c["text_x0"] - c["pad_left"]
    for i in range(13):
        t = i / 12
        points.append((full_left - c["fade"] * (1 - t), c["left_dim"] * smooth(t)))
    for i in range(1, 9):
        t = i / 8
        x = c["left_hold_end"] + (c["left_ease_end"] - c["left_hold_end"]) * t
        points.append((x, c["left_dim"] + (c["dim"] - c["left_dim"]) * smooth(t)))
    for i in range(13):
        t = i / 12
        points.append((c["text_x1"] + c["pad_right"] + c["fade"] * t, c["dim"] * (1 - smooth(t))))
    return points


def band_at(x_css: float, pts) -> float:
    """That band (0..1) at a CSS-px position, interpolated linearly between its stops as a gradient does."""
    xs = [(px - W / 2) * LAPTOP_PX_PER_UNIT for px, _ in pts]
    if x_css <= xs[0]:
        return pts[0][1] if pts[0][1] else 0.0
    for (xa, (_, a)), (xb, (_, b)) in zip(zip(xs, pts), zip(xs[1:], pts[1:])):
        if xa <= x_css <= xb:
            return a + (b - a) * (x_css - xa) / (xb - xa) if xb > xa else b
    return pts[-1][1]


def glass_t(x_css: float) -> float:
    """What the app's glass lets through, as measured: flat over the 733 px column, a smoothstep to nothing over
    270 pt (205 CSS px) outside it."""
    d = abs(x_css) - 366.5
    g = 1.0 if d <= 0 else (0.0 if d >= 205 else 1 - smooth(d / 205))
    return 1 - GLASS * g


def limiter() -> str:
    """Caps the brightest dots behind the chat text (mix-blend-mode darken), so the old band's readability holds
    under the glass alone: the cap follows the old band's shape, divided by what the glass lets through."""
    core, fade = LIM_CORE, 12
    pts = clear_points()
    cap_hex = f"#{CAP:02x}{CAP:02x}{CAP:02x}"
    left, width = -(core + fade), 2 * (core + fade)
    stops = [f'<stop offset="0" stop-color="{cap_hex}" stop-opacity="0"/>']
    # the exact curve every 2 px, then the fewest stops that keep linear interpolation within 2 levels of it
    xsamp = [-core + i * 2 for i in range(core + 1)]
    curve = [min(CAP, 242 * (1 - band_at(x, pts)) / glass_t(x)) for x in xsamp]
    keep = {0, len(xsamp) - 1}

    def split(i, j):
        if j <= i + 1:
            return
        k, worst = None, 2.0
        for m in range(i + 1, j):
            lin = curve[i] + (curve[j] - curve[i]) * (m - i) / (j - i)
            if abs(curve[m] - lin) > worst:
                k, worst = m, abs(curve[m] - lin)
        if k is not None:
            keep.add(k)
            split(i, k)
            split(k, j)
    split(0, len(xsamp) - 1)
    for i in sorted(keep):
        x, v = xsamp[i], round(curve[i])
        stops.append(f'<stop offset="{(x - left) / width:.4f}" stop-color="#{v:02x}{v:02x}{v:02x}"/>')
    stops.append(f'<stop offset="1" stop-color="{cap_hex}" stop-opacity="0"/>')
    return (f'<linearGradient id="cap" x2="1">{"".join(stops)}</linearGradient>'
            f'<rect x="50%" width="{width}" height="100%" transform="translate({left} 0)" fill="url(#cap)" '
            'style="mix-blend-mode:darken"/>')


# ---- the dots, and the band each one's crest falls in

dots = json.loads((HERE / "reference-dots.json").read_text())
clusters = []
for y in sorted({d[1] for d in dots}):
    if clusters and y - clusters[-1][-1] < 6:
        clusters[-1].append(y)
    else:
        clusters.append([y])
# math.fsum, not sum: Python 3.12 changed how sum() adds floats, and the output must not depend on the version
row_of = {y: round(math.fsum(c) / len(c), 1) for c in clusters for y in c}
arm_dots = json.loads((HERE / "fresco-arms.json").read_text())


def kind_of(area: float) -> str:
    return "s" if area <= SMALL_AREA_MAX else "b"


def band_of(x: float, y: float) -> int:
    return math.floor(((x / W) * 0.8 + (y / H) * 0.2) * STEP) - FIRST


bands = defaultdict(list)          # band -> [(x, row, kind, "h" hand or "a" arm)]
for x, y, area in dots:
    bands[band_of(x, y)].append((x, row_of[y], kind_of(area), "h"))
for x, y, area in arm_dots:
    bands[band_of(x, y)].append((x, round(y, 1), kind_of(area), "a"))
assert min(bands) >= 0 and max(bands) < BANDS, (min(bands), max(bands))


# ---- path writing: positions on the 0.1 grid, every value as short as it can be

def num(v: float) -> str:
    t = f"{v:.1f}".rstrip("0").rstrip(".")
    if t in ("-0", ""):
        t = "0"
    return t.replace("0.", ".", 1) if t.startswith(("0.", "-0.")) else t


def num2(v: float) -> str:
    t = f"{v:.2f}".rstrip("0").rstrip(".")
    return t.replace("0.", ".", 1) if t.startswith("0.") else t


def numd(v: float) -> str:
    """Dash-pattern numbers: two decimals (the arms' pitch is 11.25; one decimal would drift 0.05 a glyph)."""
    t = f"{v:.2f}".rstrip("0").rstrip(".")
    if t in ("-0", ""):
        t = "0"
    return t.replace("0.", ".", 1) if t.startswith("0.") else t


def pair(dx: float, dy: float) -> str:
    a, b = num(dx), num(dy)
    return a + ("" if b.startswith("-") or (b.startswith(".") and "." in a) else " ") + b


class Enc:
    """Subpaths 'move, h L' with relative moves; positions kept on the 0.1 grid so relative steps stay exact."""
    def __init__(self):
        self.parts, self.cx, self.cy = [], None, None

    def seg(self, x, y, length):
        x, y = round(x, 1), round(y, 1)
        length = math.ceil(length * 10 - 1e-6) / 10   # rounded up: the pen then sits where the next move assumes
        if self.cx is None:
            self.parts.append(f"M{num(x)} {num(y)}")
        else:
            self.parts.append("m" + pair(x - self.cx, y - self.cy))
        self.parts.append("h" + num2(length))
        self.cx, self.cy = round(x + round(length, 1), 1), y

    def d(self) -> str:
        return "".join(self.parts)


def fit_rows(chosen, pitch, tol=0.75):
    """[(x, y)] -> [(start, y, n)]: same-row neighbours one pitch apart, each run's start fitted to its dots."""
    rows = defaultdict(list)
    for x, y in chosen:
        rows[y].append(x)
    runs = []
    for y in sorted(rows):
        xs = sorted(rows[y])
        cur = [xs[0]]
        for x in xs[1:]:
            if round((x - cur[-1]) / pitch) == 1 and x - cur[-1] < 1.45 * pitch:
                cur.append(x)
            else:
                runs.append((y, cur))
                cur = [x]
        runs.append((y, cur))
    fitted = []
    for y, r in runs:
        s0 = math.fsum(x - i * pitch for i, x in enumerate(r)) / len(r)
        err = max(abs(x - (s0 + i * pitch)) for i, x in enumerate(r))
        assert err < tol, (r, err)
        fitted.append((s0, y, len(r)))
    return fitted


def dot_runs(pts) -> str:
    """The forearms' dots, which sit on an exact grid: each row's run is one subpath, drawn dashed "0 11.25"."""
    rows = defaultdict(list)
    for x, y in pts:
        rows[y].append(x)
    enc = Enc()
    for y in sorted(rows):
        xs = sorted(rows[y])
        cur, runs = [xs[0]], []
        for x in xs[1:]:
            if abs(x - cur[-1] - ARM_PITCH) < 0.3:
                cur.append(x)
            else:
                runs.append(cur)
                cur = [x]
        runs.append(cur)
        for r in runs:
            enc.seg(r[0], y, (len(r) - 1) * ARM_PITCH + .1)
    return enc.d()


# ---- the glyphs: whole row-runs from dashed lines. The hands' dots sit in rows at a near-constant pitch (11.0-11.4
# units): one pitch for every run, each run's start fitted to its dots (worst error 0.38 units). A thin dashed line
# gives the horizontal bars of every glyph in a run, a wide butt-capped line dashed thin gives the vertical bars, and
# slanted strokes are vertical bars skewed. Chrome restarts the dash pattern at every subpath, so runs are
# independent. Sized like the 15 px SF Mono glyphs, measured at weight 500.
PITCH = 11.2                       # the hands
ARM_PITCH = 11.25                  # the forearms' grid
T = 1.6                            # stroke width
HS, HH = 2.9, 10.75                # # : upright spacing and height
SK_AST, SK_HASH, SK_PCT = 30.0, -14, -63.0    # skew degrees: * arms, # uprights, % slash
TA = T / math.sin(math.radians(60))   # the star's steep arms' horizontal width, so they are T thick across
PCT_H, TP = 3.0, 1.5               # % : the slash's height, and its strokes' thickness
TW = TP / math.sin(math.radians(27))   # the slash's horizontal end width, so it is TP thick across
R_RING = 1.78                      # % : ring radius
ARM_DX, ARM_DY = 3.9, 2.25
ARM_LEN = round(math.hypot(2 * ARM_DX, 2 * ARM_DY), 3)

# the dense dots' glyphs, stroke families of (glyph, class, y offset, x start offset, extra length, skew degrees):
#   # : bars and lean measured off SF Mono (bars at -2.6 and +1.4, shifted along the lean)
#   % : two rings (centres (-2, -3.1) and (2, 2.7)) with holes, and a short, shallow slash through the middle: one
#       dash of a wide line, skewed, a parallelogram PCT_H tall leaning 27 degrees from horizontal, TP thick across
DENSE = [
    ("#", "pe", -2.6, -3.55, 8.2, 0), ("#", "pe", 1.4, -4.5, 8.2, 0), ("#", "pf", -0.4, -HS / 2 - T / 2, HS + T, SK_HASH),
    ("%", "pg", -0.25, -TW / 2, TW, SK_PCT), ("%", "ph", -3.1, -2.0, .1, 0), ("%", "ph", 2.7, 2.0, .1, 0),
    ("%", "pi", -3.1, -2.0, .1, 0), ("%", "pi", 2.7, 2.0, .1, 0),
]


def runs_path(fitted, cls, q, yo, xo, extra, sk, pitch):
    tn = math.tan(math.radians(sk)) if sk else 0.0
    enc = Enc()
    for s0, y, n in fitted:
        Y = y + yo
        enc.seg(s0 + xo - Y * tn, Y, (n - 1) * pitch + extra)
    return sk, f'<path class="{cls}{q}" d="{enc.d()}"/>'


def dense_layer(cells, layer: int, pitch: float, q: str):
    """One band's # (layer 1, the edge) or % (layer 2, the peak) glyphs: one path per class and skew."""
    chosen = [(c[0], c[1]) for c in cells if c[2] == "b"]
    if not chosen:
        return []
    fitted = fit_rows(chosen, pitch)
    groups = []                    # [(class, skew), families], in drawing order: ring holes after rings
    for glyph, cls, yo, xo, extra, sk in DENSE:
        if glyph != CHARS["b"][layer]:
            continue
        for group in groups:
            if group[0] == (cls, sk):
                group[1].append((yo, xo, extra))
                break
        else:
            groups.append([(cls, sk), [(yo, xo, extra)]])
    out = []
    for (cls, sk), families in groups:
        tn = math.tan(math.radians(sk)) if sk else 0.0
        enc = Enc()
        for s0, y, n in fitted:
            for yo, xo, extra in families:
                Y = y + yo
                enc.seg(s0 + xo - Y * tn, Y, (n - 1) * pitch + extra)
        out.append((sk, f'<path class="{cls}{q}" d="{enc.d()}"/>'))
    return out


def light_layer(cells, pitch: float, q: str):
    """The light dots' crest (+ at the edge, * at the peak), the strokes the two glyphs share in one path each:
    pm, the vertical bar of + and the star's vertical arm (8.1 wide, 0.2 below the dot); pn, the horizontal bar of +
    (7.8) and of the star (8.4); pd, the star's two steep arms. The star is SF Mono's, turned 30 degrees so every
    arm is along the row or steep: skewed dashes have horizontally cut ends, which read as wedges on shallow arms."""
    pts = [(c[0], c[1]) for c in cells if c[2] == "s"]
    if not pts:
        return []
    fitted = fit_rows(pts, pitch)
    return [runs_path(fitted, "pm", q, 0.2, -0.75, 1.5, 0, pitch), runs_path(fitted, "pn", q, 0, -4.2, 8.4, 0, pitch),
            runs_path(fitted, "pd", q, 0, -TA / 2, TA, SK_AST, pitch),
            runs_path(fitted, "pd", q, 0, -TA / 2, TA, -SK_AST, pitch)]


def backing(cells, pitch: float, q: str):
    """Black dots (as wide as a dense dot + 0.8 each side) under every crest glyph of a band, both kinds in one run:
    they hide the resting dots while the crest shows."""
    pts = [(c[0], c[1]) for c in cells]
    if not pts:
        return []
    enc = Enc()
    for s0, y, n in fit_rows(pts, pitch):
        enc.seg(s0, y, (n - 1) * pitch + .1)
    return [(0, f'<path class="k{q}" d="{enc.d()}"/>')]


def wrap(items) -> str:
    """[(skew, path)] -> markup, each skewed path carrying its own transform."""
    return "".join(p if not sk else p.replace("<path ", f'<path transform="skewX({sk:g})" ', 1) for sk, p in items)


def still_rest() -> str:
    """Every resting dot, still: the hands at the artwork's whole-unit positions, the forearms as dot-runs."""
    out = []
    for kind in ("s", "b"):
        pts = sorted({(round(c[0]), round(c[1])) for cells in bands.values() for c in cells
                      if c[2] == kind and c[3] == "h"}, key=lambda p: (p[1], p[0]))
        d, cx, cy = [], None, None
        for x, y in pts:
            d.append(f"M{x} {y}h0" if cx is None else "m" + pair(x - cx, y - cy) + "h0")
            cx, cy = x, y
        out.append(f'<path class="d{kind}" d="{"".join(d)}" stroke-width="{2 * DOT_R[kind]:g}"/>')
        apts = [(c[0], c[1]) for cells in bands.values() for c in cells if c[2] == kind and c[3] == "a"]
        if apts:
            out.append(f'<path class="{"as" if kind == "s" else "ab"}" d="{dot_runs(apts)}"/>')
    return "".join(out)


# ---- the crest windows. Each band is ONE group, switched by stroke-dashoffset (inherited from the group) instead of
# three opacity groups. Every crest class's dash pattern has three windows along it:
#   [0, WIN)       the peak window   (*, %): its strokes, then gap
#   [WIN, 2 WIN)   the edge window   (+, #)
#   [2 WIN, 3 WIN) empty: the crest is off
# A run is shorter than WIN, so the group's offset (0, WIN or 2 WIN) picks which glyphs show. Round-capped classes
# (the % rings, the backing dots) sit in the peak window, so the dash that opens their pattern is a real dot; butt
# classes open with a 0-length dash, which draws nothing.
KMAX = 1                           # the most glyphs in one run
for cells in bands.values():
    for src, pitch in (("h", PITCH), ("a", ARM_PITCH)):
        for kind in ("s", "b", None):          # None: the backing's runs, both kinds together (longer)
            pts = [(c[0], c[1]) for c in cells if (kind is None or c[2] == kind) and c[3] == src]
            if pts:
                KMAX = max([KMAX] + [n for _, _, n in fit_rows(pts, pitch)])
WIN = math.ceil(KMAX * (2 * ARM_LEN + ARM_PITCH) + 2)   # the longest pattern unit: the star's zigzag


def win_dash(unit, window: int) -> str:
    """dasharray: `unit` (dash, gap, ...: one glyph, summing to the pitch) KMAX times inside `window` (0 peak, 1 edge)."""
    arr = list(unit) * KMAX
    arr[-1] += 3 * WIN - window * WIN - KMAX * math.fsum(unit)
    if window:
        arr = [0, window * WIN] + arr
    return " ".join(numd(v) for v in arr)


def win2(unit_p, unit_e) -> str:
    """dasharray showing unit_p in the peak window and unit_e in the edge window (one path for two glyph stages)."""
    a = list(unit_p) * KMAX
    a[-1] += WIN - KMAX * math.fsum(unit_p)
    b = list(unit_e) * KMAX
    b[-1] += 2 * WIN - KMAX * math.fsum(unit_e)
    return " ".join(numd(v) for v in a + b)


def crest_css(pitch: float, q: str, used: set[str]) -> str:
    """The crest classes' strokes and dash windows at a pitch, for the classes the drawing uses."""
    P = pitch
    # round-capped window dots are 0.01 long, not 0: a 0-length dash exactly on a window's start is skipped when the
    # offset lands a hair past it
    back = [.01, P - .01] * KMAX
    back[-1] += WIN - KMAX * P
    back = back + [.01, P - .01] * KMAX
    back[-1] += 2 * WIN - KMAX * P
    strokes = {     # class: (stroke-width, dasharray)
        "pe": (numd(T), win_dash([8.2, P - 8.2], 1)),
        "pf": (numd(HH), win_dash([T, HS - T, T, P - HS - T], 1)),
        "pm": ("8.1", win2([1.5, P - 1.5], [1.5, P - 1.5])),
        "pn": (numd(T), win2([8.4, P - 8.4], [0, 0.3, 7.8, P - 8.1])),
        "pd": ("7.27", win_dash([TA, P - TA], 0)),
        "pg": (numd(PCT_H), win_dash([TW, P - TW], 0)),
        "ph": (numd(2 * R_RING + TP), win_dash([.01, P - .01], 0)),
        "pi": (numd(max(.1, 2 * R_RING - TP)), win_dash([.01, P - .01], 0)),
        "k": (numd(2 * DOT_R["b"] + 1.6), " ".join(numd(v) for v in back)),
    }

    def rule(names, body):
        selector = ",".join(f".{n}{q}" for n in names if n + q in used)
        return f"{selector}{{{body}}}" if selector else ""
    return (rule(["pd", "pe", "pf", "pg", "pm", "pn"], "fill:none;stroke-linecap:butt")
            + rule(["ph", "pi", "k"], "fill:none;stroke-linecap:round")
            + rule(["pd", "pm", "pn"], "stroke:#bdbdbd") + rule(["pe", "pf", "pg", "ph"], "stroke:#e0e0e0")
            + rule(["pi", "k"], "stroke:#000")
            + "".join(rule([cls], f"stroke-width:{width};stroke-dasharray:{dashes}")
                      for cls, (width, dashes) in strokes.items()))


# ---- the bands' groups and their timing: the hands' crest (C) lasts 8 beats, edge 2, peak 4, edge 2; the forearms'
# (D) shows the peak only, for 4 beats, centred on the same beat
CENTRE = 22                        # the crest's centre beat inside the keyframes
layers, rules = [still_rest()], []
for band in sorted(bands):
    cells = bands[band]
    parts = {"C": [], "D": []}
    for src, pitch, q in (("h", PITCH, ""), ("a", ARM_PITCH, "q")):
        sub = [c for c in cells if c[3] == src]
        key = "D" if src == "a" else "C"
        parts[key] += backing(sub, pitch, q) + light_layer(sub, pitch, q)
        if src == "h":
            parts[key] += dense_layer(sub, 1, pitch, q)
        parts[key] += dense_layer(sub, 2, pitch, q)
    for key, items in parts.items():
        if items:
            layers.append(f'<g class="{key}{band}">{wrap(items)}</g>')
            rules.append(f".{key}{band}{{animation:{key} {WAVE_S:g}s step-end infinite {-(BANDS - band) * BEAT:g}s}}")


def crest_keyframes(name: str, beats: int, peak_only: bool) -> str:
    edge, off = WIN, 2 * WIN

    def at(beat):
        return f"{100 * beat / BANDS:.3f}".rstrip("0").rstrip(".") + "%"
    c = CENTRE
    if peak_only:
        steps = [(0, off), (c - beats // 2, 0), (c + beats // 2, off)]
    else:
        steps = [(0, off), (c - 4, edge), (c - 2, 0), (c + 2, edge), (c + 4, off)]
    return (f"@keyframes {name}{{" + "".join(f"{at(b)}{{stroke-dashoffset:{v}}}" for b, v in steps)
            + f"100%{{stroke-dashoffset:{off}}}}}")


KEYFRAMES = crest_keyframes("C", 8, False) + crest_keyframes("D", 4, True)
DRAWING = "".join(layers)
USED = set(re.findall(r'class="([a-z]+)"', DRAWING))
ARMS_CSS = (f".as,.ab{{fill:none;stroke-linecap:round;stroke-dasharray:0 {ARM_PITCH:g}}}"
            f".as{{stroke:#d4d4d4;stroke-width:{2 * DOT_R['s']:g}}}.ab{{stroke:#f2f2f2;stroke-width:{2 * DOT_R['b']:g}}}")


def scene(version: str) -> str:
    classic = version == "classic"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
<style>
{crest_css(PITCH, "", USED) + crest_css(ARM_PITCH, "q", USED)}
path{{fill:none;stroke-linecap:round}}.ds{{stroke:#d4d4d4}}.db{{stroke:#f2f2f2}}{ARMS_CSS}
[class^=C],[class^=D]{{stroke-dashoffset:{2 * WIN}}}
{KEYFRAMES}
{"".join(rules)}
@media (prefers-reduced-motion:reduce){{[class^=C],[class^=D]{{animation:none!important}}}}
</style>
<defs>{classic_band() if classic else ""}</defs>
<svg viewBox="{-PAD} {VIEW_Y:.7f} {W + 2 * PAD} {VIEW_H:.7f}" preserveAspectRatio="xMidYMid slice">
<rect x="{-PAD}" width="{W + 2 * PAD}" height="{H}" fill="#000"/>
{DRAWING}
</svg>
{edge_fade()}
{'<rect x="50%" width="12000" height="100%" transform="translate(-6000 0)" fill="url(#mid)"/>' if classic else ""}
{"" if classic else limiter()}
</svg>"""
    return "".join(line.strip() for line in svg.splitlines())


def card() -> str:
    """The picker's card: the resting picture (no glass) as dashed dot-runs, cropped to 16:9, so no renderer
    depends on `slice`. The hands' dots per whole row and kind, the forearms the same way. It is a live card:
    a soft band of light crosses the glyphs from one forearm to the other in eight steps (4 s), then rests
    1 s, like the scene's wave; under reduced motion only the resting picture shows."""
    width = VIEW_H * 16 / 9
    left = W / 2 - width / 2
    layers = []   # (path data, colour, stroke width, dash)
    seen = []     # every dot the card shows, for where the band starts and ends
    for kind in ("s", "b"):
        colour = "#d4d4d4" if kind == "s" else "#f2f2f2"
        hand = [(x, row_of[y]) for x, y, a in dots if kind_of(a) == kind]
        enc = Enc()
        for s0, y, n in fit_rows(hand, PITCH, tol=3):
            enc.seg(s0, y, (n - 1) * PITCH + .1)
        layers.append((enc.d(), colour, 2 * DOT_R[kind], f"0 {PITCH:g}"))
        arm = [(x, round(y, 1)) for x, y, a in arm_dots if kind_of(a) == kind]
        layers.append((dot_runs(arm), colour, 2 * DOT_R[kind], f"0 {ARM_PITCH:g}"))
        seen += [(x, y) for x, y in hand + arm if left <= x <= left + width and VIEW_Y <= y <= VIEW_Y + VIEW_H]
    xs = sorted(x for x, _ in seen)
    ys = sorted(y for _, y in seen)
    start, end, mid = xs[len(xs) // 100], xs[len(xs) * 99 // 100], ys[len(ys) // 2]

    def num(v: float) -> str:
        return f"{v:.1f}".rstrip("0").rstrip(".")

    scale = width / 704   # the band keeps the old 704-wide card's proportions
    steps = 8
    css = ("@keyframes w{0%{opacity:0}2.5%{opacity:.5}5%{opacity:1}10%{opacity:1}12.5%{opacity:.5}15%{opacity:0}"
           "100%{opacity:0}}.k{opacity:0}"
           + "".join(f".k{i}{{animation:w 5.0s step-end infinite -{(0 if i == 0 else (10 - i) * .5):g}s}}"
                     for i in range(steps))
           + "@media (prefers-reduced-motion:reduce){.k{animation:none!important;opacity:0}}")
    bands = [f'<linearGradient id="c0" gradientUnits="userSpaceOnUse" x1="{num(-110 * scale)}" '
             f'y1="{num(-55 * scale)}" x2="{num(10 * scale)}" y2="{num(5 * scale)}" '
             f'gradientTransform="translate({num(start)} {num(mid)})"><stop offset="0" stop-color="#fff" '
             'stop-opacity="0"/><stop offset=".55" stop-color="#fff"/><stop offset="1" stop-color="#fff" '
             'stop-opacity="0"/></linearGradient>']
    bands += [f'<linearGradient id="c{i}" href="#c0" '
              f'gradientTransform="translate({num(start + (end - start) * i / (steps - 1))} {num(mid)})"/>'
              for i in range(1, steps)]
    defs = "".join(f'<path id="p{i}" d="{d}" stroke-dasharray="{dash}"/>' for i, (d, _, _, dash) in enumerate(layers))
    rest = "".join(f'<use href="#p{i}" stroke="{colour}" stroke-width="{w:g}"/>'
                   for i, (_, colour, w, _) in enumerate(layers))
    waves = "".join(f'<g class="k k{k}" stroke="url(#c{k})">'
                    + "".join(f'<use href="#p{i}" stroke-width="{num(w * 1.35)}"/>' for i, (_, _, w, _) in enumerate(layers))
                    + "</g>" for k in range(steps))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{left:.1f} {VIEW_Y:.1f} {width:.1f} {VIEW_H:.1f}">'
            f'<style>{css}</style><defs>{defs}{"".join(bands)}</defs>'
            f'<rect x="{-PAD}" width="{W + 2 * PAD}" height="{H}" fill="#000"/>'
            f'<g fill="none" stroke-linecap="round">{rest}{waves}</g></svg>')


for version, name in (("clear", "scene-reaching"), ("classic", "scene-reaching-classic")):
    svg = scene(version)
    out = HOOKS / f"{name}.js"
    out.write_text(f"// Generated by themes/reaching/make-scene.py ({version}): edit the generator, not this file.\n"
                   f"export const SCENE = {json.dumps(svg)}\n")
    out.with_suffix(".d.ts").write_text(f"/** The {version} Reaching backdrop: one SVG document. */\n"
                                        "export declare const SCENE: string\n")
    print(f"{version}: {len(svg):,} characters of SVG -> {out.name}")
picture = card()
(ROOT / "cards" / "reaching.svg").write_text(picture)
print(f"card: {len(picture):,} characters -> cards/reaching.svg")
