#!/usr/bin/env python3
"""Make the picker's previews: cards/<id>.webp, each theme's real scene as the app draws it (an <img> in Chrome),
three seconds into its animation, at 320 x 180 px. Run from the repository's root after a scene changes, then
tools/build.py, which packs the previews into plugins/backdrops/hooks/photos.ts:

    python3 tools/make-photos.py [id ...]

It needs Google Chrome or Chromium (set BACKDROPS_CHROME to another) and Pillow (pip install pillow). The
previews are committed, so building the plugins needs neither.

Pausing at three seconds rather than drawing the scene's rest frame shows each theme lit and moving the way it
looks in use: every CSS `animation:` shorthand is shifted by -3 s and paused.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import CARDS, ROOT, scene_text  # noqa: E402
from measure import find_chrome  # noqa: E402

try:
    from PIL import Image
except ImportError:
    sys.exit("make-photos.py needs Pillow: pip install pillow")

AT = 3.0                        # seconds into the animation
RENDER = (1280, 720)            # CSS px the scene is drawn at (16:9, like the preview)
SIZE = (320, 180)               # the preview, in px: drawn at 92 x 52 CSS px, so sharp up to about 3x
QUALITY = 82
TIME = re.compile(r"^(-?[\d.]+)(m?s)$")


def seconds(token: str) -> float:
    match = TIME.match(token)
    assert match, token
    return float(match.group(1)) / (1000 if match.group(2) == "ms" else 1)


def paused_at(svg: str, t: float) -> str:
    """Every CSS animation shorthand paused at time t: its delay becomes delay - t, plus `paused`."""
    parts, last = [], 0
    for match in re.finditer(r"(?<![\w-])animation\s*:\s*([^;}\"'<]+)", svg):
        tokens = match.group(1).split()
        if not tokens or tokens[0].startswith("none"):
            continue
        if "," in match.group(1):
            sys.exit(f"a comma-separated animation list isn't supported: {match.group(1)}")
        tokens = [token for token in tokens if token not in ("running", "paused")]
        times = [i for i, token in enumerate(tokens) if TIME.match(token)]
        if not times:
            sys.exit(f"an animation without a duration: {' '.join(tokens)}")
        delay = seconds(tokens[times[1]]) if len(times) > 1 else 0.0
        shifted = f"{delay - t:.4f}".rstrip("0").rstrip(".") + "s"
        if len(times) > 1:
            tokens[times[1]] = shifted
        else:
            tokens.insert(times[0] + 1, shifted)
        parts += [svg[last:match.start(1)], " ".join(tokens) + " paused"]
        last = match.end(1)
    return "".join(parts) + svg[last:]


def scene_of(theme_id: str) -> Path:
    for scene in ROOT.glob(f"plugins/*/hooks/scene-{theme_id}.js"):
        if scene.parent.parent.name != "backdrops":
            return scene
    sys.exit(f"no scene-{theme_id}.js in a theme's plugin")


def photo(chrome: str, theme_id: str) -> Path:
    folder = Path(tempfile.mkdtemp(prefix="backdrops-photo-"))
    try:
        (folder / "scene.svg").write_text(paused_at(scene_text(scene_of(theme_id)), AT))
        w, h = RENDER
        (folder / "page.html").write_text(
            '<!doctype html><html><body style="margin:0;background:#000;overflow:hidden">'
            f'<img src="scene.svg" style="display:block;width:{w}px;height:{h}px"></body></html>')
        shot = folder / "shot.png"
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--use-mock-keychain",
                        "--password-store=basic", f"--user-data-dir={folder / 'profile'}",
                        "--allow-file-access-from-files", "--force-device-scale-factor=1",
                        f"--window-size={w},{h}", f"--screenshot={shot}", (folder / "page.html").as_uri()],
                       capture_output=True, timeout=180)
        if not shot.is_file():
            sys.exit(f"Chrome drew nothing for {theme_id}")
        image = Image.open(shot).convert("RGB").crop((0, 0, w, h))
        if max(image.getextrema(), key=lambda band: band[1])[1] < 8:
            sys.exit(f"{theme_id} rendered blank")
        out = ROOT / "cards" / f"{theme_id}.webp"
        image.resize(SIZE, Image.LANCZOS).save(out, "WEBP", quality=QUALITY, method=6)
        return out
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def main() -> None:
    chrome = find_chrome()
    if chrome is None:
        sys.exit("Chrome or Chromium not found: install one, or set BACKDROPS_CHROME")
    wanted = sys.argv[1:] or list(CARDS)
    for theme_id in wanted:
        if theme_id not in CARDS:
            sys.exit(f"{theme_id} isn't one of the picker's themes: {', '.join(CARDS)}")
        out = photo(chrome, theme_id)
        print(f"{out.relative_to(ROOT)}: {out.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
