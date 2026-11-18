#!/usr/bin/env python3
"""Check the repository before every commit and release. Run from the repository's root:

    python3 tools/check.py                    every check
    python3 tools/check.py --fast             plugins, privacy, sizes and tests only (the pre-commit hook)
    python3 tools/check.py --fast --staged    the same, on what is staged for the next commit
    python3 tools/check.py --verbose          details for passing checks too (the graphics table)
    python3 tools/check.py --paint            also measure paint cost and text contrast in Chrome (~15 min)
    python3 tools/check.py --record-versions  after proving the themes on a new app: save its versions

It never writes to the repository. Everything runs on a copy in a temporary folder: the working tree's
files (tracked and new, not ignored), or with --staged exactly what is staged. Each check prints one
line: `ok`, `FAIL`, `NOT RUN` (a tool is missing: the line says how to fix it), or `note`. Details
follow only on failure. It exits 1 if any check failed or did not run, so nothing is skipped silently.

Tools it needs, found without any machine-specific path:
  claude   $BACKDROPS_CLAUDE, else the engine bundled with the Claude desktop app (the one that loads
           the themes), else `claude` on PATH
  tsc      $BACKDROPS_TSC, else `tsc` on PATH (npm install -g typescript)
  types    the `.claude-plugin/types/` folder the engine writes when it loads a plugin: $BACKDROPS_TYPES,
           else one already in a plugin of this checkout or another worktree of this repository
  numpy    for the bridge themes' generators: $BACKDROPS_PYTHON, else the first python3 on PATH that
           has it (with Pillow too for --paint's contrast)
  Chrome   for --paint only: $BACKDROPS_CHROME, else Google Chrome or Chromium (see tools/measure.py)
Private words to keep out of the repository (names, handles) go one per line in
`.git/info/private-terms`, which git never commits.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import mmap
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import CARD_MAX, CARDS, CARDS_MAX, SCENE_MAX, SINGLES, scene_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VERSIONS_FILE = ROOT / "tools" / "app-versions.json"
APP = Path("/Applications/Claude.app")
ENGINES = Path.home() / "Library" / "Application Support" / "Claude" / "claude-code"


class Result:
    def __init__(self, name: str, status: str, summary: str, details: str = ""):
        self.name, self.status, self.summary, self.details = name, status, summary, details

    @property
    def blocks(self) -> bool:
        return self.status in ("FAIL", "NOT RUN")


def ok(name: str, summary: str, details: str = "") -> Result:
    return Result(name, "ok", summary, details)


def fail(name: str, summary: str, details: str = "") -> Result:
    return Result(name, "FAIL", summary, details)


def not_run(name: str, summary: str) -> Result:
    return Result(name, "NOT RUN", summary)


def run(args: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: int = 300) -> tuple[int, str]:
    """Runs one program (no shell, no pipes) and returns its exit status and its output, stdout then stderr."""
    try:
        done = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout} s"
    except OSError as error:
        return 127, str(error)
    return done.returncode, done.stdout + done.stderr


def tail(text: str, lines: int = 20) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


# ---------------------------------------------------------------------------------------- the copy

def make_copy(staged: bool) -> Path:
    """The files to check, copied into a temporary folder: what is staged, or the working tree's files."""
    copy = Path(tempfile.mkdtemp(prefix="backdrops-check-"))
    if staged:
        subprocess.run(["git", "checkout-index", "--all", f"--prefix={copy}/"], cwd=ROOT, check=True)
        return copy
    for name in git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0"):
        source = ROOT / name
        if name and source.is_file():
            target = copy / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return copy


