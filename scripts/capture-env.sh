#!/usr/bin/env bash
#
# Record what the numbers in results/raw.csv were produced on. Throughput
# figures are meaningless without this.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p results

if [ -n "${ZIG:-}" ]; then :; elif [ -x toolchain/zig ]; then ZIG=./toolchain/zig; else ZIG=zig; fi

{
    echo "# Benchmark environment"
    echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo
    echo "## CPU"
    if command -v lscpu > /dev/null; then
        lscpu | grep -E "^(Architecture|CPU\(s\)|Model name|Thread\(s\) per core|Core\(s\) per socket|Socket|NUMA node\(s\)|Hypervisor|L1d|L1i|L2|L3)" || true
    else
        sysctl -n machdep.cpu.brand_string 2>/dev/null || true
        echo "cores: $(getconf _NPROCESSORS_ONLN 2>/dev/null || echo '?')"
    fi
    echo
    echo "## Toolchains"
    echo "g++: $(g++ --version | head -1)"
    echo "cmake: $(cmake --version | head -1)"
    echo "zig: $("$ZIG" version)"
    echo
    echo "## Compile flags"
    for d in rstm-word rstm-int; do
        f="build/$d/bench/CMakeFiles/CounterBenchSSB64.dir/flags.make"
        if [ -f "$f" ]; then
            echo "RSTM $d flags:   $(grep -m1 'CXX_FLAGS' "$f" | sed 's/CXX_FLAGS = //')"
            echo "RSTM $d defines: $(grep -m1 'CXX_DEFINES' "$f" | sed 's/CXX_DEFINES = //')"
        fi
    done
    echo "zstm:  -Doptimize=ReleaseFast -Dcpu=native"
    echo
    echo "## Kernel"
    uname -a
} > results/env.txt

cat results/env.txt
