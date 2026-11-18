#!/usr/bin/env python3
"""Assemble the plugins from their shared parts. Run from the repository's root after changing anything
in shared/, cards/, a theme's look module or scene, or LICENSE / ARTWORK.md:

    python3 -I tools/build.py

Each plugin is installed on its own (only its folder is copied to someone's machine), so the parts
they share are copied into each one rather than imported across folders:

  shared/theme.ts            -> every plugin's hooks/
  shared/music.snippet.ts    -> pasted between the `// >>> music` and `// <<< music` lines of each
                               register module (the engine wants every use of $ in that module)
  shared/single.register.template.ts -> hooks/register.ts of every single-theme plugin but magenta-hour,
                               whose own module adds its built-in music (the engine wants each
                               plugin's hooks written out in its own module)
  shared/single.test.template.ts -> tests/<name>.test.ts of the same plugins
  each theme's look-*.ts, scene-*.js/.d.ts, make-colors.*  -> plugins/backdrops/hooks/ (the picker),
                               except Reaching Classic, which only the single reaching plugin has
  plugins/magenta-hour/music -> plugins/backdrops/music
  cards/<id>.webp            -> plugins/backdrops/hooks/photos.ts (the picker's previews; tools/make-photos.py
                               makes them from the scenes)
  LICENSE, ARTWORK.md        -> every plugin (the notices travel with each install)

It stops on a scene over the app's 131,072-character limit, a README card (cards/<id>.svg) over 20,000 or all
of them over 210,000, or a picker preview over 12,000 bytes. Edit the sources, never the copies.
"""
import base64
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
PICKER = PLUGINS / "backdrops"
SINGLES = ["reaching", "magenta-hour", "after-hours", "ember", "fractal-glass", "crossing-hour", "promenade", "coast-road", "ocean-road"]
# the picker's themes, each with cards/<id>.svg (the README's live card) and cards/<id>.webp (the picker's preview),
# in the picker's order
CARDS = ("reaching", "magenta-hour", "after-hours", "crossing-hour", "promenade", "coast-road", "ocean-road", "fractal-glass", "ember")
# in a single plugin but not in the picker (one Reaching in the picker is enough)
NOT_IN_PICKER = {"scene-reaching-classic.js", "scene-reaching-classic.d.ts", "look-reaching-classic.ts"}
SCENE_MAX, CARD_MAX, CARDS_MAX, PHOTO_MAX = 131_072, 20_000, 210_000, 12_000
# a single-theme plugin's second version, for its generated test
TEST_SECOND = {"reaching": {"version": "classic", "scene": "reaching-classic"}}
# the single-theme plugins whose register.ts is generated: what each imports and says
SINGLE = {
    "reaching": ("Reaching", "import { REACHING, REACHING_PROBLEMS } from './look-reaching'\n"
                 "import { REACHING_CLASSIC } from './look-reaching-classic'",
                 "[REACHING, REACHING_CLASSIC]", "REACHING_PROBLEMS",
                 "Reaching backdrop: clear (default), classic (with a tint), or off"),
    "after-hours": ("After Hours", "import { AFTER_HOURS, AFTER_HOURS_PROBLEMS } from './look-after-hours'",
                    "[AFTER_HOURS]", "AFTER_HOURS_PROBLEMS", "After Hours backdrop (a synthwave Miami night), or off"),
    "ember": ("Night Hearth", "import { EMBER, EMBER_PROBLEMS } from './look-ember'",
              "[EMBER]", "EMBER_PROBLEMS", "Night Hearth backdrop (a warm glow in the corner), or off"),
    "fractal-glass": ("Fractal Glass", "import { FRACTAL_GLASS, FRACTAL_GLASS_PROBLEMS } from './look-fractal-glass'",
        "[FRACTAL_GLASS]", "FRACTAL_GLASS_PROBLEMS", "Fractal Glass backdrop (a blue glow behind fluted glass), or off"),
    "crossing-hour": ("Crossing Hour", "import { CROSSING_HOUR, CROSSING_HOUR_PROBLEMS } from './look-crossing-hour'",
        "[CROSSING_HOUR]", "CROSSING_HOUR_PROBLEMS", "Crossing Hour backdrop (Tower Bridge at sunset), or off"),
    "promenade": ("Promenade", "import { PROMENADE, PROMENADE_PROBLEMS } from './look-promenade'",
        "[PROMENADE]", "PROMENADE_PROBLEMS", "Promenade backdrop (the Brooklyn Bridge at dusk), or off"),
    "coast-road": ("Coast Road", "import { COAST_ROAD, COAST_ROAD_PROBLEMS } from './look-coast-road'",
        "[COAST_ROAD]", "COAST_ROAD_PROBLEMS", "Coast Road backdrop (Bixby Creek Bridge, Big Sur), or off"),
    "ocean-road": ("Ocean Road", "import { OCEAN_ROAD, OCEAN_ROAD_PROBLEMS } from './look-ocean-road'",
        "[OCEAN_ROAD]", "OCEAN_ROAD_PROBLEMS", "Ocean Road backdrop (the Atlantic Ocean Road, Norway), or off"),
}


def fail(message: str) -> None:
    sys.exit(f"build stopped: {message}")


