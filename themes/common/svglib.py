"""Shared drawing primitives for the scene generators: compact path encoding, palms, towers, clouds.

Everything is in picture units of a 1920 x 1248 viewBox (the 1512 x 982 pt window's aspect).
Shapes are generated, never traced: palms from a frond model (spine arcs under gravity, leaflets
along both sides), towers from setback rules, clouds from summed sines.
"""
from __future__ import annotations

import math
import random

W, H = 1920, 1248


# ---------- compact path encoding ----------

def nums(values) -> str:
    out = []
    for i, v in enumerate(values):
        t = str(int(v))
        if i and not t.startswith("-"):
            out.append(" ")
        out.append(t)
    return "".join(out)


def poly(points, closed=True, scale=1) -> str:
    """Absolute first point, then relative integer steps ('l'); zero steps dropped."""
    pts = [(round(x * scale), round(y * scale)) for x, y in points]
    clean = [pts[0]]
    for p in pts[1:]:
        if p != clean[-1]:
            clean.append(p)
    d = f"M{clean[0][0]} {clean[0][1]}"
    steps = []
    for (x0, y0), (x1, y1) in zip(clean, clean[1:]):
        steps += [x1 - x0, y1 - y0]
    if steps:
        d += "l" + nums(steps)
    return d + ("z" if closed else "")


def area(points) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]))


def polys(list_of_points, closed=True, orient=False) -> str:
    """Several subpaths in one d. orient=True turns every polygon the same way round, so overlapping
    silhouettes in one path never cut holes in each other (nonzero fill)."""
    out = []
    for p in list_of_points:
        if len(p) < 2:
            continue
        if orient and area(p) < 0:
            p = p[::-1]
        out.append(poly(p, closed))
    return "".join(out)


# ---------- geometry helpers ----------

def bez(p0, p1, p2, t):
    a = (1 - t) ** 2
    b = 2 * (1 - t) * t
    c = t * t
    return (a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1])


def bez_d(p0, p1, p2, t):
    return (2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0]),
            2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1]))


def norm(v):
    length = math.hypot(*v) or 1.0
    return (v[0] / length, v[1] / length)


# ---------- palms ----------

