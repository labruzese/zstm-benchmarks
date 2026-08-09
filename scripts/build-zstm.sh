#!/usr/bin/env bash
#
# Build the Zig benchmark driver (zig-out/bin/zstm-bench) against vendor/zstm.
#
# Uses $ZIG if set, else toolchain/zig (installed by toolchain/get-zig.sh), else
# a `zig` on PATH. Zig 0.16.0 or newer is required -- vendor/zstm declares
# minimum_zig_version = "0.16.0".
#
# -Dcpu=native matches the -march=native that RSTM's build uses, so neither side
# is handicapped on codegen.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -n "${ZIG:-}" ]; then
    :
elif [ -x toolchain/zig ]; then
    ZIG=./toolchain/zig
elif command -v zig > /dev/null; then
    ZIG=zig
else
    echo "no zig found: set \$ZIG, or run toolchain/get-zig.sh" >&2
    exit 1
fi

echo "using zig: $ZIG ($("$ZIG" version))"

# Confirm the vendored library is sound on this toolchain before trusting any
# timing it produces. zstm's suite includes real concurrency checks.
"$ZIG" build test

"$ZIG" build -Doptimize=ReleaseFast -Dcpu=native

test -x zig-out/bin/zstm-bench
echo "built zig-out/bin/zstm-bench"
