#!/bin/bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "${REPO_ROOT}"

shellcheck scripts/*.sh hooks/*.sh
shfmt -d scripts/*.sh hooks/*.sh

python3 -m json.tool settings.json >/dev/null
python3 -m json.tool mcp-template.json >/dev/null
python3 -m json.tool policy/install-manifest.json >/dev/null
python3 -m json.tool policy/managed-settings.example.json >/dev/null

python3 -m py_compile \
	scripts/*.py \
	scripts/lib/*.py \
	hooks/*.py \
	tests/python/*.py \
	tests/mutation/*.py

if command -v actionlint >/dev/null 2>&1 && ls .github/workflows/*.yml >/dev/null 2>&1; then
	actionlint .github/workflows/*.yml
fi

python3 scripts/check_repo_consistency.py

python3 -m coverage erase
python3 -m coverage run -m unittest discover -s tests/python -p 'test_*.py'
python3 -m coverage report --include='scripts/lib/*.py' --fail-under=90

python3 tests/mutation/mutate_python_helpers.py

echo "Repository validation passed."