class Palm:
    """A palm: a tapered, curved trunk and a crown of arching fronds with hanging leaflets.

    Fronds are spines arcing under gravity; leaflets hang from them like a comb, leaning outward,
    the outer row longer than the inner one. `crown(pose)` rotates the whole crown a few degrees
    (sway frames) and `flutter` adds per-frond jitter.
    """

    def __init__(self, seed, base, height, lean, trunk_w, frond_len, n_fronds=15, curve=0.0,
                 blades=12, droop=1.6, blade_len=0.6, hanging=2, gaps=True, leaf_width=0.34, leaf_angle=50, leaf_droop=0.5):
        self.rng = random.Random(seed)
        self.base = base
        self.top = (base[0] + lean, base[1] - height)
        self.ctrl = (base[0] + lean * 0.2 + curve, base[1] - height * 0.55)
        self.trunk_w = trunk_w
        self.blades = blades
        self.blade_len = blade_len
        self.gaps = gaps
        self.leaf_width = leaf_width
        self.leaf_angle = leaf_angle
        self.leaf_droop = leaf_droop
        rng = self.rng
        self.frond_specs = []
        for i in range(n_fronds):
            a = -172 + 164 * (i + rng.uniform(-0.3, 0.3)) / max(1, n_fronds - 1)
            up = math.cos(math.radians(a + 90))  # 1 when pointing straight up
            length = frond_len * rng.uniform(0.85, 1.1) * (1 - 0.3 * max(0.0, up) ** 3)
            g = droop * rng.uniform(0.8, 1.2) * (0.75 + 0.5 * (1 - max(0.0, up)))
            self.frond_specs.append({"a": a, "L": length, "g": g, "phase": rng.random(), "depth": rng.random()})
        for i in range(hanging):
            self.frond_specs.append({"a": rng.uniform(15, 165), "L": frond_len * rng.uniform(0.5, 0.7),
                                     "g": 0.35, "phase": rng.random(), "depth": rng.uniform(0.5, 1.0), "dead": i == 0})

    def trunk(self):
        left, right = [], []
        steps = 16
        for i in range(steps + 1):
            t = i / steps
            p = bez(self.base, self.ctrl, self.top, t)
            d = norm(bez_d(self.base, self.ctrl, self.top, t))
            n = (-d[1], d[0])
            w = self.trunk_w * (1.15 - 0.45 * t) + self.trunk_w * 0.9 * max(0.0, 1 - t * 7) ** 2
            w *= 1 + 0.04 * math.sin(t * 90)
            left.append((p[0] + n[0] * w / 2, p[1] + n[1] * w / 2))
            right.append((p[0] - n[0] * w / 2, p[1] - n[1] * w / 2))
        return left + right[::-1]

    def frond(self, spec, pose=0.0, flutter=0.0):
        """One frond: an arching rib with thin leaflets in a V, upper row rising then drooping,
        lower row hanging; leaflets longest a third of the way out, separated by gaps."""
        a = spec["a"] + pose + flutter * math.sin(spec["phase"] * 6.283)
        L, g = spec["L"], spec["g"]
        c = self.top
        u = (math.cos(math.radians(a)), math.sin(math.radians(a)))

        def spine(s):
            return (c[0] + u[0] * L * s, c[1] + u[1] * L * s + g * L * 0.6 * s * s)

        def tangent(s):
            return norm((u[0], u[1] + 2 * g * 0.6 * s))

        dead = spec.get("dead", False)
        K = self.blades if not dead else max(6, self.blades // 2)
        bl_max = L * self.blade_len * (0.7 if dead else 1.0)
        s0 = 0.12
        step = (1 - s0) / K
        width = self.leaf_width
        sides = []
        jitter = random.Random(int(spec["phase"] * 1e6))  # same leaflets in every sway pose
        for side in (-1, 1):  # -1: the row on the upper side of the rib, 1: the lower row
            pts = [spine(s0 * 0.5)]
            for k in range(K):
                s = s0 + step * k
                p = spine(s)
                t = tangent(s)
                n = (-t[1], t[0])
                if n[1] > 0:
                    n = (-n[0], -n[1])   # n points up
                if side == 1:
                    n = (-n[0], -n[1])
                f = (s - s0) / (1 - s0)
                theta = math.radians(self.leaf_angle - 28 * f + jitter.uniform(-7, 7))
                d = (t[0] * math.cos(theta) + n[0] * math.sin(theta), t[1] * math.cos(theta) + n[1] * math.sin(theta))
                droop = (self.leaf_droop if side == -1 else self.leaf_droop + 0.3) + 0.45 * f + (1.0 if dead else 0)
                d = norm((d[0], d[1] + droop))
                shape = math.sin(math.pi * min(1.0, 0.1 + 0.9 * f ** 0.7)) ** 0.85
                bl = bl_max * (0.25 + 0.75 * shape) * (0.92 if side == -1 else 1.0) * jitter.uniform(0.84, 1.12)
                tip = (p[0] + d[0] * bl, p[1] + d[1] * bl)
                p2 = spine(s + step * width)
                if self.gaps:
                    pts += [p, tip, p2]
                else:
                    pts += [p, tip]
            pts.append(spine(1.0))
            for k in range(K, -1, -4):
                sb = min(1.0, s0 + step * k)
                q = spine(sb)
                t = tangent(sb)
                w = 2.6 * (1 - sb) + 0.6
                pts.append((q[0] - t[1] * w * side * 0.5, q[1] + t[0] * w * side * 0.5))
            sides.append(pts)
        return sides

    def tip(self, i):
        spec = self.frond_specs[i]
        a = math.radians(spec["a"])
        L, g = spec["L"], spec["g"]
        return (self.top[0] + math.cos(a) * L, self.top[1] + math.sin(a) * L + g * L * 0.6)

    def crown(self, pose=0.0, flutter=0.0, which=None, hub=True):
        """Polygons of the crown, back fronds first; `which` filters specs by index."""
        specs = sorted(enumerate(self.frond_specs), key=lambda e: e[1]["depth"])
        out = []
        for i, spec in specs:
            if which is not None and i not in which:
                continue
            out += self.frond(spec, pose, flutter)
        # the crown's heart: coconuts tucked under a rosette of short frond bases that hides the joint
        if not hub:
            return out
        hub = self.top
        tw = self.trunk_w
        r = tw * 0.3
        for dx, dy in ((-0.32, 0.5), (0.3, 0.55), (0.0, 0.78)):
            cx, cy = hub[0] + dx * tw, hub[1] + dy * tw
            out.append([(cx + r * math.cos(k * 0.785), cy + r * math.sin(k * 0.785)) for k in range(8)])
        for k in range(11):
            a = math.radians(-178 + 176 * k / 10)
            ln = tw * (1.9 + 0.5 * math.sin(k * 1.7))
            ux, uy = math.cos(a), math.sin(a)
            nx, ny = -uy, ux
            w = tw * 0.32
            tip = (hub[0] + ux * ln, hub[1] + uy * ln + ln * 0.35)   # a little droop
            mid = (hub[0] + ux * ln * 0.55, hub[1] + uy * ln * 0.55 + ln * 0.1)
            out.append([(hub[0] + nx * w, hub[1] + ny * w), (mid[0] + nx * w * 0.6, mid[1] + ny * w * 0.6), tip,
                        (mid[0] - nx * w * 0.6, mid[1] - ny * w * 0.6), (hub[0] - nx * w, hub[1] - ny * w)])
        return out


# ---------- towers ----------

def tower_shape(rng, x, w, h, ground, style):
    """Silhouette of a tower standing on `ground`: setbacks, a crown, maybe a spire."""
    top = ground - h
    pts = [(x, ground), (x, top + h * 0.0)]
    if style == "setback":
        s1 = top + h * rng.uniform(0.08, 0.16)
        inset = w * rng.uniform(0.12, 0.2)
        s2 = top
        pts = [(x, ground), (x, s1), (x + inset, s1), (x + inset, s2), (x + w - inset, s2),
               (x + w - inset, s1), (x + w, s1), (x + w, ground)]
    elif style == "spire":
        sp = h * rng.uniform(0.12, 0.2)
        mid = x + w / 2
        pts = [(x, ground), (x, top + sp), (mid - w * 0.12, top + sp * 0.6), (mid, top),
               (mid + w * 0.12, top + sp * 0.6), (x + w, top + sp), (x + w, ground)]
    elif style == "slant":
        pts = [(x, ground), (x, top + h * 0.1), (x + w, top), (x + w, ground)]
    elif style == "round":
        # was a dome (it read as out of place): now a flat roof with clipped corners, a modern
        # Miami tower top. Same height, and no random draws, so no other tower moves
        c = w * 0.18
        pts = [(x, ground), (x, top + c), (x + c, top), (x + w - c, top), (x + w, top + c), (x + w, ground)]
    else:  # flat with a rooftop box
        bw = w * 0.35
        pts = [(x, ground), (x, top + 14), (x + w * 0.3, top + 14), (x + w * 0.3, top),
               (x + w * 0.3 + bw, top), (x + w * 0.3 + bw, top + 14), (x + w, top + 14), (x + w, ground)]
    return pts


# ---------- clouds ----------

def cloud(rng, cx, cy, length, thick, bumps=5):
    """A long lenticular streak: bumpy top, flat bottom, tapered ends."""
    top, bottom = [], []
    n = 22
    phases = [rng.uniform(0, 6.28) for _ in range(3)]
    for i in range(n + 1):
        t = i / n
        x = cx - length / 2 + length * t
        env = math.sin(math.pi * t) ** 0.8
        bump = 1 + 0.35 * math.sin(t * bumps * math.pi + phases[0]) + 0.2 * math.sin(t * 13 + phases[1])
        top.append((x, cy - thick * env * bump))
        bottom.append((x, cy + thick * 0.25 * env))
    return top + bottom[::-1]
