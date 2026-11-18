"""Promenade: the scene and its live card, drawn in code by brooklyn.py and themes/common/bridge_scene.py.

    python3 -I themes/promenade/make-scene.py          (from the repository root; needs numpy)

Writes plugins/promenade/hooks/scene-promenade.js (export const SCENE: one SVG document) and cards/promenade.svg (the
picker's live card: the picture with a small cyclist riding across). tools/build.py copies the
scene into the picker.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "common")]
import brooklyn  # noqa: E402
from bridge_scene import make  # noqa: E402

if __name__ == "__main__":
    make(brooklyn, "promenade", prefix="bk", glass=0.61, tint="#1d1a36", cap_colour="#48385c",
         ride=(1460, 1860, 880))   # ride: the card's cyclist, (from x, to x, deck y) or (x0, y0, x1, y1, size) in picture units
