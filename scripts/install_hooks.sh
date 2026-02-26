#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

git config core.hooksPath .githooks
chmod +x .githooks/pre-commit

current="$(git config --get core.hooksPath)"
echo "core.hooksPath=${current}"
echo "hook installed: .githooks/pre-commit"
echo ""
echo "提示: 版本号和 changelog 由 commitizen 管理"
echo "  - 提交代码: uv run cz commit"
echo "  - 发布版本: uv run cz bump && git push --tags"
