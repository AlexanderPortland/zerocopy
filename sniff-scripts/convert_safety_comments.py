#!/usr/bin/env python3
"""
Convert Rust safety comments into doc comments across a repository.

Transforms blocks like:
    // SAFETY: reason
    // more details
into (only adding an extra slash, preserving content):
    /// SAFETY: reason
    /// more details

Notes:
- Only converts line comments starting with `// SAFETY:` followed by contiguous `//` lines.
- Preserves indentation. Skips lines that are already doc comments (`///` or `//!`).
- Converts anywhere in the file, including before `unsafe` blocks.
"""

import argparse
import os
import re
from pathlib import Path
from typing import Tuple

SAFETY_START_RE = re.compile(r"^(?P<indent>\s*)//(?!/|!)\s*SAFETY:.*$")
FOLLOWING_COMMENT_RE = re.compile(r"^(?P<indent>\s*)//(?!/|!)(?P<rest>.*)$")  # '//' but not doc comments (/// or //!)


def transform_content(text: str) -> Tuple[str, bool]:
    lines = text.splitlines()
    out = []
    i = 0
    changed = False

    while i < len(lines):
        line = lines[i]
        m = SAFETY_START_RE.match(line)
        if not m:
            out.append(line)
            i += 1
            continue

        # Convert the SAFETY line by adding one extra slash, preserving content
        indent = m.group("indent")
        out.append(indent + "///" + line[len(indent) + 2:])

        # Convert contiguous following '//' lines that are not already doc comments (/// or //!)
        j = i + 1
        while j < len(lines):
            next_line = lines[j]
            m2 = FOLLOWING_COMMENT_RE.match(next_line)
            if not m2:
                break
            indent2 = m2.group("indent")
            out.append(indent2 + "///" + next_line[len(indent2) + 2:])
            j += 1

        changed = True
        i = j

    # Preserve trailing newline if present in original
    result = "\n".join(out)
    if text.endswith("\n"):
        result += "\n"

    return result, changed


def should_skip_dir(path: Path) -> bool:
    skip_names = {".git", "target", ".cargo", ".hg", ".svn", ".idea", ".vscode", "node_modules"}
    return path.name in skip_names


def process_repo(root: Path, dry_run: bool, verbose: bool) -> int:
    changed_files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune directories in-place
        dirnames[:] = [d for d in dirnames if not should_skip_dir(Path(dirpath) / d)]

        for fname in filenames:
            if not fname.endswith(".rs"):
                continue
            fpath = Path(dirpath) / fname
            try:
                src = fpath.read_text(encoding="utf-8")
            except Exception as e:
                if verbose:
                    print(f"[skip] {fpath}: {e}")
                continue

            new_src, changed = transform_content(src)
            if changed:
                changed_files += 1
                if verbose or dry_run:
                    print(f"[update]{' (dry-run)' if dry_run else ''} {fpath}")
                if not dry_run:
                    fpath.write_text(new_src, encoding="utf-8")

    return changed_files


def main():
    ap = argparse.ArgumentParser(description="Replace Rust // SAFETY: comment blocks with doc comments")
    ap.add_argument("root", nargs="?", default=str(Path.cwd()), help="Root directory to process (default: CWD)")
    ap.add_argument("--dry-run", action="store_true", help="Scan and report files that would change without writing")
    ap.add_argument("--verbose", "-v", action="store_true", help="Print files as they are processed")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    changed = process_repo(root, dry_run=args.dry_run, verbose=args.verbose)

    if args.dry_run:
        print(f"Would update {changed} file(s)")
    else:
        print(f"Updated {changed} file(s)")


if __name__ == "__main__":
    main()
