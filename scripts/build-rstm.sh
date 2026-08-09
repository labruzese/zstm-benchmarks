#!/usr/bin/env bash
#
# Build RSTM v7's microbenchmarks in two element-type configurations:
#
#   build/rstm-int   stock: array elements are `int` (sub-word on x86-64)
#   build/rstm-word  elements are `intptr_t`, matching zstm's usize-sized TxWord
#
# Both produce <Bench>SSB64 binaries under bench/. The STM algorithm is chosen
# at *run* time via the STM_CONFIG env var (NOrec, CGL, ...), not at build time.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

JOBS="$(nproc)"

configure_and_build() {
    local dir="$1"; shift
    cmake -S vendor/rstm -B "$dir" -Wno-dev \
        -DCMAKE_BUILD_TYPE=Release \
        -Drstm_enable_stamp=OFF \
        -Drstm_enable_mesh=OFF \
        -Drstm_enable_itm2stm=OFF \
        -Drstm_enable_bench=ON \
        -Drstm_build_32-bit=OFF \
        -Drstm_build_64-bit=ON \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        "$@" > "$dir.configure.log" 2>&1 || { cat "$dir.configure.log"; exit 1; }
    make -C "$dir" -j"$JOBS" > "$dir.build.log" 2>&1 || { tail -40 "$dir.build.log"; exit 1; }
}

mkdir -p build
# NB: the element type is selected with -Dbench_word_elements, never with
# -DCMAKE_CXX_FLAGS -- setting the latter on the command line replaces the flags
# RSTM configures in cmake/UserOverrides.cmake (-march=native -O3 ...), silently
# building one variant without optimization flags the other one gets.
configure_and_build build/rstm-int  -Dbench_word_elements=OFF
configure_and_build build/rstm-word -Dbench_word_elements=ON

for d in build/rstm-int build/rstm-word; do
    for b in CounterBench ReadNWrite1Bench ReadWriteNBench DisjointBench; do
        test -x "$d/bench/${b}SSB64" || { echo "MISSING: $d/bench/${b}SSB64"; exit 1; }
    done
done

echo "RSTM built: build/rstm-int, build/rstm-word"
