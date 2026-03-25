#!/usr/bin/env python3
"""Installer and doctor helpers for the Claude config repo."""

from __future__ import annotations

import argparse
import json
import stat
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Asset:
    """A managed asset in the repo."""

    source: str
    target: str
    component: str
    mode: str = "copy"
    executable: bool = False
    optional: bool = False


ASSETS: tuple[Asset, ...] = (
    Asset("settings.json", ".claude/settings.json", "settings", mode="json-merge"),
    Asset("claude-md-template.md", ".claude/CLAUDE.md", "claude-md", mode="copy", optional=True),
    Asset("mcp-template.json", ".mcp.json", "mcp", mode="mcp-merge"),
    Asset("scripts/statusline.sh", ".claude/statusline.sh", "statusline", executable=True),
    Asset("hooks/pre-bash-guard.py", ".claude/hooks/pre-bash-guard.py", "hooks", executable=True),
    Asset("scripts/lib/bash_guard.py", ".claude/hooks/bash_guard.py", "hooks"),
    Asset("hooks/enforce-package-manager.sh", ".claude/hooks/enforce-package-manager.sh", "hooks", executable=True),
    Asset("hooks/log-gam.sh", ".claude/hooks/log-gam.sh", "hooks", executable=True),
    Asset("commands/review-pr.md", ".claude/commands/review-pr.md", "commands"),
    Asset("commands/fix-issue.md", ".claude/commands/fix-issue.md", "commands"),
    Asset("commands/merge-dependabot.md", ".claude/commands/merge-dependabot.md", "commands"),
    Asset(
        ".claude/commands/trailofbits/config.md",
        ".claude/commands/trailofbits/config.md",
        "commands",
    ),
)


def repo_root_from(path: str | None) -> Path:
    """Resolve the repo root."""
    if path:
        return Path(path).resolve()
    return Path(__file__).resolve().parents[2]


def home_root_from(path: str | None) -> Path:
    """Resolve the install home."""
    return Path(path).expanduser().resolve() if path else Path.home()


def normalize_components(raw_components: Iterable[str] | None) -> set[str]:
    """Normalize --component arguments."""
    if not raw_components:
        return {asset.component for asset in ASSETS}
    normalized: set[str] = set()
    for raw in raw_components:
        for item in raw.split(","):
            item = item.strip()
            if item:
                normalized.add(item)
    return normalized


def load_json(path: Path) -> object:
    """Read JSON from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: object) -> None:
    """Write canonical JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def merge_json(existing: object, incoming: object) -> object:
    """Deep-merge dicts and union scalar lists while preserving user data."""
    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged = dict(existing)
        for key, value in incoming.items():
            if key in merged:
                merged[key] = merge_json(merged[key], value)
            else:
                merged[key] = value
        return merged

    if isinstance(existing, list) and isinstance(incoming, list):
        merged = list(existing)
        for item in incoming:
            if item not in merged:
                merged.append(item)
        return merged

    return incoming


def merge_mcp_json(existing: object, incoming: object) -> object:
    """Merge MCP server entries without overwriting user-defined config."""
    if not isinstance(existing, dict) or not isinstance(incoming, dict):
        return incoming

    merged = dict(existing)
    merged_servers = dict(existing.get("mcpServers", {}))
    for server_name, server_cfg in incoming.get("mcpServers", {}).items():
        merged_servers.setdefault(server_name, server_cfg)
    merged["mcpServers"] = merged_servers
    return merged


def install_asset(repo_root: Path, home_root: Path, asset: Asset, force_claude_md: bool) -> dict[str, str]:
    """Install a single asset."""
    source_path = repo_root / asset.source
    target_path = home_root / asset.target
    existed = target_path.exists()
    result = {
        "component": asset.component,
        "target": str(target_path),
        "action": "updated" if existed else "installed",
    }

    if asset.optional and asset.component == "claude-md" and target_path.exists() and not force_claude_md:
        result["action"] = "skipped-existing"
        return result

    target_path.parent.mkdir(parents=True, exist_ok=True)

    if asset.mode == "json-merge" and target_path.exists():
        dump_json(target_path, merge_json(load_json(target_path), load_json(source_path)))
    elif asset.mode == "json-merge":
        dump_json(target_path, load_json(source_path))
    elif asset.mode == "mcp-merge" and target_path.exists():
        dump_json(target_path, merge_mcp_json(load_json(target_path), load_json(source_path)))
    elif asset.mode == "mcp-merge":
        dump_json(target_path, load_json(source_path))
    else:
        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")

    if asset.executable:
        current_mode = stat.S_IMODE(target_path.stat().st_mode)
        target_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return result


