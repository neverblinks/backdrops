"""Coast Road: the scene and its live card, drawn in code by bixby.py and themes/common/bridge_scene.py.

    python3 -I themes/coast-road/make-scene.py          (from the repository root; needs numpy)

Writes plugins/coast-road/hooks/scene-coast-road.js (export const SCENE: one SVG document) and cards/coast-road.svg (the
picker's live card: the picture with a small cyclist riding across). tools/build.py copies the
scene into the picker.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "common")]
import bixby  # noqa: E402
from bridge_scene import make  # noqa: E402

if __name__ == "__main__":
    make(bixby, "coast-road", prefix="bx", glass=0.58, tint="#171735", cap_colour="#48385e",
         ride=(1300, 1780, 500))   # ride: the card's cyclist, (from x, to x, deck y) or (x0, y0, x1, y1, size) in picture units