def scene_text(path: Path) -> str:
    match = re.search(r'^export const SCENE = (".*?")\s*$', path.read_text(), re.S | re.M)
    if match is None:
        fail(f"{path} has no SCENE line")
    return json.loads(match.group(1))


MUSIC_START = "// >>> music: pasted from shared/music.snippet.ts by tools/build.py (edit that file)"
MUSIC_END = "// <<< music"


def paste_music(text: str, snippet: str) -> str:
    """Puts the music snippet between the markers, replacing whatever was there."""
    start = text.index(MUSIC_START) + len(MUSIC_START)
    end = text.index(MUSIC_END, start)
    return text[:start] + "\n" + snippet + text[end:]


def main() -> None:
    shared = ROOT / "shared"
    snippet = (shared / "music.snippet.ts").read_text()
    for module in (PICKER / "hooks" / "register.tsx", PLUGINS / "magenta-hour" / "hooks" / "register.ts"):
        module.write_text(paste_music(module.read_text(), snippet))
    for name in SINGLES + ["backdrops"]:
        hooks = PLUGINS / name / "hooks"
        shutil.copy2(shared / "theme.ts", hooks / "theme.ts")
        for notice in ("LICENSE", "ARTWORK.md"):
            shutil.copy2(ROOT / notice, PLUGINS / name / notice)
    template = (shared / "single.test.template.ts").read_text()
    code = paste_music((shared / "single.register.template.ts").read_text(), snippet)
    for name, (title, imports, themes, problems, description) in SINGLE.items():
        (PLUGINS / name / "hooks" / "register.ts").write_text(
            code.replace("__IMPORTS__", imports).replace("__TITLE__", title).replace("__PLUGIN__", name)
            .replace("__THEMES__", themes).replace("__PROBLEMS__", problems).replace("__DESCRIPTION__", description))
        second = TEST_SECOND.get(name)
        test = (template.replace("__PLUGIN__", name).replace("__FIRST__", name)
                .replace("__SECOND__", json.dumps(second) if second else "undefined"))
        (PLUGINS / name / "tests").mkdir(exist_ok=True)
        (PLUGINS / name / "tests" / f"{name}.test.ts").write_text(test)

    # scenes: check size, then copy each theme's look module and scene into the picker
    for name in SINGLES:
        hooks = PLUGINS / name / "hooks"
        for scene in sorted(hooks.glob("scene-*.js")):
            size = len(scene_text(scene))
            if size > SCENE_MAX:
                fail(f"{scene.relative_to(ROOT)} is {size:,} characters, over {SCENE_MAX:,}")
            print(f"{scene.relative_to(ROOT)}: {size:,} characters")
            for part in (scene, scene.with_suffix(".d.ts")):
                if part.name not in NOT_IN_PICKER:
                    shutil.copy2(part, PICKER / "hooks" / part.name)
        for look in hooks.glob("look-*.ts"):
            if look.name not in NOT_IN_PICKER:
                shutil.copy2(look, PICKER / "hooks" / look.name)
    for stale in NOT_IN_PICKER:
        (PICKER / "hooks" / stale).unlink(missing_ok=True)
    for helper in ("make-colors.js", "make-colors.d.ts"):
        shutil.copy2(PLUGINS / "reaching" / "hooks" / helper, PICKER / "hooks" / helper)
    music = PLUGINS / "magenta-hour" / "music"
    (PICKER / "music").mkdir(exist_ok=True)
    for track in sorted(music.glob("*.m4a")):
        shutil.copy2(track, PICKER / "music" / track.name)

    # the README's live cards: checked here, shown only by the README
    total = 0
    for theme_id in CARDS:
        svg = (ROOT / "cards" / f"{theme_id}.svg").read_text()
        for bad in ("data:", "<image", "foreignObject", "<script"):
            if bad in svg:
                fail(f"cards/{theme_id}.svg contains {bad!r}")
        if len(svg) > CARD_MAX:
            fail(f"cards/{theme_id}.svg is {len(svg):,} characters, over {CARD_MAX:,}")
        total += len(svg)
    if total > CARDS_MAX:
        fail(f"all cards together are {total:,} characters, over {CARDS_MAX:,}")
    print(f"cards: {len(CARDS)} README cards, {total:,} characters together (limit {CARDS_MAX:,})")

    # the picker's previews
    lines, size = [], 0
    for theme_id in CARDS:
        data = (ROOT / "cards" / f"{theme_id}.webp").read_bytes()
        if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
            fail(f"cards/{theme_id}.webp is not a WebP image")
        if len(data) > PHOTO_MAX:
            fail(f"cards/{theme_id}.webp is {len(data):,} bytes, over {PHOTO_MAX:,}")
        size += len(data)
        lines.append(f"  {json.dumps(theme_id)}: 'data:image/webp;base64,{base64.b64encode(data).decode()}',")
    (PICKER / "hooks" / "cards.ts").unlink(missing_ok=True)
    (PICKER / "hooks" / "photos.ts").write_text(
        "// Generated by tools/build.py from cards/*.webp (made by tools/make-photos.py): edit those.\n"
        "/** Each theme's preview in the picker: its scene three seconds in, 320 x 180 px. */\n"
        "export const PHOTOS: Readonly<Record<string, string>> = {\n" + "\n".join(lines) + "\n}\n")
    print(f"photos: {len(CARDS)} previews, {size:,} bytes together")

if __name__ == "__main__":
    main()
