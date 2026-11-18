"""Crossing Hour: the scene and its live card, drawn in code by tower.py and themes/common/bridge_scene.py.

    python3 -I themes/crossing-hour/make-scene.py          (from the repository root; needs numpy)

Writes plugins/crossing-hour/hooks/scene-crossing-hour.js (export const SCENE: one SVG document) and cards/crossing-hour.svg (the
picker's live card: the picture with a small cyclist riding across). tools/build.py copies the
scene into the picker.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "common")]
import tower  # noqa: E402
from bridge_scene import make  # noqa: E402

if __name__ == "__main__":
    make(tower, "crossing-hour", prefix="tb", glass=0.61, tint="#141634", cap_colour="#4e3863",
         ride=(120, 520, 909))   # ride: the card's cyclist, (from x, to x, deck y) or (x0, y0, x1, y1, size) in picture units
