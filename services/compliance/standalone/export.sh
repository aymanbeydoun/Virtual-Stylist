#!/usr/bin/env bash
# Export the compliance agent as a standalone repository tree.
#
#   ./standalone/export.sh /path/to/bfl-compliance-agent
#
# Copies the service + e2e pipeline to the target, applies the
# standalone-specific files (root README, .gitignore, GitHub workflows),
# and initializes a git repo on `main` if the target isn't one already.
set -euo pipefail

TARGET="${1:?usage: export.sh <target-dir>}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$TARGET"
tar -C "$SRC" \
  --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' \
  --exclude='.mypy_cache' --exclude='.ruff_cache' --exclude='e2e-artifacts' \
  --exclude='.env' --exclude='./standalone' --exclude='.git' \
  -cf - . | tar -C "$TARGET" -xf -

mkdir -p "$TARGET/.github/workflows"
cp "$SRC/standalone/workflows/"*.yml "$TARGET/.github/workflows/"
cp "$SRC/standalone/README.md" "$TARGET/README.md"
cp "$SRC/standalone/gitignore" "$TARGET/.gitignore"

if [ ! -d "$TARGET/.git" ]; then
  git -C "$TARGET" init -b main
fi
git -C "$TARGET" add -A
echo "Standalone tree ready at: $TARGET"
echo "Next: git -C '$TARGET' commit, add the GitHub remote, push."