def files_in(copy: Path) -> list[Path]:
    return sorted(p for p in copy.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def fingerprint(copy: Path) -> dict[str, str]:
    return {str(p.relative_to(copy)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files_in(copy)}


# ---------------------------------------------------------------------------------- finding tools

def version_key(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text))


def find_claude() -> Path | None:
    if os.environ.get("BACKDROPS_CLAUDE"):
        chosen = Path(os.environ["BACKDROPS_CLAUDE"])
        return chosen if chosen.is_file() else None
    if ENGINES.is_dir():
        bundled = sorted(ENGINES.glob("*/*/claude.app/Contents/MacOS/claude"),
                         key=lambda p: version_key(p.relative_to(ENGINES).parts[0]))
        if bundled:
            return bundled[-1]
    found = shutil.which("claude")
    return Path(found) if found else None


def find_tsc() -> Path | None:
    found = os.environ.get("BACKDROPS_TSC") or shutil.which("tsc")
    return Path(found) if found and Path(found).is_file() else None


def find_types() -> Path | None:
    """A `.claude-plugin/types/` folder the engine wrote. They are the same for every plugin of one engine."""
    if os.environ.get("BACKDROPS_TYPES"):
        chosen = Path(os.environ["BACKDROPS_TYPES"])
        return chosen if (chosen / "tsconfig.json").is_file() else None
    trees = [ROOT] + [Path(line[len("worktree "):]) for line in git("worktree", "list", "--porcelain").splitlines()
                      if line.startswith("worktree ")]
    for tree in trees:
        for types in sorted(tree.glob("plugins/*/.claude-plugin/types")):
            if (types / "tsconfig.json").is_file():
                return types
    return None


def find_numpy_python(modules: str = "numpy") -> str | None:
    candidates = [os.environ.get("BACKDROPS_PYTHON", ""), sys.executable]
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        candidates.append(os.path.join(folder, "python3"))
    seen = set()
    for python in candidates:
        if not python or python in seen or not os.access(python, os.X_OK):
            continue
        seen.add(python)
        if run([python, "-E", "-c", f"import {modules}"], cwd=ROOT)[0] == 0:
            return python
    return None


# --------------------------------------------------------------------------------------- the checks

# Published plugin names, and the marketplace's own. People have them installed under these names: a name that
# disappears breaks their install (plugin not found). Add names here; never remove one (CONTRIBUTING.md).
MARKETPLACE = "backdrops"
PUBLISHED = ("backdrops", "reaching", "magenta-hour", "after-hours", "ember", "fractal-glass", "crossing-hour",
             "promenade", "coast-road", "ocean-road", "night-hearth")


def check_plugins(copy: Path) -> Result:
    """Published names are all still there; the marketplace, the plugin folders, the build's lists and the cards
    all name the same themes."""
    problems = []
    marketplace = json.loads((copy / ".claude-plugin" / "marketplace.json").read_text())
    listed = {entry["name"] for entry in marketplace["plugins"]}
    if marketplace.get("name") != MARKETPLACE:
        problems.append(f"the marketplace is named {marketplace.get('name')!r}, not {MARKETPLACE!r}: every install breaks")
    renames = marketplace.get("renames", {})
    for name in PUBLISHED:
        if name not in listed and renames.get(name) not in listed:
            problems.append(f"published plugin {name!r} is gone from marketplace.json, with no rename to a listed plugin")
    folders = {p.name for p in (copy / "plugins").iterdir() if (p / ".claude-plugin" / "plugin.json").is_file()}
    built = set(SINGLES) | {"backdrops"}
    cards = {p.stem for p in (copy / "cards").glob("*.svg")}
    if listed != folders:
        problems.append(f"marketplace.json and plugins/ differ: {sorted(listed ^ folders)}")
    if built != folders:
        problems.append(f"tools/build.py SINGLES and plugins/ differ: {sorted(built ^ folders)}")
    if set(CARDS) != cards:
        problems.append(f"tools/build.py CARDS and cards/ differ: {sorted(set(CARDS) ^ cards)}")
    photos = {p.stem for p in (copy / "cards").glob("*.webp")}
    if set(CARDS) != photos:
        problems.append(f"tools/build.py CARDS and the previews (cards/*.webp) differ: {sorted(set(CARDS) ^ photos)}")
    for name in sorted(folders):
        manifest = json.loads((copy / "plugins" / name / ".claude-plugin" / "plugin.json").read_text())
        if manifest.get("name") != name:
            problems.append(f"plugins/{name}/.claude-plugin/plugin.json is named {manifest.get('name')!r}")
    if problems:
        return fail("plugins", f"{len(problems)} mismatch(es)", "\n".join(problems))
    return ok("plugins", f"{len(folders)} plugins match the marketplace, the build and the cards; "
                         f"all {len(PUBLISHED)} published names kept")


# Patterns are written so this file does not match itself (an escaped dot, a character class).
HOME_PATH = re.compile(rb"/Users/[A-Za-z0-9_]|/home/[a-z][a-z0-9_-]*/|~/\.claude|~/\.config/(?!backdrops)")
EMAIL = re.compile(rb"[A-Za-z0-9._%+-]{2,}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:com|net|org|io|dev|app|me|co|edu|ai)\b")
SECRET = re.compile(rb"sk-an[t]-|sk-[A-Za-z0-9]{30,}|AIza[0-9A-Za-z_-]{20}|ghp_[A-Za-z0-9]{20}|xox[baprs]-|-----BEGIN [A-Z ]*PRIVATE KEY-----")
DATE = re.compile(rb"\b20\d\d-[01]\d-[0-3]\d\b")
NOTE = re.compile(rb"(?i)\b(?:the )?user (?:said|asked|wanted|wants|approved|rejected|requested|prefers|liked)\b")
BINARY = {".m4a", ".webp", ".png", ".jpg", ".mp3", ".wav"}


def private_terms() -> list[bytes]:
    """The account name of whoever runs the check, plus the words in .git/info/private-terms."""
    terms = {Path.home().name}
    listed = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()) / "info" / "private-terms"
    if listed.is_file():
        terms |= {line.strip() for line in listed.read_text().splitlines() if line.strip() and not line.startswith("#")}
    return [term.lower().encode() for term in terms if len(term) >= 3]


