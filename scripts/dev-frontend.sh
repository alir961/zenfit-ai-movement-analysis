#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../workspace/frontend"
bun run dev
