#!/usr/bin/env bash
# Build a fresh one-commit tree WITHOUT plots/ or proofs/ and force-push to the
# Hugging Face Space remote. Avoids "binary files" rejection when Git Xet is not installed.
#
# Prerequisite: PNGs must already be on GitHub (origin/main) so README raw URLs work.
#
# Usage:
#   ./scripts/push_hf_lite.sh           # prompts for confirmation
#   ./scripts/push_hf_lite.sh --yes     # non-interactive

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if ! git remote get-url hf >/dev/null 2>&1; then
  echo "error: no git remote named 'hf'. Add it, e.g.:"
  echo "  git remote add hf https://huggingface.co/spaces/<user>/<space-name>"
  exit 1
fi

HF_URL="$(git remote get-url hf)"

if [[ "${1:-}" != "--yes" ]]; then
  echo "This will FORCE-PUSH a new history to: $HF_URL"
  echo "The Space repo will omit plots/ and proofs/ (README loads them from GitHub raw)."
  read -r -p "Continue? [y/N] " ans
  ans_lc="$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')"
  [[ "$ans_lc" == "y" ]] || exit 1
fi

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

echo "Exporting tracked files from HEAD..."
git archive HEAD | tar -x -C "$TMP"

echo "Removing plots/ and proofs/ from export..."
rm -rf "$TMP/plots" "$TMP/proofs"

cd "$TMP"
git init -b main >/dev/null
git add -A
if git diff --cached --quiet; then
  echo "error: nothing to commit (empty export?)"
  exit 1
fi
git commit -m "Deploy Space without plots/proofs (README uses GitHub raw images)" >/dev/null

git remote add hf "$HF_URL"
echo "Force-pushing to hf (main)..."
git push hf main --force

echo "Done. Push origin if README changed: git push origin main"