def prose(path: Path, data: bytes) -> bytes:
    """The part of a file people write: a scene module minus its generated SCENE line, an SVG's comments."""
    if path.suffix == ".js" and path.name.startswith("scene-"):
        return b"\n".join(line for line in data.splitlines() if not line.startswith(b"export const SCENE = "))
    if path.suffix == ".svg":
        return b"\n".join(re.findall(rb"<!--(.*?)-->", data, re.S))
    return data


def check_privacy(copy: Path) -> Result:
    terms = private_terms()
    found = []
    files = files_in(copy)
    for path in files:
        name = str(path.relative_to(copy))
        data = path.read_bytes()
        rules = [("a home folder path", HOME_PATH, data), ("an email address", EMAIL, data), ("a secret", SECRET, data)]
        if path.suffix not in BINARY:
            written = prose(path, data)
            rules += [("a date", DATE, written), ("a note about what someone said", NOTE, written)]
        for label, pattern, content in rules:
            if pattern.search(content):
                found.append(f"{name}: {label}")
        lowered = data.lower()
        for term in terms:
            if term in lowered:
                found.append(f"{name}: a private word (from the account name or .git/info/private-terms)")
                break
    if found:
        return fail("privacy", f"{len(found)} finding(s)", "\n".join(found))
    return ok("privacy", f"{len(files)} files clean")


def check_sizes(copy: Path) -> Result:
    problems, largest = [], (0, "")
    for scene in sorted(copy.glob("plugins/*/hooks/scene-*.js")):
        size = len(scene_text(scene))
        largest = max(largest, (size, scene.stem[len("scene-"):]))
        if size > SCENE_MAX:
            problems.append(f"{scene.relative_to(copy)}: {size:,} characters, over {SCENE_MAX:,}")
    total = 0
    for theme_id in CARDS:
        card = copy / "cards" / f"{theme_id}.svg"
        size = len(card.read_text()) if card.is_file() else 0
        total += size
        if size > CARD_MAX:
            problems.append(f"cards/{theme_id}.svg: {size:,} characters, over {CARD_MAX:,}")
    if total > CARDS_MAX:
        problems.append(f"all cards together: {total:,} characters, over {CARDS_MAX:,}")
    if problems:
        return fail("sizes", f"{len(problems)} over the limit", "\n".join(problems))
    return ok("sizes", f"largest scene {largest[0]:,} of {SCENE_MAX:,} ({largest[1]}); "
                       f"cards {total:,} of {CARDS_MAX:,}")


def plugin_folders(copy: Path) -> list[Path]:
    return sorted(p for p in (copy / "plugins").iterdir() if (p / ".claude-plugin" / "plugin.json").is_file())


