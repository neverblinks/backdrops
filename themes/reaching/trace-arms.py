#!/usr/bin/env python3
"""Trace Reaching's forearms past the artwork's edges from Michelangelo's fresco, in the artwork's own dots.

    python3 -I themes/reaching/trace-arms.py <fresco.jpg>      (needs numpy and opencv-python)

Writes themes/reaching/fresco-arms.json, which make-scene.py adds to the artwork's dots. Only that file is
committed: the fresco scan is not, fetch it yourself (public domain, Wikimedia Commons:
"Michelangelo - Creation of Adam (cropped).jpg", 3524 x 1599 px).

The artwork stops at its frame, about a hand's length past each wrist, so on windows wider than a laptop the
forearms ended in mid-air. Past each edge this fills in what the fresco shows there, nothing else: Adam's
forearm widening toward his elbow, God's rising toward his. How:

1. Each dot hand was registered onto the fresco (one similarity transform per hand, fitted to the fresco's
   skin; 83% and 78% of the dots land on the painted hands). The maps are below.
2. The artwork's two dot kinds split by the fresco's light at each dot: dense where it is brighter than a
   threshold, small below it. The threshold is learned here (it classifies 80% of the artwork's dots).
3. Past the edges, every point of the artwork's grid (21.1-unit rows, 11.25-unit columns) inside each arm's
   outline becomes a dot of the kind the fresco's light there calls for. The outlines were read off the
   fresco warped into picture units; near each seam they ease from the artwork's own edge (80 units).
"""
import json, math, sys
from pathlib import Path
import numpy as np
import cv2

here = Path(__file__).resolve().parent
dots = json.loads((here / "reference-dots.json").read_text())
fresco = cv2.imread(sys.argv[1])
if fresco is None or fresco.shape[1] != 3524:
    raise SystemExit("expected the 3524 x 1599 px Wikimedia scan of the fresco")
# picture units -> px of the fresco scaled to 1600 wide, one map per hand
REG = {"L": {"map": [[0.139808, 0.007327, 476.774501], [-0.007327, 0.139808, 236.627168], [0.0, 0.0, 1.0]]}, "R": {"map": [[0.139808, 0.007327, 462.191768], [-0.007327, 0.139808, 248.17872], [0.0, 0.0, 1.0]]}}
FULL = fresco.shape[1] / 1600                                    # the maps are in 1600-px fresco units
lab = cv2.cvtColor(fresco, cv2.COLOR_BGR2LAB)
light = cv2.GaussianBlur(lab[:, :, 0].astype(np.float32), (0, 0), 3.2)
bgr = fresco.astype(np.int32)
b, g, r = bgr[:, :, 0], bgr[:, :, 1], bgr[:, :, 2]
skin = ((r - b > 52) & (r > 95) & (r - g > 18)).astype(np.float32)
skin = cv2.GaussianBlur(skin, (0, 0), 3.0)

ROW, PITCH, REACH = 21.1, 11.25, 520


def at(side, x, y):
    m = np.array(REG[side]["map"])
    px, py, _ = m @ np.array([x, y, 1.0])
    X, Y = int(round(px * FULL)), int(round(py * FULL))
    if not (0 <= X < fresco.shape[1] and 0 <= Y < fresco.shape[0]):
        return None
    return float(light[Y, X]), float(skin[Y, X])


# 1. the artwork's language
dense_l, small_l = [], []
for x, y, a in dots:
    s = at("L" if x < 1000 else "R", x, y)
    if s:
        (dense_l if a > 20 else small_l).append(s[0])
dense_l, small_l = np.array(dense_l), np.array(small_l)
cands = np.arange(60, 240, 1.0)
acc = [((dense_l >= t).sum() + (small_l < t).sum()) / (len(dense_l) + len(small_l)) for t in cands]
T = float(cands[int(np.argmax(acc))])
print(f"light threshold dense/small: {T:.0f} of 255 (classifies {max(acc):.0%} of the artwork's dots); "
      f"dense median {np.median(dense_l):.0f}, small median {np.median(small_l):.0f}")

# the grid rows: the artwork's own, carried on at the same pitch
rows = sorted({round(y, 1) for _, y, _ in dots})
centres, cur = [], []
for y in rows:
    if cur and y - cur[-1] >= 6:
        centres.append(round(sum(cur) / len(cur), 1)); cur = []
    cur.append(y)
centres.append(round(sum(cur) / len(cur), 1))
while centres[0] - ROW > 0:
    centres.insert(0, round(centres[0] - ROW, 1))
while centres[-1] + ROW < 1293:
    centres.append(round(centres[-1] + ROW, 1))

# 2. past the edges. The arms' outlines, read off the fresco warped into picture units (on a
# 100-unit grid): Adam's forearm widens toward the elbow, his knee sits below it, apart; God's forearm
# rises toward the elbow between the folds of his red mantle. Near each seam the outline eases from the
# artwork's own edge to the fresco's (80 units), so the join doesn't step.
OUTLINE = {
    "L": ([(0, 496), (-100, 515), (-200, 537), (-300, 539), (-400, 544), (-520, 549)],
          [(0, 797), (-100, 853), (-200, 920), (-300, 967), (-373, 980), (-440, 984), (-520, 987)]),
    "R": ([(2000, 445), (2100, 400), (2200, 380), (2300, 363), (2400, 357), (2520, 350)],
          [(2000, 757), (2100, 771), (2200, 777), (2300, 780), (2400, 767), (2520, 747)]),
}


def interp(pts, x):
    pts = sorted(pts)
    if x <= pts[0][0]:
        return pts[0][1]
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        if xa <= x <= xb:
            return ya + (yb - ya) * (x - xa) / (xb - xa)
    return pts[-1][1]


out = []
for side, edge, step in (("L", 8.0, -1), ("R", 1990.0, 1)):
    near = [y for x, y, _ in dots if abs(x - edge) < 30]
    art_top, art_bot = min(near), max(near)
    top_pts, bot_pts = OUTLINE[side]
    d_top = art_top - interp(top_pts, edge); d_bot = art_bot - interp(bot_pts, edge)
    k = 1
    while True:
        x = edge + step * k * PITCH
        if abs(x - edge) > REACH:
            break
        ease = math.exp(-abs(x - edge) / 80)
        top = interp(top_pts, x) + d_top * ease
        bot = interp(bot_pts, x) + d_bot * ease
        for y in centres:
            if top - 4 <= y <= bot + 4:
                s_ = at(side, x, y)
                if s_:
                    out.append([round(x, 1), y, 44 if s_[0] >= T else 8])
        k += 1
print("dots added: left", sum(1 for d in out if d[0] < 0), "right", sum(1 for d in out if d[0] > 2000))
(here / "fresco-arms.json").write_text(json.dumps(out, separators=(",", ":")))

