#!/usr/bin/env bash

set -euo pipefail

echo "Preparing AI-STL-FORGE commit..."

git status --short
git add -A

echo "\nStaged files:"
git diff --cached --name-only

git commit -m "v2.0.0: production release hardening\n\n- Add cookie-cutter STL mode support\n- Speed up mesh generation with vectorized geometry path\n- Extend smoke test with cookie-cutter coverage\n- Add integration tests for cookie-cutter and batch flows\n- Refresh README production documentation"

echo "Commit complete."