def engine_version(claude: Path) -> str:
    status, output = run([str(claude), "--version"], cwd=ROOT)
    match = re.search(r"\d+\.\d+\.\d+", output)
    return match.group(0) if status == 0 and match else "unknown"


def one_test(claude: Path, plugin: Path) -> tuple[str, int, int, str]:
    """Runs one plugin's tests. Trusts the printed summary, not the exit status: no summary is a failure."""
    status, output = run([str(claude), "plugin", "test", str(plugin)], cwd=plugin)
    passed = re.search(r"^\s*(\d+) pass\s*$", output, re.M)
    failed = re.search(r"^\s*(\d+) fail\s*$", output, re.M)
    if not passed or not failed:
        return plugin.name, 0, 1, "no pass/fail summary in its output:\n" + tail(output)
    p, f = int(passed.group(1)), int(failed.group(1))
    if p == 0:
        return plugin.name, 0, max(f, 1), "no test ran:\n" + tail(output)
    if f or status != 0:
        return plugin.name, p, max(f, 1), tail(output, 40)
    return plugin.name, p, 0, ""


def check_tests(copy: Path, claude: Path | None) -> Result:
    if claude is None:
        return not_run("tests", "no claude found: install the Claude desktop app or set BACKDROPS_CLAUDE")
    with concurrent.futures.ThreadPoolExecutor() as pool:
        results = list(pool.map(lambda plugin: one_test(claude, plugin), plugin_folders(copy)))
    passed, failed = sum(r[1] for r in results), sum(r[2] for r in results)
    summary = f"{passed} pass, {failed} fail in {len(results)} plugins (engine {engine_version(claude)})"
    if failed:
        return fail("tests", summary, "\n".join(f"{name}:\n{details}" for name, _, f, details in results if f))
    return ok("tests", summary)


def one_validation(claude: Path, target: Path, label: str) -> str:
    """Returns '' when valid, else what is wrong. Reads the JSON report, not the exit status."""
    status, output = run([str(claude), "plugin", "validate", "--json", str(target)], cwd=target)
    try:
        report = json.loads(output[output.index("{"): output.rindex("}") + 1])
    except ValueError:
        return f"{label}: unreadable report:\n{tail(output)}"
    errors = list(report.get("manifest", {}).get("errors", []))
    for content in report.get("contents", []):
        errors += content.get("errors", [])
    if report.get("success") is not True or errors or status != 0:
        return f"{label}: " + ("; ".join(str(e) for e in errors) or tail(output))
    return ""


def check_validate(copy: Path, claude: Path | None) -> Result:
    if claude is None:
        return not_run("validate", "no claude found: install the Claude desktop app or set BACKDROPS_CLAUDE")
    targets = [(copy, "marketplace")] + [(p, p.name) for p in plugin_folders(copy)]
    with concurrent.futures.ThreadPoolExecutor() as pool:
        problems = [p for p in pool.map(lambda t: one_validation(claude, *t), targets) if p]
    if problems:
        return fail("validate", f"{len(problems)} of {len(targets)} invalid", "\n".join(problems))
    return ok("validate", f"the marketplace and {len(targets) - 1} plugins valid")


def check_types(copy: Path) -> Result:
    tsc, types = find_tsc(), find_types()
    if tsc is None:
        return not_run("types", "no tsc found: npm install -g typescript, or set BACKDROPS_TSC")
    if types is None:
        return not_run("types", "no engine type files: open any of these plugins once in the app, "
                                "or set BACKDROPS_TYPES to a plugin's .claude-plugin/types folder")
    plugins = plugin_folders(copy)
    for plugin in plugins:
        target = plugin / ".claude-plugin" / "types"
        if not target.exists():
            shutil.copytree(types, target)

    def one(plugin: Path) -> tuple[str, int, str]:
        status, output = run([str(tsc), "-p", str(plugin.relative_to(copy)), "--noEmit", "--pretty", "false"], cwd=copy)
        return plugin.name, status, output

    with concurrent.futures.ThreadPoolExecutor() as pool:
        results = list(pool.map(one, plugins))
    bad = [f"{name}:\n{tail(output, 30)}" for name, status, output in results if status != 0 or "error TS" in output]
    if bad:
        return fail("types", f"tsc errors in {len(bad)} of {len(plugins)} plugins", "\n".join(bad))
    return ok("types", f"tsc clean in {len(plugins)} plugins")


