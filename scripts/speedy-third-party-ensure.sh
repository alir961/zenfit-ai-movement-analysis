#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-https://github.com/open-mmlab/mmpose.git}"
TARGET_DIR="third_party/mmpose"

mkdir -p "$(dirname "$TARGET_DIR")"

if [[ ! -d "$TARGET_DIR/.git" ]]; then
  echo "[speedy-third-party] Cloning $REPO_URL -> $TARGET_DIR"
  git clone --depth 1 --branch main "$REPO_URL" "$TARGET_DIR"
else
  echo "[speedy-third-party] Updating existing repo at $TARGET_DIR"
  git -C "$TARGET_DIR" fetch origin main
  git -C "$TARGET_DIR" checkout main
  git -C "$TARGET_DIR" pull --ff-only origin main
fi

for s in "$TARGET_DIR/projects" "$TARGET_DIR/mmpose"; do
  if [[ ! -e "$s" ]]; then
    echo "[speedy-third-party] Invalid mmpose checkout, missing sentinel: $s" >&2
    exit 1
  fi
done

head="$(git -C "$TARGET_DIR" rev-parse --short HEAD)"
echo "[speedy-third-party] Ready (main @ $head)"