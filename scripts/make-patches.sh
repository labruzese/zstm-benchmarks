#!/usr/bin/env bash
#
# Regenerate patches/ from a pristine RSTM v7 tree.
#
# patches/ exists so a reader can see exactly what was changed in the vendored
# copy of RSTM without diffing against an upstream tarball by hand. The vendored
# tree under vendor/rstm/ already has these changes applied; this script only
# refreshes the human-readable record of them.
#
# Usage: scripts/make-patches.sh /path/to/pristine/rstm
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRISTINE="${1:?usage: make-patches.sh /path/to/pristine/rstm}"

cd "$ROOT"
mkdir -p patches

emit() {
    local n="$1" name="$2" desc="$3"; shift 3
    local out="patches/${n}-${name}.patch"
    { echo "# $desc"; echo "#"; } > "$out"
    for f in "$@"; do
        if [ -f "$PRISTINE/$f" ]; then
            diff -u "$PRISTINE/$f" "vendor/rstm/$f" \
                --label "a/$f" --label "b/$f" >> "$out" || true
        else
            echo "# (new file: $f)" >> "$out"
            diff -u /dev/null "vendor/rstm/$f" \
                --label /dev/null --label "b/$f" >> "$out" || true
        fi
    done
    echo "wrote $out"
}

emit 0001 build-on-modern-cmake \
    "Quote CMAKE_THREAD_LIBS_INIT. It is empty on glibc >= 2.34 (pthreads live in libc), and unquoted it leaves string(REGEX MATCH) with too few arguments, so configure fails outright on CMake 3.28." \
    CMakeLists.txt

emit 0002 march-native \
    "Target the host CPU instead of the hardcoded -march=core2 -mtune=core2. Comparing 2006-era codegen against a native-targeted Zig build would not be a fair fight." \
    cmake/UserOverrides.cmake

emit 0003 word-sized-elements \
    "Parameterize the microbenchmark element type. RSTM's benches store 'int', which on x86-64 goes through the sub-word DISPATCH<T,4> path: a masked read-modify-write logged at word granularity, so adjacent elements falsely conflict. zstm's TxWord is a native usize. -Dbench_word_elements=ON switches to intptr_t for an apples-to-apples comparison; the default keeps stock behavior." \
    bench/bench_elem.hpp \
    bench/CMakeLists.txt \
    bench/CounterBench.cpp \
    bench/ReadNWrite1Bench.cpp \
    bench/ReadWriteNBench.cpp \
    bench/DisjointBench.cpp \
    bench/Disjoint.hpp

echo
echo "Note: STAMP, mesh, and libitm2stm were removed from the vendored tree"
echo "(unused here, ~2MB); that removal is not represented as a patch."