def check_rebuild(copy: Path) -> Result:
    """Regenerates every scene that has a generator here, rebuilds the plugins and the README previews,
    and fails if any file comes out different: the sources and their outputs must be committed together."""
    generators = sorted(copy.glob("themes/*/make-scene.py"))
    python = find_numpy_python()
    if python is None:
        return not_run("rebuild", "the bridge generators need numpy: pip install numpy, or set BACKDROPS_PYTHON")
    before = fingerprint(copy)
    steps = [([python, "-E", "-B", str(g)], str(g.relative_to(copy))) for g in generators]
    steps += [([sys.executable, "-I", "-B", "tools/build.py"], "tools/build.py"),
              ([sys.executable, "-I", "-B", "tools/make-previews.py"], "tools/make-previews.py")]
    for args, label in steps:
        status, output = run(args, cwd=copy)
        if status != 0:
            return fail("rebuild", f"{label} failed", tail(output))
    after = fingerprint(copy)
    changed = sorted(name for name in before if after.get(name) != before[name])
    added = [name for name in sorted(set(after) - set(before)) if not ignored(name)]
    with_generator = {g.parent.name for g in generators}
    regenerated = f"{len(with_generator & set(SINGLES))} of {len(SINGLES)} themes regenerated"
    if changed or added:
        details = [f"changed: {n}" for n in changed] + [f"new: {n}" for n in added]
        return fail("rebuild", f"{regenerated}; {len(details)} file(s) differ from the generated output: "
                               "run the generators and tools/build.py, then commit their output", "\n".join(details))
    return ok("rebuild", f"{regenerated}, plugins and previews rebuilt: no file changed")


def ignored(name: str) -> bool:
    done = subprocess.run(["git", "check-ignore", "--no-index", "-q", name], cwd=ROOT)
    return done.returncode == 0


# ------------------------------------------------------------------------------------- graphics cost

SVG = "{http://www.w3.org/2000/svg}"


def layer_kinds(element: ET.Element) -> list[str]:
    """What makes the browser paint this element into a layer of its own before compositing it."""
    style = element.get("style", "")
    kinds = []
    if element.get("mask") or "mask:" in style:
        kinds.append("mask")
    if element.get("filter") or "filter:" in style:
        kinds.append("filter")
    if element.get("clip-path") or "clip-path:" in style:
        kinds.append("clip")
    if "mix-blend-mode" in style or element.get("mix-blend-mode"):
        kinds.append("blend")
    opacity = element.get("opacity")
    if opacity is not None and element.tag in (SVG + "g", SVG + "svg") and float(opacity) < 1:
        kinds.append("opacity")
    return kinds


def full_window(element: ET.Element) -> bool:
    return element.tag in (SVG + "g", SVG + "svg") and element.get("transform") is None and \
        element.get("width", "100%") == "100%" and element.get("height", "100%") == "100%"


def graphics_cost(svg: str) -> dict[str, int]:
    """Counts the layers that cover the whole window: containers reached from the root through other
    full-window containers only. Each one is painted off screen at window size every frame it changes."""
    counts = {"mask": 0, "filter": 0, "clip": 0, "blend": 0, "opacity": 0, "pictures": 0}
    root = ET.fromstring(svg)
    stack = [(child, True) for child in root]
    while stack:
        element, reachable = stack.pop()
        whole = reachable and full_window(element)
        if whole:
            for kind in layer_kinds(element):
                counts[kind] += 1
            if element.tag == SVG + "svg":
                counts["pictures"] += 1
        stack.extend((child, whole) for child in element)
    return counts


