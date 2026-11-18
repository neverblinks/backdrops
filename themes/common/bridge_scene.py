"""The bridge-ride scenes' shared build: the scene document and the picker's live card, written into the plugin.

Each theme's make-scene.py names its scene module and a few numbers and calls make(). The scene keeps to the
app's limits: under 131,072 characters, animation as the full shorthand with step-end and explicit % stops on a
0.125 s beat (opacity and transforms on groups), and a highlight limiter behind the text. The app's glass dims
the chat column and follows it when the sidebar or the right panel opens.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from bridges import Motion, document, limiter
from card_scale import drop_unused, scale_svg, simplify

ROOT = Path(__file__).resolve().parent.parent.parent
SCENE_MAX = 131072


def short_ids(svg, prefix):
    ids = re.findall(rf'\bid="({prefix}-[^"]+)"', svg)
    assert len(ids) == len(set(ids)), "duplicate id"
    names = list("abcdefghijklmnopqrstuvwxyz") + [a + b for a in "abcdefghijklmnopqrstuvwxyz" for b in "abcdefghijklmnopqrstuvwxyz"]
    for old, new in zip(sorted(ids, key=lambda i: -svg.count(f"#{i})")), names):
        svg = svg.replace(f'id="{old}"', f'id="{new}"').replace(f"url(#{old})", f"url(#{new})")
    return re.sub(r'(?<=[="\s,(:-])0\.(?=\d)', ".", svg)


def check(svg):
    refs = set(re.findall(r"url\(#([^)]+)\)", svg))
    ids = set(re.findall(r'\bid="([^"]+)"', svg))
    assert refs <= ids, f"missing defs: {refs - ids}"
    css = svg[svg.index("<style>"):svg.index("</style>")]
    for c in set(re.findall(r'class="([^"]+)"', svg)):
        assert f".{c}{{" in css, f"class {c} has no rule"
    assert "steps(" not in css and not re.search(r"[{}]\s*(to|from)\s*\{", css)


def scene(scene_module, prefix, glass, tint, cap_colour):
    m = Motion()
    defs, body, _ = scene_module.scene(m)
    svg = short_ids(document(m, defs, body), prefix)
    # the limiter goes in after short_ids(), which would also have dropped its numbers' leading zeros
    svg = svg[:-len("</svg>")] + limiter(cap_colour, glass, tint) + "</svg>"
    check(svg)
    if len(svg) > SCENE_MAX:
        raise SystemExit(f"scene is {len(svg):,} characters, over {SCENE_MAX:,}")
    return svg


def mini_rider(k):
    """A small cyclist at the origin (rear wheel on the ground), in card units."""
    r, wb = 9 * k, 30 * k
    return (f'<g fill="none" stroke="#15111d" stroke-width="{2.4 * k:.2f}"><circle cy="{-r:.1f}" r="{r:.1f}"/><circle cx="{wb:.1f}" cy="{-r:.1f}" r="{r:.1f}"/>'
            f'<path d="M0 {-r:.1f}l{12 * k:.1f} 0 {10 * k:.1f} {-14 * k:.1f}H{7 * k:.1f}l{5 * k:.1f} {14 * k:.1f}M{wb:.1f} {-r:.1f}l{-6 * k:.1f} {-17 * k:.1f}"/>'
            f'<path stroke-width="{6 * k:.1f}" stroke-linecap="round" d="M{7 * k:.1f} {-28 * k:.1f}l{13 * k:.1f} {-12 * k:.1f}M{9 * k:.1f} {-26 * k:.1f}l{4 * k:.1f} {14 * k:.1f}"/>'
            f'<circle cx="{23 * k:.1f}" cy="{-44 * k:.1f}" r="{4 * k:.1f}" fill="#15111d"/></g>')


def card(scene_module, ride):
    scene_module.CARD = True
    defs, body, _ = scene_module.scene(Motion())
    scene_module.CARD = False
    # the card's own still rider is replaced by a moving one
    flat = re.sub(r'<g(?: transform="[^"]*")? fill="none" stroke="#(?:15111d|0d111a)" stroke-width="2.4">.*?</g>', "", "".join(body), count=1, flags=re.S)
    inner = re.sub(r' class="m\d+"|<!--[^>]*-->', "", f'<defs>{"".join(defs)}</defs>{flat}')
    k = 704 / 1920
    still = simplify(drop_unused(scale_svg(inner, k, 0, 84)))
    if len(ride) == 3:
        x0, x1, y0 = ride
        y1, size = y0, 1.0
    else:
        x0, y0, x1, y1, size = ride
    cx0, cx1, cy0, cy1 = x0 * k, x1 * k, (y0 - 84) * k, (y1 - 84) * k
    beats = 36                                   # 4.5 s across, one step a beat (the scene's own pace)
    stops = "".join(f"{100 * i / beats:.3f}".rstrip("0").rstrip(".") + f"%{{transform:translate({cx0 + (cx1 - cx0) * i / beats:.1f}px,{cy0 + (cy1 - cy0) * i / beats:.1f}px)}}"
                    for i in range(beats)) + f"100%{{transform:translate({cx1:.1f}px,{cy1:.1f}px)}}"
    style = ("<style>@keyframes cr{" + stops + "}.cr{animation:cr 4.5s step-end infinite 0s}"
             "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>")
    rider = f'<g class="cr" transform="translate({cx0:.1f} {cy0:.1f})">{mini_rider(k * size)}</g>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 704 396">{style}{still}{rider}</svg>'


def make(scene_module, theme_id, prefix, glass, tint, cap_colour, ride):
    """Writes plugins/<theme_id>/hooks/scene-<theme_id>.js and cards/<theme_id>.svg.

    prefix: the scene module's id prefix (shortened away); glass and tint: the app's glass over the chat column, as
    the theme's look-<theme_id>.ts sets it; cap_colour: the highlight limiter's cap under that glass; ride: the
    card's cyclist, (from x, to x, deck y) or (x0, y0, x1, y1, size) in picture units.
    """
    svg = scene(scene_module, prefix, glass, tint, cap_colour)
    (ROOT / f"plugins/{theme_id}/hooks/scene-{theme_id}.js").write_text(
        f"// Generated by themes/{theme_id}/make-scene.py: edit the generator, not this file.\nexport const SCENE = {json.dumps(svg)}\n")
    c = card(scene_module, ride)
    (ROOT / f"cards/{theme_id}.svg").write_text(c)
    print(f"{theme_id}: scene {len(svg):,} characters, card {len(c):,}")
