#!/usr/bin/env python3
"""
Run the full benchmark matrix and append every result to results/raw.csv.

Runs are strictly sequential -- a second benchmark executing concurrently would
poison the measurement. Each (config, workload, thread count) cell is measured
`--trials` times; report.py takes the median.

Runs are pinned, by default, to one logical CPU per physical performance core
(see pick_cpus). Without pinning the thread sweep silently changes what a
"thread" costs partway up: on a hybrid Intel part, p=1..8 lands on P-cores,
p=16 starts doubling up SMT siblings, and p=24 starts recruiting E-cores. The
resulting curve mixes algorithmic scaling with core-type changes and cannot be
read as scaling at all. 

Usage:  scripts/run-matrix.py [--duration 5] [--trials 5] [--threads 1,2,4,8]
                              [--no-pin | --cpus 0,2,4,6]
"""

import argparse
import csv
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time


def _parse_cpulist(text):
    """Parse a Linux cpulist ("0-3,8,10-11") into a sorted list of ints."""
    out = []
    for part in text.strip().split(","):
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-")
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def _read(path):
    try:
        return pathlib.Path(path).read_text()
    except OSError:
        return None


def pick_cpus():
    """One logical CPU per physical performance core, in order.

    Two things get filtered out, in this order:

      1. Efficiency cores. On hybrid Intel parts the kernel exposes the split as
         /sys/devices/system/cpu/types/intel_core_*/cpulist (P) vs intel_atom_*
         (E). Older kernels only have cpu_capacity, where the P-cores carry the
         larger number; we take the top capacity class. A P-core and an E-core
         differ by roughly 2x on this workload, so mixing them makes a thread
         count mean two different things.

      2. SMT siblings. thread_siblings_list groups the logical CPUs sharing one
         physical core; we keep the lowest-numbered of each group. Two threads
         on one core share L1 and the store buffer, which is a different
         experiment from two threads on two cores.

    Returns None if the topology cannot be read (non-Linux, container with no
    /sys), in which case the caller falls back to not pinning.
    """
    online = _read("/sys/devices/system/cpu/online")
    if online is None:
        return None
    cpus = _parse_cpulist(online)
    if not cpus:
        return None

    # 1. performance cores
    perf = None
    types = sorted(pathlib.Path("/sys/devices/system/cpu/types").glob("intel_core_*")) \
        if pathlib.Path("/sys/devices/system/cpu/types").is_dir() else []
    for t in types:
        cpulist = _read(t / "cpulist")
        if cpulist:
            perf = (perf or []) + _parse_cpulist(cpulist)
    if perf is None:
        caps = {}
        for c in cpus:
            v = _read(f"/sys/devices/system/cpu/cpu{c}/cpu_capacity")
            if v is not None:
                caps[c] = int(v.strip())
        if caps and len(set(caps.values())) > 1:
            top = max(caps.values())
            perf = [c for c, v in caps.items() if v == top]
    if perf:
        cpus = [c for c in cpus if c in set(perf)]

    # 2. one logical CPU per physical core
    seen, out = set(), []
    for c in cpus:
        sib = _read(f"/sys/devices/system/cpu/cpu{c}/topology/thread_siblings_list")
        key = tuple(_parse_cpulist(sib)) if sib else (c,)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out or None


def default_threads(n):
    """1, 2, 4, ... up to n, always including n itself."""
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
    ("zstm-ala",          "zstm", None,                 None),
    # ("rstm-word-norec",   "rstm", "build/rstm-word",    "NOrec"),
    ("rstm-word-na-norec", "rstm", "build/rstm-word-na", "NOrec"),
    # ("rstm-int-norec",    "rstm", "build/rstm-int",     "NOrec"),
    ("rstm-word-cgl",     "rstm", "build/rstm-word",    "CGL"),
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


def run_one(config, workload, threads, duration, cpus=None):
    label, kind, build, stm_config = config
    cell, zig_name, rstm_stem, extra = workload

    env = dict(os.environ)
    if kind == "zstm":
        cmd = [str(ROOT / "zig-out/bin/zstm-bench"), "-b", zig_name]
    else:
        cmd = [str(ROOT / build / "bench" / f"{rstm_stem}SSB64")]
        env["STM_CONFIG"] = stm_config
    cmd += ["-p", str(threads), "-d", str(duration)] + extra
    if cpus:
        # Pin to exactly as many CPUs as there are threads, so a p=4 run cannot
        # be handed 8 cores by the scheduler and a p=1 run always lands on the
        # same core it did for every other config.
        cmd = ["taskset", "-c",
               ",".join(str(c) for c in cpus[:threads])] + cmd

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
                    help="comma-separated thread counts (default: powers of two "
                         "up to the number of pinned cores, plus that count)")
    ap.add_argument("--cpus", default=None,
                    help="explicit comma-separated CPU list to pin to, in the "
                         "order threads should fill it")
    ap.add_argument("--no-pin", action="store_true",
                    help="do not pin; let the scheduler place threads")
    args = ap.parse_args()

    cpus = None
    if args.cpus:
        cpus = [int(c) for c in args.cpus.split(",")]
    elif not args.no_pin:
        cpus = pick_cpus()
        if cpus is None:
            print("note: could not read CPU topology; running unpinned")
    if cpus and not shutil.which("taskset"):
        print("note: taskset not found; running unpinned")
        cpus = None
    if cpus:
        print(f"pinning to {len(cpus)} cores: "
              f"{','.join(str(c) for c in cpus)}")

    n = len(cpus) if cpus else (os.cpu_count() or 1)
    thread_counts = ([int(t) for t in args.threads.split(",")]
                     if args.threads else default_threads(n))
    if cpus and max(thread_counts) > len(cpus):
        print(f"info: thread counts go to {max(thread_counts)} but only "
              f"{len(cpus)} cores are pinned; those cells oversubscribe")
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
                        row = run_one(config, workload, threads, args.duration,
                                      cpus)
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
