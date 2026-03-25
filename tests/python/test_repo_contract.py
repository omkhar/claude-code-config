"""Contract tests for repo consistency and examples."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class RepoContractTests(unittest.TestCase):
    def test_readme_references_validate_and_install(self) -> None:
        readme = Path(REPO_ROOT, "README.md").read_text(encoding="utf-8")
        self.assertIn("./scripts/install.sh", readme)
        self.assertIn("./scripts/doctor.sh", readme)
        self.assertIn("./scripts/validate-repo.sh", readme)

    def test_config_command_installs_all_shipped_commands(self) -> None:
        command = Path(REPO_ROOT, ".claude/commands/trailofbits/config.md").read_text(encoding="utf-8")
        self.assertIn("merge-dependabot.md", command)
        self.assertNotIn("Granola", command)
        self.assertIn("./scripts/install.sh", command)
        self.assertNotIn("raw.githubusercontent.com", command)
        self.assertNotIn("WebFetch", command)

    def test_mcp_template_uses_pinned_packages_and_env_expansion(self) -> None:
        payload = json.loads(Path(REPO_ROOT, "mcp-template.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["mcpServers"]["context7"]["command"], "context7-mcp")
        self.assertEqual(payload["mcpServers"]["exa"]["command"], "exa-mcp-server")
        self.assertEqual(payload["mcpServers"]["exa"]["env"]["EXA_API_KEY"], "${EXA_API_KEY:-}")

    def test_settings_uses_external_hook_script(self) -> None:
        payload = json.loads(Path(REPO_ROOT, "settings.json").read_text(encoding="utf-8"))
        hook_command = payload["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertIn("pre-bash-guard.py", hook_command)
        self.assertNotIn("grep -qiE", hook_command)
        self.assertIn("Read(~/.mcp.json)", payload["permissions"]["deny"])
        self.assertIn("Read(./.mcp.json)", payload["permissions"]["deny"])

    def test_review_pr_does_not_force_yolo_for_gemini(self) -> None:
        command = Path(REPO_ROOT, "commands/review-pr.md").read_text(encoding="utf-8")
        self.assertNotIn("--yolo", command)
        self.assertIn("./scripts/validate-repo.sh", command)

    def test_merge_dependabot_requires_opt_in_for_admin_merge(self) -> None:
        command = Path(REPO_ROOT, "commands/merge-dependabot.md").read_text(encoding="utf-8")
        self.assertIn("ALLOW_ADMIN_MERGE=1", command)
        self.assertIn("gh pr merge --repo $REPO --squash {number}", command)

    def test_validate_repo_passes_shellcheck_targets(self) -> None:
        process = subprocess.run(
            ["shellcheck", "scripts/install.sh", "scripts/doctor.sh", "scripts/validate-repo.sh"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_statusline_strips_control_sequences_from_display_fields(self) -> None:
        payload = json.dumps(
            {
                "workspace": {"current_dir": str(REPO_ROOT)},
                "model": {"display_name": "Opus\x1b[31m"},
                "cost": {"total_cost_usd": 1, "total_duration_ms": 1000},
                "context_window": {"remaining_percentage": 90, "current_usage": {}},
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir, "repo")
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True, capture_output=True)
            process = subprocess.run(
                ["bash", str(Path(REPO_ROOT, "scripts/statusline.sh"))],
                input=payload.replace(str(REPO_ROOT), str(repo)),
                text=True,
                capture_output=True,
                check=True,
            )
        self.assertNotIn("\x1b[31m", process.stdout)


if __name__ == "__main__":
    unittest.main()
