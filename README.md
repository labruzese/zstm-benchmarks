# Zig port of RSTM benchmarks for comparison

## Quick start

```sh
scripts/run-all.sh              # everything: fetch Zig, build both, run, report
```
Requirements: a C++ compiler, CMake, Python 3, and Zig 0.16+. If you already
have Zig, set `ZIG=/path/to/zig`.

### Multicore machine

The thread counts defaults to powers of two up to `nproc`, with `nproc` itself
included. Override as:

```sh
scripts/run-all.sh --threads 1,2,4,8,16,32,64 --duration 10 --trials 7
```

Runtime is `configs × workloads × thread-counts × trials × duration`, i.e.
`4 × 5 × |threads| × trials × duration` seconds. The defaults on a 32-core
machine come to about 50 minutes.

## Measurements

| Workload | Description |
|---|---|
| `Counter` | One shared word. Every transaction conflicts with every other; commit-path cost and abort behavior. |
| `ReadNWrite1` | `-O` random reads, then one write. Read-mostly; read log grows, write set holds one entry. |
| `ReadWriteN` | `-O` reads then `-O` writes. Write-heavy; write-set insert and commit-time writeback. |
| `Disjoint` | Switch between reads and writes every other transation; commit-contention. |

## Comparision Validity

### Harness 

[`zig/src/harness.zig`](zig/src/harness.zig) is a port of
`vendor/rstm/bench/bmharness.cpp`: same flags, same three-phase thread barrier,
same `clock_gettime(CLOCK_REALTIME)` clock, same CSV output line, same
`rand_r_32` PRNG (so both walk the identical sequence of array indices), same
`spin64()` inter-transaction filler.

### Element width

RSTM's array benchmarks store `int`. On x86-64 that is a
sub-word access, so RSTM routes it through the `DISPATCH<T,4>` specialization in
`include/api/library_inst.hpp`, a read-modify-write logged at 8-byte
granularity, which makes *adjacent array elements conflict with each other*.
zstm's `TxWord` is a native `usize` with no such behavior. 

We build RSTM twice: stock (`int`) and word-normalized (`intptr_t`, via
`-Dbench_word_elements=ON`). 

### Codegen
Both sides target the host: `-march=native` and `-Dcpu=native`.

## Deviations

1. **Timed-run termination.** RSTM uses `alarm()` + a SIGALRM handler to clear
   `CFG.running`. The Zig harness uses a timer thread that sleeps and then
   clears the same flag. Both are "flip a flag the run loop polls"; the timer
   thread sleeps rather than spins, so it does not compete for a core.

2. **Abort counting.** RSTM reports per-thread aborts from libstm's profiling.
   zstm's `Tx.run` hides its retry loop, so the harness drives transactions with
   zstm's explicit `txBegin`/`txCommit`/`reset` and counts retries itself. 
   `harness.runTx` is step-for-step identical to `Tx.run`; the only addition is 
   an increment on the abort path, which never runs on a successful commit.

## Repository layout

```
vendor/zstm/             zstm 
vendor/rstm/             RSTM v7, minus STAMP/mesh/libitm2stm, some patches
build.zig                builds zstm-bench against vendor/zstm
zig/src/harness.zig      port of RSTM's bmharness.cpp
zig/src/workloads.zig    ports of the four benchmarks
scripts/                 build, run, and report scripts
results/                 raw.csv, tables.md, env.txt
```

## Licensing

RSTM is distributed under the Modified BSD license; see
[`vendor/rstm/LICENSE.RSTM`](vendor/rstm/LICENSE.RSTM). It is vendored here
with small patches fixing a bug and supporting newer toolchains.
