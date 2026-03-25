You are installing or updating Trail of Bits' Claude Code configuration into the user's `~/.claude/` directory.

## Local-first rule

Do not fetch raw config files from GitHub and do not install from remote content. This command must use a local checkout of `trailofbits/claude-code-config` so the user can inspect, diff, test, and validate what gets installed.

## Find the local checkout

Look for a local repo checkout in this order:

1. The current working directory, if it contains `scripts/install.sh` and `policy/install-manifest.json`
   and its git remote URL resolves to `trailofbits/claude-code-config`
2. `~/src/claude-code-config`
3. `~/code/claude-code-config`
4. `~/src/github.com/trailofbits/claude-code-config`

Treat the current directory as trusted only if:

- `git rev-parse --show-toplevel` resolves successfully
- the top-level directory name is `claude-code-config`
- `git remote get-url origin` or `git remote get-url upstream` resolves to the Trail of Bits repo

If no trusted local checkout exists, stop and tell the user to clone or update the repo locally first. Do not improvise a remote install path.

## Managed components

- **settings.json** — permissions, hooks, telemetry, and statusline config
- **CLAUDE.md** — global development standards and tool preferences
- **MCP servers** — pinned Context7 and Exa entries
- **Statusline script** — two-line status bar with context and cost tracking
- **Hook helper scripts** — tested Bash guard plus optional helper examples
- **review-pr command** — installs `commands/review-pr.md`
- **fix-issue command** — installs `commands/fix-issue.md`
- **merge-dependabot command** — installs `commands/merge-dependabot.md`

## Steps

1. Read `policy/install-manifest.json` from the local checkout so you know exactly what the repo ships.
2. Inventory the current install state with `./scripts/doctor.sh`.
3. Install all managed components with:

   ```bash
   ./scripts/install.sh --all
   ```

4. If the user explicitly wants to overwrite an existing `~/.claude/CLAUDE.md`, rerun the installer with:

   ```bash
   ./scripts/install.sh --component claude-md --force-claude-md
   ```

5. Re-run:

   ```bash
   ./scripts/doctor.sh
   ```

6. Summarize what was installed or updated, and call out any warnings. In particular:
   - remind the user that Exa auth comes from `EXA_API_KEY`
   - mention if `CLAUDE.md` was preserved instead of overwritten
   - mention if required local tools are missing
