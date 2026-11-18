"""Ocean Road: the scene and its live card, drawn in code by causeway.py and themes/common/bridge_scene.py.

    python3 -I themes/ocean-road/make-scene.py          (from the repository root; needs numpy)

Writes plugins/ocean-road/hooks/scene-ocean-road.js (export const SCENE: one SVG document) and cards/ocean-road.svg (the
picker's live card: the picture with a small cyclist riding across). tools/build.py copies the
scene into the picker.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "common")]
import causeway  # noqa: E402
from bridge_scene import make  # noqa: E402

if __name__ == "__main__":
    make(causeway, "ocean-road", prefix="cw", glass=0.52, tint="#0b1626", cap_colour="#364052",
         ride=(60, 1092, 1000, 992, 1.45))   # ride: the card's cyclist, (from x, to x, deck y) or (x0, y0, x1, y1, size) in picture units
