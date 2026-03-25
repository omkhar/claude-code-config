# Trail of Bits Claude Code Config

Opinionated Claude Code defaults, hooks, commands, and operating guidance for security-conscious engineering teams.

This repo is Claude-first. It also includes workflows that are useful when you pair Claude with Codex or Gemini for second-opinion reviews, but the installed config surface is intentionally centered on Claude Code.

## Quick start

```bash
git clone https://github.com/trailofbits/claude-code-config.git
cd claude-code-config
./scripts/install.sh --component settings --component statusline --component hooks --component commands --component mcp
./scripts/doctor.sh
./scripts/validate-repo.sh
```

If you also want the shipped global `CLAUDE.md`, either install it explicitly:

```bash
./scripts/install.sh --component claude-md
```

or force an overwrite when you are updating an existing file:

```bash
./scripts/install.sh --component claude-md --force-claude-md
```

After the local checkout is in place, you can also run `/trailofbits:config` inside Claude Code. The command now uses the local repo checkout and the installer scripts above; it does not fetch raw config files from GitHub.

## Operating model

### Safe default on a host machine

Use standard Claude Code permissions on your host. Treat the shipped hooks and deny rules as guardrails, not a hard boundary.

This repo blocks obvious destructive or high-risk patterns such as:

- `rm -rf`
- `git clean -fd*`
- force-pushes
- direct pushes to `main` or `master`
- `curl|bash` and `wget|sh`
- obvious reads of secret-bearing host paths
- shell startup file edits
- package-manager mismatches in `pnpm` and `uv` projects

Those checks live in `~/.claude/hooks/pre-bash-guard.py` and `~/.claude/hooks/bash_guard.py` after install.

### Isolated autonomy

If you want no-prompt, high-throughput agent execution, do it inside a devcontainer, VM, or disposable remote machine. That is the right place for `--dangerously-skip-permissions`, not your primary host.

Recommended isolation options:

- [trailofbits/claude-code-devcontainer](https://github.com/trailofbits/claude-code-devcontainer)
- [trailofbits/dropkit](https://github.com/trailofbits/dropkit)
- Claude Code built-in `/sandbox` plus the deny rules from this repo

### Managed high-assurance mode

If you administer Claude Code for a team, start from [`policy/managed-settings.example.json`](policy/managed-settings.example.json). It disables bypass-permissions mode and keeps project MCP servers off by default.

## What gets installed

The installer manages these components:

- `settings.json`: telemetry/privacy defaults, deny rules, hook wiring, statusline config
- `CLAUDE.md`: global Claude guidance and coding standards
- `MCP servers`: pinned Context7 and Exa entries with env-based secrets
- `Statusline script`: a two-line status bar for model, branch, cost, and context
- `Hook helper scripts`: the tested Bash guard plus example helpers
- `review-pr command`: multi-agent PR review workflow
- `fix-issue command`: end-to-end issue fixing workflow
- `merge-dependabot command`: batched dependency review and merge workflow

List them at any time with:

```bash
./scripts/install.sh --list
```

## Developer workflow

The intended fast loop is:

```bash
./scripts/validate-repo.sh
```

That script is the local source of truth for this repo. It runs:

- `shellcheck`
- `shfmt`
- JSON validation
- Python syntax checks
- repo consistency checks
- unit and integration tests
- Python coverage with a `90%` floor for helper code
- mutation tests for the critical helper logic

CI runs the same repo validation entrypoint.

Use `./scripts/doctor.sh` when the installed state looks wrong, and `./scripts/install.sh` when you want to refresh managed files.

## Settings

[`settings.json`](settings.json) is designed around a small number of durable defaults:

- disable non-essential telemetry and feedback prompts
- keep project MCP servers opt-in
- wire `PreToolUse` to an external tested hook instead of inline regex snippets
- deny obvious reads of local credentials and wallet data
- deny edits to shell startup files
- point Claude Code at the shipped statusline script

The important design choice is externalized hook logic. Inline one-liner regex hooks drift quickly and are hard to test. This repo ships the Bash guard as Python so it can be unit-tested and mutation-tested.

### Hooks

Hooks are useful guardrails and workflow nudges. They are not a security boundary by themselves.

Shipped hooks:

- [`hooks/pre-bash-guard.py`](hooks/pre-bash-guard.py): canonical blocking hook used by `settings.json`
- [`scripts/lib/bash_guard.py`](scripts/lib/bash_guard.py): tested guard logic
- [`hooks/enforce-package-manager.sh`](hooks/enforce-package-manager.sh): optional example for package-manager policy
- [`hooks/log-gam.sh`](hooks/log-gam.sh): optional mutation audit example with redacted previews

## MCP servers

[`mcp-template.json`](mcp-template.json) is pinned and env-based:

- `@upstash/context7-mcp@2.1.4`
- `exa-mcp-server@3.1.9`
- Exa auth comes from `EXA_API_KEY`, not an inline secret in `~/.mcp.json`

Install or merge the template with:

```bash
./scripts/install.sh --component mcp
```

Then export your Exa key in your shell or secret manager before launching Claude Code:

```bash
export EXA_API_KEY=...
```

## Commands

This repo ships three reusable Claude commands:

- [`commands/review-pr.md`](commands/review-pr.md)
- [`commands/fix-issue.md`](commands/fix-issue.md)
- [`commands/merge-dependabot.md`](commands/merge-dependabot.md)

The commands prefer the repo-local `./scripts/validate-repo.sh` fast path when it exists. They also avoid assuming risky autonomy defaults for external reviewers.

## Portability

This repo is not pretending that Claude, Codex, and Gemini are interchangeable. The current support split is:

| Tool | Role here | Notes |
|------|-----------|-------|
| Claude Code | Primary target | Installed config, hooks, commands, and docs are built for Claude |
| Codex CLI | Secondary reviewer | Supported as an optional PR second opinion if installed |
| Gemini CLI | Secondary reviewer | Supported as an optional PR second opinion if installed |

If you use Codex or Gemini as your primary coding agent, take the design ideas here, but do not assume the Claude-specific settings files install cleanly into those tools.

## Updating

1. Pull the repo.
2. Re-run `./scripts/install.sh` for the components you manage.
3. Run `./scripts/doctor.sh`.
4. Run `./scripts/validate-repo.sh` before committing local changes.

## References

- [Claude Code best practices](https://code.claude.com/docs/en/best-practices)
- [Claude Code hooks guide](https://code.claude.com/docs/en/hooks-guide)
- [Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing)
- [Anthropic sandboxing engineering post](https://www.anthropic.com/engineering/claude-code-sandboxing)
- [Trail of Bits skills](https://github.com/trailofbits/skills)
- [Trail of Bits claude-code-devcontainer](https://github.com/trailofbits/claude-code-devcontainer)
- [Trail of Bits dropkit](https://github.com/trailofbits/dropkit)
