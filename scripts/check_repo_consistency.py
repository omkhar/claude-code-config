#!/usr/bin/env python3
"""Repo-specific drift checks for docs, manifests, and command inventory."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "policy" / "install-manifest.json"
CONFIG_COMMAND_PATH = REPO_ROOT / ".claude" / "commands" / "trailofbits" / "config.md"
README_PATH = REPO_ROOT / "README.md"
MCP_TEMPLATE_PATH = REPO_ROOT / "mcp-template.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def component_labels(manifest: dict) -> set[str]:
    return {component["label"] for component in manifest["components"]}


def config_labels() -> set[str]:
    text = CONFIG_COMMAND_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"- \*\*(.+?)\*\* —", text))


def command_inventory() -> set[str]:
    return {path.name for path in (REPO_ROOT / "commands").glob("*.md")}


def manifest_command_inventory(manifest: dict) -> set[str]:
    command_sources = set()
    for component in manifest["components"]:
        for source in component["sources"]:
            source_path = Path(source)
            if source_path.parent.name == "commands":
                command_sources.add(source_path.name)
    return command_sources


def main() -> int:
    manifest = load_manifest()
    failures: list[str] = []

    for component in manifest["components"]:
        for source in component["sources"]:
            source_path = REPO_ROOT / source
            if not source_path.exists():
                failures.append(f"manifest references missing source: {source}")

    labels = component_labels(manifest)
    config_components = config_labels()
    if labels != config_components:
        failures.append(
            "config command component list drifted from policy/install-manifest.json: "
            f"manifest={sorted(labels)} config={sorted(config_components)}"
        )

    if manifest_command_inventory(manifest) != command_inventory():
        failures.append(
            "install manifest command list drifted from commands/: "
            f"manifest={sorted(manifest_command_inventory(manifest))} repo={sorted(command_inventory())}"
        )

    readme = README_PATH.read_text(encoding="utf-8")
    if "Granola" in CONFIG_COMMAND_PATH.read_text(encoding="utf-8") or "Granola" in readme:
        failures.append("stale Granola reference detected; the repo no longer ships a Granola MCP entry")

    mcp_template = json.loads(MCP_TEMPLATE_PATH.read_text(encoding="utf-8"))
    shipped_servers = set(mcp_template.get("mcpServers", {}))
    if shipped_servers != {"context7", "exa"}:
        failures.append(f"unexpected MCP template server set: {sorted(shipped_servers)}")

    if "merge-dependabot command" not in readme:
        failures.append("README does not mention the merge-dependabot command")

    if "raw.githubusercontent.com" in CONFIG_COMMAND_PATH.read_text(encoding="utf-8"):
        failures.append("config command must not fetch raw files from GitHub")
    if "WebFetch" in CONFIG_COMMAND_PATH.read_text(encoding="utf-8"):
        failures.append("config command must use the local checkout, not WebFetch")
    if "./scripts/install.sh" not in readme or "./scripts/doctor.sh" not in readme or "./scripts/validate-repo.sh" not in readme:
        failures.append("README must document the install/doctor/validate workflow")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print("Repo consistency checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
