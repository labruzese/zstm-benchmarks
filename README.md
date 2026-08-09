# zstm vs. RSTM NOrec

A head-to-head throughput comparison of two implementations of the **same** STM
algorithm:

- **[zstm](vendor/zstm)** — NOrec in Zig. Global sequence lock, value-based
  validation over a read log, redo log in a hash map, ALA/SLA modes.
- **[RSTM v7](vendor/rstm)** — the Rochester/Lehigh STM library, whose
  `libstm/algs/norec.cpp` is a reference implementation of the same algorithm
  from the paper that introduced it (Dalessandro, Spear & Scott, *NOrec:
  Streamlining STM by Abolishing Ownership Records*, PPoPP'10).

Because the algorithm is held fixed, differences in the numbers are attributable
to implementation choices — data structures, barrier fast paths, abort
mechanism — rather than to algorithmic ones. **RSTM CGL** (a single coarse-grained
lock) is measured alongside as a baseline, so "how much does the STM cost" has a
reference point.

See **[RESULTS.md](RESULTS.md)** for the numbers and the analysis.

## Quick start

```sh
scripts/run-all.sh              # everything: fetch Zig, build both, run, report
```

Or step by step:

```sh
toolchain/get-zig.sh            # Zig 0.16.0, from the PyPI `ziglang` wheel
scripts/build-rstm.sh           # builds build/rstm-int and build/rstm-word
scripts/build-zstm.sh           # builds zig-out/bin/zstm-bench
scripts/capture-env.sh          # writes results/env.txt
scripts/run-matrix.py           # writes results/raw.csv
scripts/report.py               # writes results/tables.md
```

Requirements: a C++ compiler, CMake, Python 3, and Zig 0.16+. If you already
have Zig, set `ZIG=/path/to/zig` and skip `get-zig.sh`; otherwise `get-zig.sh`
installs it from the PyPI `ziglang` wheel (which bundles the genuine upstream
toolchain) into a local venv. `vendor/zstm` declares
`minimum_zig_version = "0.16.0"`.

### Running on a multicore machine

The thread sweep defaults to powers of two up to `nproc`, with `nproc` itself
included — so a 32-core box sweeps 1,2,4,8,16,32 with no arguments. Override it,
and the run length, as you like:

```sh
scripts/run-all.sh --threads 1,2,4,8,16,32,64 --duration 10 --trials 7
```

Runtime is `configs × workloads × thread-counts × trials × duration`, i.e.
`4 × 5 × |threads| × trials × duration` seconds. The defaults on a 32-core
machine come to about 50 minutes.

Two things worth doing for numbers you can trust: run it on an otherwise idle
machine (the harness measures wall-clock throughput, so any competing load shows
up directly in the results), and check the "Measurement spread" table that
`report.py` emits — if the max/min ratio across trials is large, raise
`--trials` or `--duration` before reading anything into small differences.

Results land in `results/`. `results/env.txt` records the CPU, toolchain
versions, and exact compile flags; keep it with any numbers you share, since
throughput figures mean nothing without it.

## What is measured

Four microbenchmarks, ported from `vendor/rstm/bench/` to Zig in
[`zig/src/workloads.zig`](zig/src/workloads.zig):

| Workload | What it stresses |
|---|---|
| `Counter` | One shared word. Every transaction conflicts with every other: commit-path cost and abort behavior. |
| `ReadNWrite1` | `-O` random reads, then one write. Read-mostly; read log grows, write set holds one entry. |
| `ReadWriteN` | `-O` reads then `-O` writes. Write-heavy; write-set insert and commit-time writeback. |
| `Disjoint` | Per-thread private, cache-line-padded buffers, so transactions **never** conflict. Pure instrumentation overhead — the cleanest signal in the suite. |

## Making the comparison fair

The interesting part of this project is the set of things that had to be
equalized before the numbers meant anything.

**Identical harness.** [`zig/src/harness.zig`](zig/src/harness.zig) is a port of
`vendor/rstm/bench/bmharness.cpp`: same flags, same three-phase thread barrier,
same `clock_gettime(CLOCK_REALTIME)` clock, same CSV output line, same
`rand_r_32` PRNG (so both walk the identical sequence of array indices), same
`spin64()` inter-transaction filler.

**Element width.** RSTM's array benchmarks store `int`. On x86-64 that is a
sub-word access, so RSTM routes it through the `DISPATCH<T,4>` specialization in
`include/api/library_inst.hpp` — a masked read-modify-write logged at 8-byte
granularity, which makes *adjacent array elements conflict with each other*.
zstm's `TxWord` is a native `usize` with no such behavior. We therefore build
RSTM twice: stock (`int`) and word-normalized (`intptr_t`, via
`-Dbench_word_elements=ON`). **The word build is the apples-to-apples
comparison**; the `int` build is reported alongside as the stock-RSTM reference.
See [`vendor/rstm/bench/bench_elem.hpp`](vendor/rstm/bench/bench_elem.hpp).

**Codegen.** RSTM hardcodes `-march=core2 -mtune=core2` (contemporary in 2011).
Left alone, RSTM would be generating code for a 2006 CPU while Zig targeted the
host. Both sides now target the host: `-march=native` and `-Dcpu=native`.

Note that the element type must be selected with `-Dbench_word_elements`, not
with `-DCMAKE_CXX_FLAGS` — setting the latter on the command line *replaces*
the flags RSTM configures in `cmake/UserOverrides.cmake`, silently building one
variant without the optimization flags the other one gets.

**Log capacity.** Both sides pre-size their read log and write set so the timed
region allocates nothing. On the zstm side this must be sized to the workload's
*actual* maximum and no larger: zstm's write set is a `std.AutoHashMapUnmanaged`,
whose `clearRetainingCapacity` memsets the whole metadata array, so `Tx.reset`
costs O(reserved capacity) rather than O(entries used). Reserving a blanket 4096
entries made every transaction memset ~4 KB and understated zstm by roughly 20x
on three of the four workloads. (RSTM's `WriteSet::reset` is O(1) — it bumps a
version stamp; `include/stm/WriteSet.hpp:452`.)

## Deliberate deviations

Documented rather than hidden, because each one is a judgement call:

1. **Timed-run termination.** RSTM uses `alarm()` + a SIGALRM handler to clear
   `CFG.running`. The Zig harness uses a timer thread that sleeps and then
   clears the same flag. Both are "flip a flag the run loop polls"; the timer
   thread sleeps rather than spins, so it does not compete for a core.

2. **Abort counting.** RSTM reports per-thread aborts from libstm's profiling.
   zstm's `Tx.run` hides its retry loop, so the harness drives transactions with
   zstm's explicit `txBegin`/`txCommit`/`reset` API — documented as public and
   supported in `root.zig` — and counts retries itself. `harness.runTx` is
   step-for-step identical to `Tx.run`; the only addition is an increment on the
   abort path, which never runs on a successful commit.

3. **An upstream bug is preserved.** `vendor/rstm/bench/Disjoint.hpp` contains
   `if (i && 0x1)` where `i & 0x1` was plainly intended, so the condition is true
   for every `i != 0`. The Zig port reproduces this deliberately. Fixing it on
   one side only would change the read/write mix there and invalidate the
   comparison.

## Repository layout

```
toolchain/get-zig.sh     Zig 0.16.0 installer (PyPI wheel) + `zig` shim
vendor/zstm/             zstm, verbatim
vendor/rstm/             RSTM v7, minus STAMP/mesh/libitm2stm; see patches/
patches/                 every change made to vendored RSTM, as readable diffs
build.zig                builds zstm-bench against vendor/zstm
zig/src/harness.zig      port of RSTM's bmharness.cpp
zig/src/workloads.zig    ports of the four microbenchmarks
scripts/                 build, run, and report scripts
results/                 raw.csv, tables.md, env.txt
```

## Licensing

RSTM is distributed under the Modified BSD license; see
[`vendor/rstm/LICENSE.RSTM`](vendor/rstm/LICENSE.RSTM). It is vendored here
unmodified except for the changes recorded in [`patches/`](patches). zstm is
vendored verbatim.
