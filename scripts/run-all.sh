#!/usr/bin/env bash
#
# Any arguments are forwarded to run-matrix.py, so:
#
#   scripts/run-all.sh                          # thread sweep from nproc
#   scripts/run-all.sh --threads 1,2,4,8,16,32  # explicit sweep
#   scripts/run-all.sh --duration 10 --trials 7 # longer, more repeats
#
# Set ZIG=/path/to/zig to use an existing Zig install
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -z "${ZIG:-}" ] && ! command -v zig > /dev/null; then
    echo "can't find Zig compiler"
    exit 1
fi

echo "==> building RSTM"
scripts/build-rstm.sh

echo "==> building zstm harness"
scripts/build-zstm.sh

echo "==> recording environment"
scripts/capture-env.sh

echo "==> running matrix"
python3 scripts/run-matrix.py "$@"

echo "==> generating tables"
python3 scripts/report.py > /dev/null
echo
echo "results/raw.csv, results/tables.md, results/env.txt"
