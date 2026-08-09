#!/usr/bin/env python3
"""
Run the full benchmark matrix and append every result to results/raw.csv.

Runs are strictly sequential -- a second benchmark executing concurrently would
poison the measurement. Each (config, workload, thread count) cell is measured
`--trials` times; report.py takes the median.

By default the thread sweep is derived from this machine's core count: powers of
two up to nproc, with nproc itself included. Override with --threads.

Usage:  scripts/run-matrix.py [--duration 5] [--trials 5] [--threads 1,2,4,8]
"""

import argparse
import csv
import os
import pathlib
import re
import subprocess
import sys
import time


def default_threads():
    """1, 2, 4, ... up to the core count, always including the core count."""
    n = os.cpu_count() or 1
    counts = []
    p = 1
    while p <= n:
        counts.append(p)
        p *= 2
    if n not in counts:
        counts.append(n)
    return counts

ROOT = pathlib.Path(__file__).resolve().parent.parent

# (label, kind, build-dir-or-None, STM_CONFIG-or-None)
CONFIGS = [
    ("zstm-ala",       "zstm", None,              None),
    ("rstm-word-norec", "rstm", "build/rstm-word", "NOrec"),
    ("rstm-int-norec",  "rstm", "build/rstm-int",  "NOrec"),
    ("rstm-word-cgl",   "rstm", "build/rstm-word", "CGL"),
]

# (cell label, zig workload name, rstm binary stem, extra args)
WORKLOADS = [
    ("Counter",          "Counter",     "CounterBench",     []),
    ("ReadNWrite1/m256", "ReadNWrite1", "ReadNWrite1Bench", ["-m", "256", "-O", "8"]),
    ("ReadNWrite1/m4096", "ReadNWrite1", "ReadNWrite1Bench", ["-m", "4096", "-O", "8"]),
    ("ReadWriteN/m256",  "ReadWriteN",  "ReadWriteNBench",  ["-m", "256", "-O", "8"]),
    ("Disjoint/16-8-2",  "Disjoint",    "DisjointBench",    ["-B", "PrDw-16-8-2"]),
]

CSV_RE = re.compile(r"^csv,.*txns=(\d+), time=(\d+), throughput=(\d+)")
ZIG_ABORTS_RE = re.compile(r"^aborts, (\d+)")
RSTM_ABORTS_RE = re.compile(r"Aborts: (\d+)")
FIELDS = ["config", "bench", "threads", "trial", "txns", "time_ns", "throughput",
          "aborts", "verified"]


def run_one(config, workload, threads, duration):
    label, kind, build, stm_config = config
    cell, zig_name, rstm_stem, extra = workload

    env = dict(os.environ)
    if kind == "zstm":
        cmd = [str(ROOT / "zig-out/bin/zstm-bench"), "-b", zig_name]
    else:
        cmd = [str(ROOT / build / "bench" / f"{rstm_stem}SSB64")]
        env["STM_CONFIG"] = stm_config
    cmd += ["-p", str(threads), "-d", str(duration)] + extra

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                          timeout=duration * 20 + 120)
    if proc.returncode != 0:
        sys.exit(f"FAILED ({proc.returncode}): {' '.join(cmd)}\n"
                 f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")

    out = proc.stdout + proc.stderr
    m = CSV_RE.search(out) or next(
        (CSV_RE.match(l) for l in out.splitlines() if CSV_RE.match(l)), None)
    if m is None:
        for line in out.splitlines():
            m = CSV_RE.match(line)
            if m:
                break
    if m is None:
        sys.exit(f"no csv line from {' '.join(cmd)}\n{out}")

    txns, time_ns, throughput = (int(g) for g in m.groups())

    aborts = 0
    for line in out.splitlines():
        za = ZIG_ABORTS_RE.match(line)
        if za:
            aborts += int(za.group(1))
        for ra in RSTM_ABORTS_RE.finditer(line):
            aborts += int(ra.group(1))

    verified = "Verification: Passed" in out
    if not verified:
        sys.exit(f"VERIFICATION FAILED: {' '.join(cmd)}\n{out}")

    return dict(config=label, bench=cell, threads=threads, trial=None,
                txns=txns, time_ns=time_ns, throughput=throughput,
                aborts=aborts, verified=int(verified))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=5,
                    help="seconds per run (default 5)")
    ap.add_argument("--trials", type=int, default=5,
                    help="repeats per cell; report.py takes the median (default 5)")
    ap.add_argument("--threads", default=None,
                    help="comma-separated thread counts "
                         f"(default for this machine: "
                         f"{','.join(str(t) for t in default_threads())})")
    args = ap.parse_args()

    thread_counts = ([int(t) for t in args.threads.split(",")]
                     if args.threads else default_threads())
    out_path = ROOT / "results" / "raw.csv"
    out_path.parent.mkdir(exist_ok=True)

    total = len(CONFIGS) * len(WORKLOADS) * len(thread_counts) * args.trials
    done = 0
    started = time.time()

    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for trial in range(1, args.trials + 1):
            for workload in WORKLOADS:
                for threads in thread_counts:
                    for config in CONFIGS:
                        row = run_one(config, workload, threads, args.duration)
                        row["trial"] = trial
                        writer.writerow(row)
                        fh.flush()
                        done += 1
                        elapsed = time.time() - started
                        eta = elapsed / done * (total - done)
                        print(f"[{done:3d}/{total}] {row['config']:<16} "
                              f"{row['bench']:<19} p={threads} t={trial}  "
                              f"{row['throughput']:>10,} txn/s   ETA {eta/60:.1f}m",
                              flush=True)

    print(f"\nwrote {out_path} ({done} runs in {(time.time()-started)/60:.1f} min)")


if __name__ == "__main__":
    main()
