#!/usr/bin/env bash
#
# Build RSTM v7's microbenchmarks in three configurations:
#
#   build/rstm-int      stock: array elements are `int` (sub-word on x86-64)
#   build/rstm-word     elements are `intptr_t`, matching zstm's usize TxWord
#   build/rstm-word-na  as rstm-word, minus the adaptivity timing
#
# The first two differ only in element width (see bench/bench_elem.hpp). 
#
# The third additionally compiles out the two rdtsc's that stm::begin/stm::commit
# execute per transaction to feed the adaptive policy decider -- which never
# runs, because STM_CONFIG pins one algorithm for the whole process.
#
# All produce <Bench>SSB64 binaries under bench/. The STM algorithm is chosen
# at via the STM_CONFIG env var (NOrec, CGL, ...).
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
# RSTM configures in cmake/UserOverrides.cmake (-march=native -O3 ...)
configure_and_build build/rstm-int     -Dbench_word_elements=OFF
configure_and_build build/rstm-word    -Dbench_word_elements=ON
configure_and_build build/rstm-word-na -Dbench_word_elements=ON \
                                       -Dlibstm_enable_adaptivity_timing=OFF

# Just check that adaptivity-timing option has to actually taken effect
if cmp -s build/rstm-word/bench/CounterBenchSSB64 \
          build/rstm-word-na/bench/CounterBenchSSB64; then
    echo "ERROR: rstm-word and rstm-word-na produced identical binaries;" >&2
    echo "       libstm_enable_adaptivity_timing did not take effect." >&2
    exit 1
fi

for d in build/rstm-int build/rstm-word build/rstm-word-na; do
    for b in CounterBench ReadNWrite1Bench ReadWriteNBench DisjointBench; do
        test -x "$d/bench/${b}SSB64" || { echo "MISSING: $d/bench/${b}SSB64"; exit 1; }
    done
done

echo "RSTM built: build/rstm-int, build/rstm-word, build/rstm-word-na"