def check_graphics(copy: Path) -> Result:
    rows = []
    for scene in sorted(copy.glob("plugins/*/hooks/scene-*.js")):
        if scene.parent.parent.name == "backdrops":
            continue  # the picker's copies are the single plugins' scenes
        counts = graphics_cost(scene_text(scene))
        offscreen = counts["filter"] + counts["clip"] + counts["blend"] + counts["opacity"]
        rows.append((counts["mask"], offscreen, counts["pictures"], scene.stem[len("scene-"):]))
    rows.sort(reverse=True)
    line = ", ".join(f"{name} {masked}" for masked, _, _, name in rows if masked)
    table = "\n".join(f"{name:<18} {masked:>3} masked  {offscreen:>3} other off-screen  {pictures:>3} nested pictures"
                      for masked, offscreen, pictures, name in rows)
    return Result("graphics", "note", f"full-window masked layers: {line or 'none'}", table)


# ------------------------------------------------------------------------------- paint (--paint)

DRAW_WARN_MS = 100          # Chrome's raster time over 6 s at 3840 x 1620; the light themes take 8 to 30
# the least contrast behind the chat column in each layout: the usual one (sidebar collapsed, info panel closed),
# then with the sidebar open, with the info panel open, and with both open
OPEN = {"primary": 4.5, "secondary": 3.0, "muted": 3.0}
CONTRAST_MIN = {"closed": {"primary": 7.0, "secondary": 4.5, "muted": 4.5}, "sidebar": OPEN, "panel": OPEN, "both": OPEN}


def measure(copy: Path, python: str, what: str) -> tuple[list[dict], str]:
    """Runs tools/measure.py on the copy; returns its results, or why it could not run."""
    status, output = run([python, "-E", "-B", "tools/measure.py", what], cwd=copy, timeout=1800)
    results = []
    for line in output.splitlines():
        if line.startswith("{"):
            results.append(json.loads(line))
    errors = [r["error"] for r in results if "error" in r]
    if errors or status != 0 or not results:
        return [], errors[0] if errors else tail(output, 10)
    return results, ""


def check_draw(copy: Path) -> Result:
    results, problem = measure(copy, sys.executable, "draw")
    if problem:
        return not_run("draw", problem)
    missing = [r["scene"] for r in results if r["ms"] is None]
    if missing:
        return fail("draw", f"no trace for {', '.join(missing)}")
    results.sort(key=lambda r: -r["ms"])
    heavy = [f"{r['scene']} {r['ms']} ms" for r in results if r["ms"] > DRAW_WARN_MS]
    table = "\n".join(f"{r['scene']:<18} {r['ms']:>5} ms" for r in results)
    if heavy:
        return Result("draw", "note", f"over {DRAW_WARN_MS} ms of raster in 6 s at 3840x1620: {', '.join(heavy)}", table)
    return ok("draw", f"every scene under {DRAW_WARN_MS} ms of raster in 6 s at 3840x1620 "
                      f"(heaviest {results[0]['scene']} {results[0]['ms']} ms)", table)


def check_contrast(copy: Path) -> list[Result]:
    """One result per layout, each against that layout's targets."""
    python = find_numpy_python("numpy, PIL")
    if python is None:
        return [not_run("contrast", "needs a python with numpy and Pillow: pip install numpy pillow, "
                                    "or set BACKDROPS_PYTHON")]
    results, problem = measure(copy, python, "contrast")
    if problem:
        return [not_run("contrast", problem)]
    found = []
    for layout, target in CONTRAST_MIN.items():
        mine = [r for r in results if r["layout"] == layout]
        if not mine:
            found.append(fail("contrast", f"{layout}: not measured"))
            continue
        aim = f"{target['primary']:g} / {target['secondary']:g}"
        misses, rows = [], []
        for result in mine:
            worst = {role: min(sizes[role] for sizes in result["ratios"].values()) for role in target}
            rows.append(f"{result['scene']:<18} " + "  ".join(f"{role} {worst[role]:.2f}" for role in target)
                        + ("  (glass modelled)" if result["glass"] else ""))
            low = [f"{role} {worst[role]:.2f}" for role in target if worst[role] < target[role]]
            if low:
                misses.append(f"{result['scene']} ({', '.join(low)})")
        if misses:
            found.append(fail("contrast", f"{layout}: below {aim} behind the chat column: {', '.join(misses)}",
                              "\n".join(rows)))
        else:
            found.append(ok("contrast", f"{layout}: {len(mine)} scenes at {aim} in {len(mine[0]['ratios'])} sizes "
                                        f"and zooms", "\n".join(rows)))
    return found


