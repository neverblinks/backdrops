#!/usr/bin/env python3
"""Measure scenes the way the app draws them: as an <img> in Chrome. `tools/check.py --paint` runs it; it prints
one JSON line per scene.

    python3 tools/measure.py draw [scene-id ...]
        Paint cost: Chrome's raster and paint time while the scene animates for 6 s at 3840 x 1620 pt, the
        app's zoom. The same setup for every scene, so the numbers compare on one Mac; lower is lighter.

    python3 tools/measure.py contrast [--layout closed|sidebar|panel|both ...] [scene-id ...]
        Text contrast: the brightest 6 pt box behind the chat column, at 8 window sizes and zoom 100% and
        131%, worst over 9 moments of the scene's longest loop, in each layout (default all four): closed (sidebar
        collapsed, info panel closed), sidebar (sidebar open), panel (info panel open) and both. Each render serves every
        layout: only where the column sits changes. Where the theme sets the app's glass (a tint at some opacity
        over the chat column, following it in every layout), the glass is modelled over the column (its tint and
        opacity; a blurred glass is not modelled yet). Needs numpy and Pillow.

Chrome is $BACKDROPS_CHROME, else Google Chrome or Chromium in /Applications, else one on PATH.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import ROOT, SINGLES, scene_text  # noqa: E402

ZOOM = 1.2 ** 1.5                      # the app's zoom
SIZES = [(1280, 800), (1512, 949), (1728, 1117), (2560, 1440), (2560, 1080), (3440, 1440), (3840, 1620), (5120, 2160)]
PHASES = 9                             # moments sampled evenly over the scene's longest loop
COLUMN = 733                           # the chat column, CSS px
GUTTER = 51                            # its least margin each side when the window is narrow, CSS px: measured in the
                                       # app on a 1512 pt window with the sidebar and the right panel both open
TOP, BOTTOM, BOX = 90, 130, 6          # pt kept clear of text at the top (title bar) and bottom (composer); glyph box
JOBS = 6                               # Chrome renders at once
SIDEBAR, PANEL = 279, 319              # CSS px the sidebar and the info panel take from the window
LAYOUTS = ("closed", "sidebar", "panel", "both")
PAINT_EVENTS = {"RasterTask", "TileManager::RunTasks", "PaintLayerContents", "Paint", "ImageDecodeTask", "PaintImage",
                "SVGImage::DrawForContainer", "SVGImage::Draw", "DisplayItemList::Raster",
                "RasterBufferProvider::PlaybackToMemory"}


def find_chrome() -> str | None:
    candidates = [os.environ.get("BACKDROPS_CHROME", ""),
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Chromium.app/Contents/MacOS/Chromium",
                  shutil.which("google-chrome") or "", shutil.which("chromium") or ""]
    return next((c for c in candidates if c and os.access(c, os.X_OK)), None)


def scenes(ids: list[str]) -> list[tuple[str, Path, Path]]:
    """Each single plugin's scene with the look module that shows it: (scene id, scene file, look module)."""
    found = []
    for plugin in SINGLES:
        for scene in sorted((ROOT / "plugins" / plugin / "hooks").glob("scene-*.js")):
            scene_id = scene.stem[len("scene-"):]
            if not ids or scene_id in ids:
                found.append((scene_id, scene, scene.with_name(f"look-{scene_id}.ts")))
    return found


def look(path: Path) -> tuple[dict[str, str], float, str, float]:
    """The theme's text colours and its glass (blur, tint, opacity), read from its look module. A version that
    borrows its colours from another look module (Reaching Classic) gets them from there."""
    text = path.read_text()
    colours = dict(re.findall(r"'(text-primary|text-secondary|text-muted)': '(#[0-9a-fA-F]{6})'", text))
    if not colours:
        for other in re.findall(r"from '\./(look-[\w-]+)'", text):
            colours = look(path.with_name(f"{other}.ts"))[0] or colours
    match = re.search(r"glass: \{ blur: ([\d.]+), tint: '#([0-9a-fA-F]{6})', opacity: ([\d.]+) \}", text)
    if match is None:
        if "glass:" in text:   # a glass this can't read must not be measured as no glass
            raise ValueError(f"{path.name}: can't read its glass (expected {{ blur: N, tint: '#rrggbb', opacity: N }})")
        return colours, 0.0, "000000", 0.0
    return colours, float(match.group(1)), match.group(2), float(match.group(3))


def page(folder: Path, width: float, height: float, extra: str = "") -> Path:
    html = folder / "page.html"
    html.write_text(f'<html><body style="margin:0;background:#000"><img src="scene.svg" '
                    f'style="display:block;width:{width}px;height:{height}px">{extra}</body></html>')
    return html


