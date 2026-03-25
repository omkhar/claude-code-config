#!/bin/bash
set -euo pipefail
# EXAMPLE: PostToolUse hook — logs GAM (Google Apps Manager) write operations
# to JSONL. Adapt the verb patterns for any CLI tool where you want an audit
# trail of mutations. See README.md for wiring instructions.
INPUT=$(cat)
COMMAND=$(echo "${INPUT}" | jq -r '.tool_input.command // empty')

[[ -z "${COMMAND}" ]] && exit 0
[[ "${COMMAND}" != *'gam7/gam '* ]] && exit 0

# Verb lists verified against GamCommands.txt v7.33.00
READ_PATTERN='(print|show|info|get|list|report|check|version|help)'
WRITE_PATTERN='(create|add|update|delete|remove|suspend|unsuspend|wipe|sync|move|transfer|trash|purge|enable|disable|deprovision)'

GAM_ARGS="${COMMAND#*gam7/gam }"
FIRST_WORD="${GAM_ARGS%% *}"

# Skip read operations
echo "${FIRST_WORD}" | grep -qiE "^${READ_PATTERN}$" && exit 0

# Match write verb
ACTION=$(echo "${GAM_ARGS}" | grep -oiE "(^|[[:space:]])${WRITE_PATTERN}([[:space:]]|$)" |
	head -1 | tr -d ' ' || true)
[[ -z "${ACTION}" ]] && exit 0

# Log the mutation
EXIT_CODE=$(echo "${INPUT}" | jq -r '.tool_result.exit_code // 0')
[[ "${EXIT_CODE}" == "0" ]] && STATUS="success" || STATUS="failed"
LOG_DIR="${CLAUDE_AUDIT_DIR:-${HOME}/.claude/audit}"
LOG_FILE="${LOG_DIR}/gam-mutations.jsonl"
mkdir -p "${LOG_DIR}"
chmod 700 "${LOG_DIR}"

COMMAND_PREVIEW=$(echo "${COMMAND}" |
	sed -E 's/(--?(token|password|secret|key)[=[:space:]]+)[^[:space:]]+/\1[REDACTED]/gi')
COMMAND_HASH=$(printf '%s' "${COMMAND}" | shasum -a 256 | awk '{print $1}')

jq -nc \
	--arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
	--arg action "${ACTION}" \
	--arg command_preview "${COMMAND_PREVIEW}" \
	--arg command_sha256 "${COMMAND_HASH}" \
	--arg status "${STATUS}" \
	'{timestamp: $ts, action: $action, command_preview: $command_preview, command_sha256: $command_sha256, status: $status}' \
	>>"${LOG_FILE}"
chmod 600 "${LOG_FILE}"

# Remind the operator
if [[ "${STATUS}" == "success" ]]; then
	echo "GAM MUTATION: ${ACTION} — logged to ${LOG_FILE}"
fi
exit 0
