#!/usr/bin/env python3
"""Every line taken out of a decision document since HEAD must be in its mirror under docs/history/.

Usage: python3 docs/history/nothing_lost.py [<document> ...]   (no arguments: every mirrored document)

Exits 1 listing each removed line missing from the mirror, and also when a mirror itself lost a
line: the mirror only grows. Compares against HEAD, so a document with someone else's uncommitted
edits reads as a loss — check `git diff --quiet HEAD -- <document>` before starting to cut.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HISTORY = "docs/history/"
# The documents that hold decisions, and where each one's history goes. The mirror keeps the rest
# of the path, so one is computed from the other.
_ROOT_FILES = {"CLAUDE.md": HISTORY + "root/CLAUDE.md"}
_PREFIXES = {"plans/00-STATUS.md": HISTORY + "plans/00-STATUS.md", "docs/": HISTORY}
# Lines that carry no content of their own: blank, a rule, a table separator, a code fence.
_MARKUP = re.compile(r"^(\s*|[-|:\s]+|```[\w-]*)$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? ")


def mirror_of(relative: str) -> str | None:
    if relative.startswith(HISTORY):
        return None
    if relative in _ROOT_FILES:
        return _ROOT_FILES[relative]
    for source, target in _PREFIXES.items():
        if relative == source or (source.endswith("/") and relative.startswith(source)):
            return target if not source.endswith("/") else target + relative[len(source) :]
    return None


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout


def _removed(root: Path, relative: str) -> list[tuple[int, str]]:
    diff = _git(root, "diff", "--no-color", "--no-ext-diff", "-U0", "HEAD", "--", relative)
    removed: list[tuple[int, str]] = []
    old_line = 0
    for line in diff.splitlines():
        if hunk := _HUNK.match(line):
            old_line = int(hunk.group(1))
        elif line.startswith("-") and not line.startswith("---"):
            removed.append((old_line, line[1:]))
            old_line += 1
    return [(n, text) for n, text in removed if not _MARKUP.match(text)]


def check(root: Path, relative: str) -> list[str]:
    mirror = mirror_of(relative)
    if mirror is None:
        raise SystemExit(f"{relative}: not a document this check mirrors")
    mirror_path = root / mirror
    kept = (
        {line.strip() for line in mirror_path.read_text(encoding="utf-8").splitlines()}
        if mirror_path.exists()
        else set()
    )
    problems = [
        f"{relative}:{n}: not in {mirror}: {text.strip()}"
        for n, text in _removed(root, relative)
        if text.strip() not in kept
    ]
    problems += [
        f"{mirror}:{n}: the mirror lost a line: {text.strip()}" for n, text in _removed(root, mirror)
    ]
    return problems


def mirrored_documents(root: Path) -> list[str]:
    tracked = _git(root, "ls-files", "--cached", "--deleted", "*.md").split()
    return sorted({path for path in tracked if mirror_of(path) is not None})


def main(paths: list[str]) -> int:
    root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    relatives = [Path(p).resolve().relative_to(root).as_posix() for p in paths] or mirrored_documents(root)
    problems: list[str] = []
    for relative in relatives:
        problems += check(root, relative)
    for problem in problems:
        print(problem)
    print(f"{len(relatives)} document(s) checked, {len(problems)} line(s) lost")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
