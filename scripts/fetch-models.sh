#!/usr/bin/env bash
# Fetch what the workspace backend loads at startup: the MMPose sources
# (RTMPose3D config) under third_party/ and the RTMW3D-L checkpoint at the repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

./scripts/speedy-third-party-ensure.sh

CKPT="rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth"
URL="https://download.openmmlab.com/mmpose/v1/wholebody_3d_keypoint/rtmw3d/$CKPT"
# The checkpoint is a pickle, which can run code when loaded: only keep the known file.
SHA256="794dbc78b04a43d81781f8ab0eba5b24f3dd5d71aaf6ae253940424159fb81ed"

verify() {
  if command -v sha256sum >/dev/null 2>&1; then
    echo "$SHA256  $1" | sha256sum -c --status
  else
    echo "$SHA256  $1" | shasum -a 256 -c --status
  fi
}

if [[ -f "$CKPT" ]]; then
  if ! verify "$CKPT"; then
    echo "[fetch-models] $CKPT does not match the expected SHA-256; delete it and run again" >&2
    exit 1
  fi
  echo "[fetch-models] $CKPT already present (checksum OK)"
else
  echo "[fetch-models] Downloading $CKPT"
  curl -fL --retry 3 -o "$CKPT.part" "$URL"
  if ! verify "$CKPT.part"; then
    rm -f "$CKPT.part"
    echo "[fetch-models] Downloaded file does not match the expected SHA-256" >&2
    exit 1
  fi
  mv "$CKPT.part" "$CKPT"
fi
