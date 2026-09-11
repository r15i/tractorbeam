#!/usr/bin/env python3
"""Live preview of the report: rebuild on save, refresh in the viewer.

    just watch                  # or: python tools/watch_paper.py

Opens paper/Final_Report.pdf in a PDF viewer that reloads the file by itself
(zathura and okular both do), then watches the sources and rebuilds whenever one
of them changes. Save a file, look at the window, the new page is there.

What it watches, and what each change costs:

    tools/*.py                  regenerates the .tex and the .docx, then compiles
    paper/Final_Report.tex      compiles only (for hand-edits to the LaTeX)

Figures are NOT regenerated. `just report` depends on `just figures`, which
re-renders every plot from the CSVs and takes far too long to sit in a save
loop. Run `just figures` yourself after changing the experiment data or
tools/make_figures.py; everything already in paper/figures/ is reused as-is.

Unlike the two scripts this replaces, a failed build is reported rather than
discarded — pdflatex's output goes to the terminal on error instead of
/dev/null, so a report that silently stopped updating cannot look like one that
had nothing to update.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
TEX = PROJECT_DIR / "paper" / "Final_Report.tex"
PDF = PROJECT_DIR / "paper" / "Final_Report.pdf"
TOOLS = PROJECT_DIR / "tools"

# Viewers that notice the file changed underneath them and redraw. Ordered by
# how well they behave when the PDF is replaced mid-compile.
RELOADING_VIEWERS = ["zathura", "okular"]

POLL_S = 0.5
DEBOUNCE_S = 0.4          # let an editor finish writing before building


def watched_files() -> dict[Path, float]:
    """Current mtimes of everything that should trigger a rebuild."""
    files = {}
    for path in sorted(TOOLS.glob("*.py")):
        if path.name == Path(__file__).name:
            continue          # editing the watcher shouldn't rebuild the report
        try:
            files[path] = path.stat().st_mtime
        except FileNotFoundError:
            pass
    if TEX.exists():
        files[TEX] = TEX.stat().st_mtime
    return files


def run(cmd: list[str], label: str) -> bool:
    """Run a build step, surfacing its output only when it fails."""
    proc = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"  {label} FAILED (exit {proc.returncode})")
        tail = (proc.stdout + proc.stderr).strip().splitlines()
        for line in tail[-25:]:
            print(f"    {line}")
        return False
    return True


def compile_pdf() -> bool:
    # pdflatex exits non-zero on a hard error; -interaction=nonstopmode keeps it
    # from stopping to ask, so this returns rather than hanging the watcher.
    return run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
         f"-output-directory={PDF.parent}", str(TEX)],
        "pdflatex",
    )


def regenerate() -> bool:
    env_cmd = ["uv", "run", "python", "tools/generate_report.py"]
    proc = subprocess.run(env_cmd, cwd=PROJECT_DIR, capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": "src"})
    if proc.returncode != 0:
        print(f"  generate_report.py FAILED (exit {proc.returncode})")
        for line in (proc.stdout + proc.stderr).strip().splitlines()[-25:]:
            print(f"    {line}")
        return False
    # generate_report.py compiles the PDF itself; if it did not, do it here.
    return True


def open_viewer(viewer: str | None) -> subprocess.Popen | None:
    if viewer == "none":
        return None
    if viewer is None:
        viewer = next((v for v in RELOADING_VIEWERS if shutil.which(v)), None)
    if viewer is None:
        print("No self-reloading viewer found (zathura, okular). Opening with "
              "xdg-open; you may have to refresh it by hand.")
        subprocess.Popen(["xdg-open", str(PDF)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return None
    print(f"Viewer: {viewer} (reloads on its own)")
    return subprocess.Popen([viewer, str(PDF)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--viewer", default=None,
                        help="viewer to open (default: first of zathura, okular; "
                             "'none' to watch without opening one)")
    parser.add_argument("--no-build", action="store_true",
                        help="do not build once at startup")
    args = parser.parse_args()

    if not TEX.exists() and not args.no_build:
        print(f"{TEX} does not exist yet — building it first.")
        if not regenerate():
            return 1

    if not args.no_build:
        print("Initial build...")
        regenerate()

    if not PDF.exists():
        print(f"ERROR: {PDF} was not produced; nothing to preview.", file=sys.stderr)
        return 1

    viewer = open_viewer(args.viewer)

    state = watched_files()
    print(f"Watching {len(state)} files under tools/ and paper/. Ctrl-C to stop.\n")

    try:
        while True:
            time.sleep(POLL_S)

            if viewer is not None and viewer.poll() is not None:
                print("Viewer closed; stopping.")
                return 0

            current = watched_files()
            changed = [p for p, m in current.items()
                       if p not in state or state[p] != m]
            removed = [p for p in state if p not in current]
            if not changed and not removed:
                continue

            time.sleep(DEBOUNCE_S)
            current = watched_files()

            names = ", ".join(p.name for p in changed) or "files removed"
            print(f"[{time.strftime('%H:%M:%S')}] {names}")

            # A .tex-only edit needs nothing but a compile; anything in tools/
            # means the .tex has to be regenerated first.
            tex_only = changed == [TEX]
            ok = compile_pdf() if tex_only else regenerate()
            print("  rebuilt" if ok else "  build failed — previous PDF left in place")

            state = watched_files()
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
