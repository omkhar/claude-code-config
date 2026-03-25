#!/usr/bin/env python3
"""Thin wrapper for the installed Bash guard helper."""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
repo_helper_dir = HOOK_DIR.parent / "scripts" / "lib"
if repo_helper_dir.exists():
    sys.path.insert(0, str(repo_helper_dir))

from bash_guard import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
