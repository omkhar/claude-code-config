#!/usr/bin/env python3
"""Guard helper for Bash PreToolUse hooks."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Iterable

DEFAULT_BRANCHES = {"main", "master"}
SHELL_WRAPPERS = {"bash", "sh", "zsh"}
SECRET_PATH_MARKERS = (
    "~/.ssh/",
    "~/.aws/",
    "~/.config/gh/",
    "~/.gnupg/",
    "~/.mcp.json",
    "~/.netrc",
    "~/.config/gcloud/",
    "~/.zshrc",
    "~/.bashrc",
)


def load_command(stdin_text: str) -> str:
    """Extract the Bash command from hook JSON."""
    payload = json.loads(stdin_text or "{}")
    command = payload.get("tool_input", {}).get("command", "")
    return command if isinstance(command, str) else ""


def strip_env_prefix(tokens: list[str]) -> list[str]:
    """Drop a leading env wrapper and inline env assignments."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "env":
            index += 1
            continue
        if "=" in token and not token.startswith("-") and token.split("=", 1)[0]:
            index += 1
            continue
        break
    return tokens[index:]


def unwrap_shell_command(command: str) -> list[str]:
    """Return nested shell payloads wrapped in bash -c / sh -c forms."""
    nested: list[str] = []
    queue = [command]
    seen: set[str] = set()
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        nested.append(current)
        try:
            tokens = shlex.split(current, posix=True)
        except ValueError:
            continue
        tokens = strip_env_prefix(tokens)
        if len(tokens) >= 3 and os.path.basename(tokens[0]) in SHELL_WRAPPERS:
            for index, token in enumerate(tokens[1:], start=1):
                if token in {"-c", "-lc", "-ic"} and index + 1 < len(tokens):
                    queue.append(tokens[index + 1])
                    break
    return nested


def contains_all_flags(command: str, long_flag: str, short_flag: str) -> bool:
    """Check for either a long flag or a short-option bundle member."""
    if re.search(rf"(^|\s){re.escape(long_flag)}($|\s)", command):
        return True
    return re.search(rf"(^|\s)-[A-Za-z]*{re.escape(short_flag)}[A-Za-z]*($|\s)", command) is not None


def has_rm_rf(command: str) -> bool:
    """Detect rm with both recursive and force semantics."""
    return re.search(r"\brm\b", command) is not None and contains_all_flags(
        command,
        "--recursive",
        "r",
    ) and contains_all_flags(command, "--force", "f")


def has_git_clean(command: str) -> bool:
    """Detect destructive git clean invocations."""
    if re.search(r"\bgit\s+clean\b", command) is None:
        return False
    has_force = re.search(r"(^|\s)-[A-Za-z]*f[A-Za-z]*($|\s)", command) is not None
    has_dir = re.search(r"(^|\s)-[A-Za-z]*d[A-Za-z]*($|\s)", command) is not None
    return has_force and has_dir


def has_force_push(command: str) -> bool:
    """Detect any git push force variant."""
    if re.search(r"\bgit\s+push\b", command) is None:
        return False
    return re.search(r"(^|\s)(--force|--force-with-lease|-f)($|\s)", command) is not None


def current_branch(project_dir: str | None) -> str | None:
    """Return the current branch name for the active project."""
    if not project_dir:
        return None
    try:
        output = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    branch = output.stdout.strip()
    return branch or None


def pushes_default_branch(command: str, project_dir: str | None) -> bool:
    """Detect direct pushes to main/master, even when implicit."""
    if re.search(r"\bgit\s+push\b", command) is None:
        return False
    if re.search(r"(^|[\s:])(main|master)($|\s)", command) is not None:
        return True
    branch = current_branch(project_dir)
    if branch in DEFAULT_BRANCHES and ":" not in command:
        return True
    return False


def has_download_exec(command: str) -> bool:
    """Detect common curl/wget download-and-exec shapes."""
    patterns = (
        r"curl[^|>]*\|\s*(bash|sh)\b",
        r"wget[^|>]*\|\s*(bash|sh)\b",
        r"(bash|sh)\s+-c\s+['\"][^'\"]*(curl|wget)",
        r"source\s+<\([^)]*(curl|wget)",
        r"<\([^)]*(curl|wget)[^)]*\)",
    )
    return any(re.search(pattern, command) is not None for pattern in patterns)


def reads_secret_paths(command: str) -> bool:
    """Detect obvious reads of sensitive host paths."""
    if not any(marker in command for marker in SECRET_PATH_MARKERS):
        return False
    readers = ("cat ", "tar ", "rsync ", "scp ", "python", "ruby ", "perl ", "node ")
    return any(reader in command for reader in readers)


def writes_shell_config(command: str) -> bool:
    """Detect shell-profile writes or appends."""
    return re.search(r"(>>|>|tee\s+-a|tee\s+)\s*~/(?:\.zshrc|\.bashrc)", command) is not None


def package_manager_violation(command: str, project_dir: str | None) -> str | None:
    """Enforce project package-manager conventions."""
    if not project_dir:
        return None
    if os.path.exists(os.path.join(project_dir, "pnpm-lock.yaml")) and re.search(
        r"(^|\s)(npm|npx)($|\s)",
        command,
    ):
        return "Use pnpm instead of npm/npx in pnpm-managed projects."
    if os.path.exists(os.path.join(project_dir, "uv.lock")) and (
        re.search(r"(^|\s)(pip|pip3)($|\s)", command)
        or re.search(r"python[0-9.]*\s+-m\s+pip($|\s)", command)
    ):
        return "Use uv instead of pip in uv-managed projects."
    return None


def iter_reasons(command: str, project_dir: str | None) -> Iterable[str]:
    """Yield blocking reasons for a Bash command."""
    package_reason = package_manager_violation(command, project_dir)
    if package_reason:
        yield package_reason

    for candidate in unwrap_shell_command(command):
        if has_rm_rf(candidate):
            yield "Use trash or an explicit file list instead of rm -rf."
        if has_git_clean(candidate):
            yield "Do not use git clean -fd* in autonomous sessions."
        if has_force_push(candidate):
            yield "Do not force push from autonomous sessions."
        if pushes_default_branch(candidate, project_dir):
            yield "Use feature branches and PRs instead of pushing directly to main/master."
        if has_download_exec(candidate):
            yield "Do not use download-and-exec shell pipelines."
        if reads_secret_paths(candidate):
            yield "Do not read obvious secret-bearing host paths from Bash."
        if writes_shell_config(candidate):
            yield "Do not modify shell startup files from Bash."


def main() -> int:
    """CLI entrypoint for Claude Code hooks."""
    stdin_text = sys.stdin.read()
    command = load_command(stdin_text)
    if not command:
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    reasons = list(dict.fromkeys(iter_reasons(command, project_dir)))
    if not reasons:
        return 0

    for reason in reasons:
        print(f"BLOCKED: {reason}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
