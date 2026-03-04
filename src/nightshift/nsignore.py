"""Reader for .nsignore files — determines which files to skip in listing and deploy."""

from __future__ import annotations

import os

# Patterns to exclude from the archive
DEFAULT_EXCLUDE_PATTERNS = {".git", "__pycache__", ".venv", ".env", "*.pyc", "node_modules", ".ruff_cache"}


def read_nsignore(directory: str) -> set[str]:
    """Read .nsignore from *directory* and return the combined set of patterns.

    Lines starting with '#' and empty lines are ignored.
    """
    patterns: set[str] = set(DEFAULT_EXCLUDE_PATTERNS)
    nsignore_path = os.path.join(directory, ".nsignore")
    if os.path.isfile(nsignore_path):
        with open(nsignore_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.add(line)
    return patterns


def should_exclude(name: str, patterns: set[str]) -> bool:
    """Return True if *name* matches any pattern in *patterns*.

    Supports:
    - Exact name matches (e.g. ``.git``, ``node_modules``)
    - Wildcard suffix patterns (e.g. ``*.pyc``, ``*.log``)
    """
    # Handle path components (e.g. "foo/__pycache__/bar.pyc")
    parts = name.replace("\\", "/").split("/")
    for part in parts:
        if part in patterns:
            return True
        for pattern in patterns:
            if pattern.startswith("*") and part.endswith(pattern[1:]):
                return True
    return False