def draw_cost(chrome: str, scene_id: str, scene: Path) -> dict:
    folder = Path(tempfile.mkdtemp(prefix="backdrops-draw-"))
    try:
        (folder / "scene.svg").write_text(scene_text(scene))
        width, height = 3840 / ZOOM, 1620 / ZOOM
        html = page(folder, width, height, "<script>setTimeout(() => window.close(), 6000)</script>")
        trace = folder / "trace.json"
        process = subprocess.Popen(
            [chrome, "--headless=new", "--hide-scrollbars", f"--force-device-scale-factor={ZOOM}",
             "--allow-file-access-from-files", f"--window-size={int(width)},{int(height)}",
             f"--user-data-dir={folder / 'profile'}", "--trace-startup=cc,viz,gpu,disabled-by-default-cc.debug,blink",
             f"--trace-startup-file={trace}", "--trace-startup-duration=6", "--trace-startup-format=json",
             html.as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(40):            # Chrome writes the trace when the 6 s are up
            time.sleep(0.5)
            if trace.is_file() and trace.stat().st_size > 1000:
                time.sleep(1.5)
                break
        stop(process)
        events = json.loads(trace.read_text()) if trace.is_file() else []
        events = events["traceEvents"] if isinstance(events, dict) else events
        total = sum(e["dur"] for e in events if e.get("ph") == "X" and e.get("dur") and e.get("name") in PAINT_EVENTS)
        return {"kind": "draw", "scene": scene_id, "ms": round(total / 1000) if events else None}
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def stop(process: subprocess.Popen) -> None:
    """Ends Chrome and every helper it started: a hung headless Chrome ignores a polite request."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def screenshot(chrome: str, zoom: float, folder: Path, css_w: float, css_h: float, html: Path) -> None:
    """One headless screenshot. Headless Chrome now and then never exits: give each try a minute, try twice."""
    shot = folder / "shot.png"
    for _ in range(2):
        shot.unlink(missing_ok=True)
        process = subprocess.Popen([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                                    f"--force-device-scale-factor={zoom}", "--allow-file-access-from-files",
                                    f"--user-data-dir={folder / 'profile'}",
                                    f"--window-size={int(css_w) + 2},{int(css_h) + 2}", f"--screenshot={shot}",
                                    html.as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True)
        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            stop(process)
            continue
        if shot.is_file():
            return
    raise RuntimeError(f"Chrome made no screenshot at {css_w:.0f}x{css_h:.0f} CSS px")


def loop_length(svg: str) -> float:
    """The longest animation cycle in the scene, s."""
    return max((float(d) for d in re.findall(r"(\d[\d.]*)s step-end infinite", svg)), default=0.0)


def paused_at(svg: str, moment: float) -> str:
    """The scene with every animation paused `moment` seconds in: each delay shifted back by it, then paused."""
    paused = re.sub(r"(\d[\d.]*)s step-end infinite (-?[\d.]+)s",
                    lambda m: f"{m.group(1)}s step-end infinite {float(m.group(2)) - moment:g}s paused", svg)
    return paused.replace("</style>", "*{animation-play-state:paused!important}</style>", 1)


def linear(c):
    import numpy as np
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(rgb):
    return 0.2126 * linear(rgb[..., 0]) + 0.7152 * linear(rgb[..., 1]) + 0.0722 * linear(rgb[..., 2])


def hex_luminance(colour: str) -> float:
    import numpy as np
    return float(luminance(np.array([[int(colour[i:i + 2], 16) for i in (1, 3, 5)]], float))[0])


def brightest_box(region, k: int) -> float:
    """The brightest k x k box anywhere in the region (sliding, not a grid), from an integral image."""
    import numpy as np
    total = np.pad(region, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    boxes = total[k:, k:] - total[:-k, k:] - total[k:, :-k] + total[:-k, :-k]
    return float(boxes.max()) / (k * k) if boxes.size else 0.0


def column(layout: str, width: int, zoom: float) -> tuple[int, int]:
    """The chat column's left and right edge, pt: centred in what the sidebar or the info panel leaves of the
    window, at most COLUMN wide, with at least GUTTER each side."""
    left = SIDEBAR * zoom if layout in ("sidebar", "both") else 0
    right = PANEL * zoom if layout in ("panel", "both") else 0
    wide = min(COLUMN * zoom, width - left - right - 2 * GUTTER * zoom)
    x0 = int(round(left + (width - left - right) / 2 - wide / 2))
    return x0, x0 + int(wide)


def brightest_behind_text(chrome: str, svg: str, moment: float, width: int, height: int, zoom: float,
                          layouts: tuple[str, ...], glass: tuple[float, str, float]) -> dict[str, float]:
    """Draws the scene paused at `moment` in a width x height pt window at `zoom` and, for each layout, lays the
    theme's glass over the chat column and returns the luminance of the brightest 6 pt box behind the text."""
    import numpy as np
    from PIL import Image
    blur, tint_hex, opacity = glass
    folder = Path(tempfile.mkdtemp(prefix="backdrops-contrast-"))
    try:
        (folder / "scene.svg").write_text(paused_at(svg, moment))
        css_w, css_h = width / zoom, height / zoom
        screenshot(chrome, zoom, folder, css_w, css_h, page(folder, css_w, css_h))
        rgb = np.asarray(Image.open(folder / "shot.png").convert("RGB"), float)[:height, :width].copy()
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    tint = np.array([int(tint_hex[i:i + 2], 16) for i in (0, 2, 4)], float)
    found = {}
    for layout in layouts:
        x0, x1 = column(layout, width, zoom)
        # the app's glass follows the column: its tint at its opacity, blended in sRGB values
        behind = rgb[TOP:height - BOTTOM, x0:x1] * (1 - opacity) + tint * opacity
        found[layout] = brightest_box(luminance(behind), BOX)
    return found


def contrast(chrome: str, chosen: list[tuple[str, Path, Path]], layouts: tuple[str, ...]) -> list[dict]:
    """Every scene at every size, zoom and phase in every layout, all renders sharing one pool of Chrome
    processes; one result per scene and layout."""
    plans, jobs = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=JOBS) as pool:
        for scene_id, scene, look_module in chosen:
            colours, blur, tint_hex, opacity = look(look_module)
            if blur > 0:   # how strongly the app blurs for a given value is not measured yet
                raise ValueError(f"{scene_id}: a blurred glass (blur {blur:g}) is not modelled; measure it in the app")
            svg = scene_text(scene)
            loop = loop_length(svg)
            moments = sorted({round(loop * i / (PHASES - 1), 3) for i in range(PHASES)}) if loop else [0.0]
            plans[scene_id] = (colours, opacity > 0)
            for zoom in (1.0, ZOOM):
                for width, height in SIZES:
                    for moment in moments:
                        future = pool.submit(brightest_behind_text, chrome, svg, moment, width, height, zoom,
                                             layouts, (blur, tint_hex, opacity))
                        jobs.append((scene_id, f"{width}x{height}@{zoom * 100:.0f}%", future))
        worst: dict[tuple[str, str], dict[str, float]] = {}
        failed: dict[str, str] = {}
        for scene_id, size, future in jobs:
            try:
                values = future.result()
            except Exception as error:
                failed.setdefault(scene_id, str(error))
                continue
            for layout, value in values.items():
                sizes = worst.setdefault((scene_id, layout), {})
                sizes[size] = max(sizes.get(size, 0.0), value)
    results = []
    for scene_id, (colours, has_glass) in plans.items():
        if scene_id in failed:
            results.append({"error": f"{scene_id}: {failed[scene_id]}"})
            continue
        text = {role: hex_luminance(colours[f"text-{role}"]) for role in ("primary", "secondary", "muted")}
        for layout in layouts:
            ratios = {size: {role: round((lum + 0.05) / (value + 0.05), 2) for role, lum in text.items()}
                      for size, value in worst[(scene_id, layout)].items()}
            results.append({"kind": "contrast", "scene": scene_id, "layout": layout, "glass": has_glass,
                            "ratios": ratios})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("what", choices=["draw", "contrast"])
    parser.add_argument("scenes", nargs="*", help="scene ids (default: every scene)")
    parser.add_argument("--layout", choices=LAYOUTS, action="append", help="repeat for several (default: all four)")
    options = parser.parse_args()
    chrome = find_chrome()
    if chrome is None:
        print(json.dumps({"error": "no Chrome found: install Google Chrome or set BACKDROPS_CHROME"}))
        return 1
    chosen = scenes(options.scenes)
    if options.what == "draw":
        for scene_id, scene, _ in chosen:     # one at a time: parallel runs would slow each other's raster
            print(json.dumps(draw_cost(chrome, scene_id, scene)), flush=True)
    else:
        try:
            results = contrast(chrome, chosen, tuple(options.layout or LAYOUTS))
        except ValueError as error:
            print(json.dumps({"error": str(error)}))
            return 1
        for result in results:
            print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
