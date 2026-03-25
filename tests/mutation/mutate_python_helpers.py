#!/usr/bin/env python3
"""Lightweight mutation harness for the Python helper modules."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MUTATIONS = (
    (
        "scripts/lib/bash_guard.py",
        "if has_download_exec(candidate):",
        "if False:",
    ),
    (
        "scripts/lib/bash_guard.py",
        "if pushes_default_branch(candidate, project_dir):",
        "if False:",
    ),
    (
        "scripts/lib/claude_config_tooling.py",
        'Asset("commands/merge-dependabot.md", ".claude/commands/merge-dependabot.md", "commands"),',
        "",
    ),
)


def main() -> int:
    """Run mutations and ensure tests catch them."""
    for relative_path, original, replacement in MUTATIONS:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shutil.copytree(REPO_ROOT, temp_root / "repo", dirs_exist_ok=True)
            target = temp_root / "repo" / relative_path
            text = target.read_text(encoding="utf-8")
            if original not in text:
                raise RuntimeError(f"Mutation target not found in {relative_path}")
            target.write_text(text.replace(original, replacement, 1), encoding="utf-8")
            result = subprocess.run(
                ["python3", "-m", "unittest", "discover", "-s", "tests/python", "-p", "test_*.py"],
                cwd=temp_root / "repo",
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                raise RuntimeError(
                    f"Mutation survived for {relative_path}.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                )
    print("Mutation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
