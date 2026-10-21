#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-https://github.com/open-mmlab/mmpose.git}"
# Pinned MMPose commit: its config is executed and its code imported at startup,
# so the checkout must not follow whatever is pushed to main.
MMPOSE_COMMIT="${MMPOSE_COMMIT:-759b39c13fea6ba094afc1fa932f51dc1b11cbf9}"
TARGET_DIR="third_party/mmpose"

mkdir -p "$(dirname "$TARGET_DIR")"

if [[ ! -d "$TARGET_DIR/.git" ]]; then
  echo "[speedy-third-party] Cloning $REPO_URL @ $MMPOSE_COMMIT -> $TARGET_DIR"
  git init -q "$TARGET_DIR"
  git -C "$TARGET_DIR" remote add origin "$REPO_URL"
fi
if [[ "$(git -C "$TARGET_DIR" rev-parse -q --verify HEAD || true)" != "$MMPOSE_COMMIT" ]]; then
  echo "[speedy-third-party] Checking out $MMPOSE_COMMIT in $TARGET_DIR"
  git -C "$TARGET_DIR" fetch -q --depth 1 origin "$MMPOSE_COMMIT"
  git -C "$TARGET_DIR" checkout -q --detach "$MMPOSE_COMMIT"
fi

for s in "$TARGET_DIR/projects" "$TARGET_DIR/mmpose"; do
  if [[ ! -e "$s" ]]; then
    echo "[speedy-third-party] Invalid mmpose checkout, missing sentinel: $s" >&2
    exit 1
  fi
done

echo "[speedy-third-party] Ready (mmpose @ ${MMPOSE_COMMIT:0:12})"
