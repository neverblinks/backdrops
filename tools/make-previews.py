#!/usr/bin/env python3
"""Make the README's live previews: assets/live/<theme>.svg, each the theme's real animated scene
(the same SVG the app draws) with a sample conversation drawn on top in the app's layout and the
theme's own text colours. Run from the repository's root after tools/build.py:

    python3 -I tools/make-previews.py

GitHub shows an SVG in a README as an image, and browsers run the animation inside it, so the
README moves like the app. The scene is identical to the app's; the chat on top is a drawing of
the app's layout (1512 x 982 pt window, sidebar collapsed), not a screenshot of it.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import CARDS, ROOT, scene_text  # noqa: E402

PICKER = ROOT / "plugins" / "backdrops" / "hooks"
OUT = ROOT / "assets" / "live"
W, H = 1512, 982
ZOOM = 1.2 ** 1.5           # the app's zoom
FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Helvetica Neue', sans-serif"
MONO = "'SF Mono', Menlo, monospace"


def colours(theme_id: str) -> dict[str, str]:
    """The theme's text and surface colours, read from its look module's palette anchors."""
    text = (PICKER / f"look-{theme_id}.ts").read_text()
    return dict(re.findall(r"'(text-primary|text-secondary|text-muted|surface-1|surface-2)': '(#[0-9a-f]{6})'", text))


def glass(theme_id: str) -> str:
    """The app's glass, when the theme sets one: its tint at its opacity over the chat column (733 CSS px), easing
    to nothing over 205 CSS px each side, as measured in the app. Blur is not drawn."""
    text = (PICKER / f"look-{theme_id}.ts").read_text()
    match = re.search(r"glass: \{ blur: [\d.]+, tint: '(#[0-9a-fA-F]{6})', opacity: ([\d.]+) \}", text)
    if match is None or float(match.group(2)) == 0:
        return ""
    tint, opacity = match.group(1), float(match.group(2))
    half, fade = 366.5 * ZOOM, 205 * ZOOM
    stops = []
    for i in range(9):                     # a smoothstep from the column's edge outward, both sides
        t = i / 8
        strength = 1 - t * t * (3 - 2 * t)
        for x in (W / 2 - half - fade * t, W / 2 + half + fade * t):
            stops.append((x / W, strength))
    stops.sort()
    gradient = "".join(f'<stop offset="{x:.4f}" stop-color="{tint}" stop-opacity="{opacity * k:.3f}"/>' for x, k in stops)
    return (f'<linearGradient id="glass" x2="1">{gradient}</linearGradient>'
            f'<rect width="{W}" height="{H}" fill="url(#glass)"/>')


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def chat(c: dict[str, str]) -> str:
    """A sample exchange in the app's layout: a user bubble, a thinking line, a reply, the composer."""
    primary, secondary, muted = c["text-primary"], c["text-secondary"], c["text-muted"]
    bubble = c.get("surface-1", "#111111")
    parts = []
    # the user's message, right-aligned in a rounded bubble
    parts.append(f'<rect x="1018" y="120" width="221" height="58" rx="14" fill="{bubble}" fill-opacity=".92" stroke="#ffffff" stroke-opacity=".14"/>')
    parts.append(f'<text x="1218" y="156" text-anchor="end" font-family="{FONT}" font-size="17" fill="{primary}" style="font-family:{FONT};font-size:17px;font-weight:400;text-anchor:end">set a backdrop</text>')
    # the thinking summary, muted
    parts.append(f'<text x="278" y="244" font-family="{FONT}" font-size="16" fill="{muted}" style="font-family:{FONT};font-size:16px;font-weight:400;text-anchor:start">Thinking about which backdrop suits a long coding session…</text>')
    lines = [
        (primary, "Here it is. The picture stays behind the conversation, and every few seconds"),
        (primary, "something in it moves: a wave, a glow, a light on the water."),
        (primary, ""),
        (primary, "Behind the text the picture is kept dark enough that long replies stay easy to read,"),
        (primary, "while the edges of the window keep the art at full brightness."),
    ]
    y = 292
    for colour, line in lines:
        if line:
            parts.append(f'<text x="278" y="{y}" font-family="{FONT}" font-size="17" fill="{colour}" style="font-family:{FONT};font-size:17px;font-weight:400;text-anchor:start">{escape(line)}</text>')
        y += 29
    parts.append(f'<text x="278" y="{y + 6}" font-family="{MONO}" font-size="15" fill="{secondary}" style="font-family:{MONO};font-size:15px;font-weight:400;text-anchor:start">/backdrops after hours</text>')
    # the composer and the line under it
    parts.append(f'<rect x="252" y="872" width="1008" height="56" rx="14" fill="{bubble}" fill-opacity=".94" stroke="#ffffff" stroke-opacity=".16"/>')
    parts.append(f'<text x="290" y="906" font-family="{FONT}" font-size="17" fill="{muted}" style="font-family:{FONT};font-size:17px;font-weight:400;text-anchor:start">Reply…</text>')
    return "".join(parts)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for theme_id in CARDS:
        art = scene_text(PICKER / f"scene-{theme_id}.js")
        # the scene's own root becomes a nested picture filling the window. Scenes whose root is in CSS px (no
        # viewBox: their overlays, such as a limiter, are placed in screen units) get a viewBox in CSS px at the
        # app's zoom, so those land where the app draws them; single-viewBox scenes keep theirs.
        if re.match(r'^<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">', art):
            art = art.replace('<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">',
                              f'<svg x="0" y="0" width="{W}" height="{H}" viewBox="0 0 {W / ZOOM:.2f} {H / ZOOM:.2f}">', 1)
        else:
            art = re.sub(r'^<svg xmlns="http://www.w3.org/2000/svg"', f'<svg x="0" y="0" width="{W}" height="{H}"', art, count=1)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
               f'<rect width="{W}" height="{H}" fill="#000"/>{art}{glass(theme_id)}{chat(colours(theme_id))}</svg>')
        (OUT / f"{theme_id}.svg").write_text(svg)
        print(f"assets/live/{theme_id}.svg: {len(svg):,} characters")


if __name__ == "__main__":
    main()