# ----------------------------------------------------------------------------------- app versions

def installed_versions() -> dict[str, str] | None:
    info = APP / "Contents" / "Info.plist"
    if not info.is_file():
        return None
    with info.open("rb") as handle:
        desktop = plistlib.load(handle).get("CFBundleShortVersionString", "unknown")
    engines = sorted((p.name for p in ENGINES.iterdir() if re.fullmatch(r"[\d.]+", p.name)), key=version_key) \
        if ENGINES.is_dir() else []
    chromium = "unknown"
    framework = APP / "Contents" / "Frameworks" / "Electron Framework.framework" / "Electron Framework"
    if framework.is_file():
        with framework.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
            match = re.search(rb"Chrome/(\d+\.\d+\.\d+\.\d+)", data)
            chromium = match.group(1).decode() if match else "unknown"
    return {"desktop": desktop, "engine": engines[-1] if engines else "unknown", "chromium": chromium}


def check_versions() -> Result | None:
    """Says nothing new while the app is the one the themes were proven on; says what to re-run when it isn't."""
    installed = installed_versions()
    if installed is None:
        return None
    proven = json.loads(VERSIONS_FILE.read_text())
    if installed == proven:
        return ok("app", "desktop {desktop}, engine {engine}, Chromium {chromium}: the versions the themes "
                         "were proven on".format(**proven))
    changes = ", ".join(f"{key} {proven.get(key)} -> {value}" for key, value in installed.items()
                        if proven.get(key) != value)
    return Result("app", "note", f"not the app the themes were proven on ({changes}). Re-run "
                                 "CONTRIBUTING.md 'When the app updates', then "
                                 "python3 tools/check.py --record-versions")


def record_versions() -> int:
    installed = installed_versions()
    if installed is None or "unknown" in installed.values():
        print(f"can't read the installed app's versions: {installed}")
        return 1
    VERSIONS_FILE.write_text(json.dumps(installed, indent=2) + "\n")
    print(f"{VERSIONS_FILE.relative_to(ROOT)}: " + ", ".join(f"{k} {v}" for k, v in installed.items()))
    return 0


# -------------------------------------------------------------------------------------------- main

def show(result: Result, verbose: bool) -> None:
    print(f"{result.status:<8}{result.name:<10}{result.summary}", flush=True)
    if result.details and (result.blocks or verbose):
        print("\n".join("          " + line for line in result.details.splitlines()), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--fast", action="store_true", help="plugins, privacy, sizes and tests only")
    parser.add_argument("--staged", action="store_true", help="check what is staged, not the working tree")
    parser.add_argument("--verbose", "-v", action="store_true", help="details for passing checks too")
    parser.add_argument("--paint", action="store_true", help="also measure paint cost and text contrast in Chrome")
    parser.add_argument("--record-versions", action="store_true",
                        help="save the installed app's versions as the ones the themes are proven on")
    options = parser.parse_args()
    if options.record_versions:
        return record_versions()

    copy = make_copy(options.staged)
    try:
        claude = find_claude()
        checks = [("plugins", lambda: check_plugins(copy)), ("privacy", lambda: check_privacy(copy)),
                  ("sizes", lambda: check_sizes(copy)), ("tests", lambda: check_tests(copy, claude))]
        if not options.fast:
            checks += [("validate", lambda: check_validate(copy, claude)), ("types", lambda: check_types(copy)),
                       ("rebuild", lambda: check_rebuild(copy)), ("graphics", lambda: check_graphics(copy)),
                       ("app", check_versions)]
        if options.paint:
            checks += [("draw", lambda: check_draw(copy)), ("contrast", lambda: check_contrast(copy))]
        blocked = False
        for name, check in checks:
            try:
                result = check()
            except Exception as error:  # a check that crashes is a failure, never a pass
                result = fail(name, f"crashed: {error!r}")
            if result is None:
                continue
            for each in result if isinstance(result, list) else [result]:   # contrast reports per layout
                show(each, options.verbose)
                blocked |= each.blocks
        return 1 if blocked else 0
    finally:
        shutil.rmtree(copy, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
