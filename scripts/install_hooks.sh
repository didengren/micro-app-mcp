#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

git config core.hooksPath .githooks
chmod +x .githooks/pre-commit

current="$(git config --get core.hooksPath)"
echo "core.hooksPath=${current}"
echo "hook installed: .githooks/pre-commit"