def install_components(
    repo_root: Path,
    home_root: Path,
    components: set[str],
    force_claude_md: bool,
) -> list[dict[str, str]]:
    """Install selected components."""
    actions: list[dict[str, str]] = []
    for asset in ASSETS:
        if asset.component in components:
            actions.append(install_asset(repo_root, home_root, asset, force_claude_md))
    return actions


def resolve_hook_targets(settings: dict[str, object]) -> list[str]:
    """Extract referenced hook/statusline paths from settings."""
    paths: list[str] = []
    status_line = settings.get("statusLine", {})
    if isinstance(status_line, dict):
        command = status_line.get("command")
        if isinstance(command, str):
            paths.append(command)

    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return paths
    pre_tool = hooks.get("PreToolUse", [])
    if not isinstance(pre_tool, list):
        return paths
    for matcher in pre_tool:
        if not isinstance(matcher, dict):
            continue
        hook_list = matcher.get("hooks", [])
        if not isinstance(hook_list, list):
            continue
        for hook in hook_list:
            if not isinstance(hook, dict):
                continue
            command = hook.get("command")
            if isinstance(command, str):
                paths.append(command)
    return paths


def referenced_path_exists(command: str, home_root: Path) -> bool:
    """Check whether a referenced ~/.claude path exists."""
    token = command.split()[0]
    if token.startswith("python3") and len(command.split()) >= 2:
        token = command.split()[1]
    path = token.replace("~", str(home_root))
    return Path(path).expanduser().exists()


def doctor_report(repo_root: Path, home_root: Path) -> dict[str, object]:
    """Build a doctor report."""
    report: dict[str, object] = {"components": {}, "warnings": []}
    components = {asset.component for asset in ASSETS}
    for component in sorted(components):
        assets = [asset for asset in ASSETS if asset.component == component]
        missing = []
        for asset in assets:
            target = home_root / asset.target
            if not target.exists():
                missing.append(str(target))
        report["components"][component] = {"missing": missing, "ok": not missing}

    settings_path = home_root / ".claude/settings.json"
    if settings_path.exists():
        settings = load_json(settings_path)
        if isinstance(settings, dict):
            for command in resolve_hook_targets(settings):
                if "~/.claude/" in command and not referenced_path_exists(command, home_root):
                    report["warnings"].append(f"missing-hook-target:{command}")
        helper = home_root / ".claude/hooks/bash_guard.py"
        wrapper = home_root / ".claude/hooks/pre-bash-guard.py"
        if wrapper.exists() and not helper.exists():
            report["warnings"].append("missing-hook-helper:~/.claude/hooks/bash_guard.py")

    mcp_path = home_root / ".mcp.json"
    if mcp_path.exists():
        text = mcp_path.read_text(encoding="utf-8")
        if "your-exa-api-key-here" in text or '"${EXA_API_KEY:-}"' not in text:
            report["warnings"].append("mcp-placeholder-secret")
        if "@latest" in text:
            report["warnings"].append("floating-mcp-version")

    config_command_path = repo_root / ".claude/commands/trailofbits/config.md"
    if not config_command_path.exists():
        report["warnings"].append("missing-config-command-source")

    return report


def print_human_install(results: list[dict[str, str]]) -> None:
    """Print human-readable install results."""
    for result in results:
        print(f"{result['action']}: {result['component']} -> {result['target']}")


def print_human_doctor(report: dict[str, object]) -> None:
    """Print human-readable doctor output."""
    for component, state in sorted(report["components"].items()):
        status = "ok" if state["ok"] else "missing"
        print(f"{component}: {status}")
        for missing in state["missing"]:
            print(f"  missing: {missing}")
    for warning in report["warnings"]:
        print(f"warning: {warning}")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--repo-root")
    install_parser.add_argument("--home")
    install_parser.add_argument("--component", action="append")
    install_parser.add_argument("--force-claude-md", action="store_true")
    install_parser.add_argument("--json", action="store_true")

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--repo-root")
    doctor_parser.add_argument("--home")
    doctor_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from(getattr(args, "repo_root", None))
    home_root = home_root_from(getattr(args, "home", None))

    if args.command == "install":
        results = install_components(
            repo_root,
            home_root,
            normalize_components(args.component),
            args.force_claude_md,
        )
        if args.json:
            json.dump(results, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            print_human_install(results)
        return 0

    report = doctor_report(repo_root, home_root)
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print_human_doctor(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
