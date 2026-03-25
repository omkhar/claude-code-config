#!/bin/bash
set -euo pipefail
# EXAMPLE: PreToolUse hook — blocks the wrong package manager for the repo.
# Adapt for any "use X not Y" convention.
CMD=$(jq -r '.tool_input.command // empty')
[[ -z "$CMD" ]] && exit 0

if [[ -f "${CLAUDE_PROJECT_DIR}/pnpm-lock.yaml" ]] && echo "$CMD" | grep -qE '(^|[[:space:]])(npm|npx)([[:space:]]|$)'; then
	echo "BLOCKED: This project uses pnpm, not npm/npx. Use pnpm instead." >&2
	exit 2
fi

if [[ -f "${CLAUDE_PROJECT_DIR}/uv.lock" ]] && echo "$CMD" | grep -qE '(^|[[:space:]])(pip|pip3)([[:space:]]|$)|python[0-9.]*[[:space:]]+-m[[:space:]]+pip([[:space:]]|$)'; then
	echo "BLOCKED: This project uses uv, not pip. Use uv instead." >&2
	exit 2
fi

exit 0
