# Maintaining Backdrops

How the repository works and how to change it. Backdrops is maintained by its author; bug reports go in an issue.

## Plugin names are immutable

The marketplace's name (`backdrops`) and each plugin's `name` in `.claude-plugin/marketplace.json` are permanent.
People have the plugins installed under these names, and renaming one breaks their install with a
`plugin-not-found` error.

- To change how a plugin is labelled, set `displayName`.
- If a rename can't be avoided, add the old name to the top-level `renames` map in `marketplace.json`
  (`"renames": { "old-name": "new-name" }`), so existing installs move to the new name.

`tools/check.py` fails if a published name disappears. A new plugin's name joins `PUBLISHED` in `tools/check.py`
when it is released; no name ever leaves it.

## Where things live

| Folder | What it holds |
|---|---|
| `themes/<id>/` | A theme's generator, `make-scene.py`, and its helpers. Scenes are only ever generated: edit the generator, never the scene it writes. |
| `themes/common/` | Code the generators share: `svglib.py` (compact paths, palms, towers, clouds), `bridges.py` and `bridge_scene.py` (the bridge rides' frame, highlight limiter, cyclist, scene and card), `rescale.py` and `card_scale.py` (shrink a scene into a card). Text contrast is measured by `tools/measure.py`. |
| `plugins/<id>/` | One installable plugin per theme, plus `plugins/backdrops/`, the picker with every theme. |
| `cards/<id>.svg` | Each theme's live card in the README. |
| `cards/<id>.webp` | Each theme's preview in the picker, made from its scene by `tools/make-photos.py`. |
| `shared/` | TypeScript every plugin shares, copied into each by `tools/build.py`. |
| `assets/live/` | The README's moving previews, made by `tools/make-previews.py`. |
| `tools/` | `build.py`, `make-previews.py`, `make-photos.py`, `check.py`, `measure.py`, and `app-versions.json`: the app versions the themes were last proven on. |

Each plugin installs on its own, so the parts plugins share are copied into each one rather than imported across
folders. `tools/build.py` does the copying: edit the source, never the copy.

A generator writes `plugins/<id>/hooks/scene-<id>.js` and `cards/<id>.svg`. The bridge rides' generators need
numpy. Ember's and Fractal Glass's scenes have no generator here and are committed as built.

## Add a theme

1. **Generator.** Write `themes/<id>/make-scene.py`. Start from the closest existing theme, and put anything a
   second theme could use in `themes/common/`. Keep the scene within the app's limits: one SVG document under
   131,072 characters, with at least one animation always running.
2. **Plugin.** Copy a single-theme plugin folder to `plugins/<id>/`, then rename its look module
   (`look-<id>.ts`) and the name in its `plugin.json`.
3. **Build lists.** In `tools/build.py`, add the id to `SINGLES` and `CARDS` and give it an entry in `SINGLE`.
   Add the plugin to `.claude-plugin/marketplace.json`.
4. **Picker.** In `plugins/backdrops/hooks/themes.ts`, import the look module, then add the theme to `THEMES`
   (in card order) and its problems to `PAINT_PROBLEMS`.
5. **Card and preview.** Write `cards/<id>.svg`, the README's live card: a still picture with one small animated
   layer, at most 20,000 characters (all cards together under 210,000). Then make the picker's preview with
   `python3 tools/make-photos.py <id>` (it needs Chrome and Pillow); run it again whenever the scene changes.
6. **Build.** Run the generator, then `python3 -I tools/build.py` and `python3 -I tools/make-previews.py`.
7. **Words.** Add the theme's section and preview to `README.md`, and its credits to `ARTWORK.md` if it uses
   anyone's art or music.
8. **Check.** Run `python3 tools/check.py --paint` (next section). Then open a new session in the desktop app,
   apply the theme, and confirm it still moves after the first few seconds and the text stays readable.

## Check every change

```
python3 tools/check.py
```

The checks are for this repository; a private copy needs none of them.

It works on a copy in a temporary folder and never writes to the repository. Each check prints one line, with
details only when something fails. It takes about ten seconds.

| Check | Fails when |
|---|---|
| `plugins` | a published plugin name is gone, or the marketplace, the plugin folders, `build.py`'s lists and `cards/` disagree |
| `privacy` | a tracked file holds a home-folder path, an email address, a secret, a date, a note about what someone said, or a word listed in `.git/info/private-terms` (git never commits that file) |
| `sizes` | a scene is over 131,072 characters, a card over 20,000, or all cards over 210,000 |
| `tests` | a plugin's tests fail, or print no pass/fail count (the count is read, never the exit status) |
| `validate` | `claude plugin validate` reports an error for a plugin or the marketplace |
| `types` | `tsc --noEmit` reports an error in any plugin |
| `rebuild` | running the generators, `build.py` and `make-previews.py` changes any file |
| `graphics` | never: it counts each scene's full-window masked layers |
| `app` | never: it says when the installed app differs from the one the themes were proven on |

With `--paint` it also measures each scene in Chrome, the way the app draws it (about 15 minutes). Chrome is not
the app: its version can differ from the app's Chromium, and a blurred glass is not modelled yet.

| Check | Fails when |
|---|---|
| `draw` | never: it notes any scene over 100 ms of raster time in 6 s at 3840 × 1620 |
| `contrast` | text behind the chat column falls below its layout's target (below) at any of 8 window sizes, 2 zooms and 9 moments of the animation. It reports each layout on its own line. Where a theme sets the app's glass, the glass is modelled over the column. |

| Layout | Primary | Secondary and muted |
|---|---|---|
| Usual: sidebar collapsed, right panel closed | 7:1 | 4.5:1 |
| Sidebar open | 4.5:1 | 3:1 |
| Right panel open | 4.5:1 | 3:1 |
| Sidebar and right panel both open | 4.5:1 | 3:1 |

A tool it can't find shows as `NOT RUN` with the fix, and the check exits 1, so nothing is skipped silently. It
finds `claude` (the engine bundled with the desktop app first), `tsc`, a python with numpy, and Chrome on its own,
or through `BACKDROPS_CLAUDE`, `BACKDROPS_TSC`, `BACKDROPS_PYTHON` and `BACKDROPS_CHROME`. The type check needs the
engine's type files, which the app writes into `plugins/<id>/.claude-plugin/types/` once it has loaded a plugin
from this folder. If no plugin in this checkout has them, set `BACKDROPS_TYPES` to such a folder.

**Graphics cost.** A masked full-window layer is painted off screen at window size whenever it changes. With many
sessions open, the app's graphics memory grows, and backdrops can freeze or go blank. Masked layers and paint time
are the suspected causes, but the link is not measured yet. A new theme should use no more of either than it needs.

**Pre-commit hook.** To run the fast checks (plugins, privacy, sizes, tests) on exactly what each commit records,
install the hook once per clone:

```
git config core.hooksPath tools/hooks
```

## When the app updates

`python3 tools/check.py` adds an `app` note when the installed desktop app, its engine or its Chromium differs from
`tools/app-versions.json`. Then:

1. Run `python3 tools/check.py --paint`. The tests run on the new engine, and the contrast and paint measures use
   the new browser if Chrome has moved to the same version.
2. In the desktop app, open a new session and apply each theme with `/backdrops <name> session`. Check that each
   one draws (not blank), still moves after the first few seconds, and keeps the chat text readable. Then open
   `/backdrops` and check that every preview shows and a click applies its theme.
3. Fix what broke. When every theme passes, record the versions and commit the file:

```
python3 tools/check.py --record-versions
```

## Release

1. `python3 tools/check.py` passes, with no `app` note.
2. Raise `version` in the `plugin.json` of each plugin that changed. The picker changes whenever any theme does.
   Installed copies update only when the version changes.
3. Commit, then tag each released plugin with `claude plugin tag plugins/<id>`, which checks that `plugin.json` and
   the marketplace agree.
4. Push the branch and the tags.
