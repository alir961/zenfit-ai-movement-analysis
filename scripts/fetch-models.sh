#!/usr/bin/env bash
# Fetch what the workspace backend loads at startup: the MMPose sources
# (RTMPose3D config) under third_party/ and the RTMW3D-L checkpoint at the repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

./scripts/speedy-third-party-ensure.sh

CKPT="rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth"
URL="https://download.openmmlab.com/mmpose/v1/wholebody_3d_keypoint/rtmw3d/$CKPT"
if [[ -f "$CKPT" ]]; then
  echo "[fetch-models] $CKPT already present"
else
  echo "[fetch-models] Downloading $CKPT"
  curl -fL --retry 3 -o "$CKPT.part" "$URL"
  mv "$CKPT.part" "$CKPT"
fi
