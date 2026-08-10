#!/usr/bin/env python3
"""
Turn results/raw.csv into markdown tables (results/tables.md).

Each cell is the median across trials. Each cell also carries
its own max/min spread, because a median printed to seven significant figures
implies a precision that a cell with 3x spread does not have; cells above
--max-spread are marked so a noisy run cannot be read as a result.
"""

import argparse
import collections
import csv
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "results" / "raw.csv"
OUT = ROOT / "results" / "tables.md"

# Reference config for the ratio column: RSTM NOrec with the adaptivity rdtsc's
# compiled out, so the ratio reflects the algorithms rather than the framework
# around them. Falls back to the stock word build when that config is absent.
BASELINE = ["rstm-word-na-norec", "rstm-word-norec"]

CONFIG_ORDER = ["zstm-ala", "rstm-word-norec", "rstm-word-na-norec",
                "rstm-int-norec", "rstm-word-cgl"]
CONFIG_LABEL = {
    "zstm-ala": "zstm (ALA)",
    "rstm-word-norec": "RSTM NOrec (word)",
    "rstm-word-na-norec": "RSTM NOrec (word, no adapt)",
    "rstm-int-norec": "RSTM NOrec (int)",
    "rstm-word-cgl": "RSTM CGL",
}


def load():
    rows = list(csv.DictReader(open(RAW)))
    # (bench, threads, config) -> list of throughputs / aborts / txns
    tput = collections.defaultdict(list)
    aborts = collections.defaultdict(list)
    txns = collections.defaultdict(list)
    for r in rows:
        key = (r["bench"], int(r["threads"]), r["config"])
        tput[key].append(int(r["throughput"]))
        aborts[key].append(int(r["aborts"]))
        txns[key].append(int(r["txns"]))
    return rows, tput, aborts, txns


def med(d, key):
    return statistics.median(d[key]) if key in d else None


def spread(d, key):
    """max/min across trials for one cell, or None if it can't be computed."""
    vals = d.get(key)
    if not vals or len(vals) < 2 or min(vals) <= 0:
        return None
    return max(vals) / min(vals)


def fmt(n):
    return f"{n:,.0f}" if n is not None else "--"


def fmt_cell(tput, key, max_spread):
    """Median plus its own spread, so noisy cells cannot pass as precise."""
    v = med(tput, key)
    if v is None:
        return "--"
    s = spread(tput, key)
    if s is None:
        return fmt(v)
    mark = "!" if s >= max_spread else ""
    return f"{fmt(v)}<br><sub>{mark}{s:.2f}x</sub>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-spread", type=float, default=1.25,
                    help="mark cells whose max/min across trials reaches this "
                         "(default 1.25)")
    args = ap.parse_args()
    max_spread = args.max_spread

    rows, tput, aborts, txns = load()
    # preserve first-appearance order
    benches, seen = [], set()
    for r in rows:
        if r["bench"] not in seen:
            seen.add(r["bench"])
            benches.append(r["bench"])
    thread_counts = sorted({int(r["threads"]) for r in rows})
    configs = [c for c in CONFIG_ORDER if any(r["config"] == c for r in rows)]
    trials = len({r["trial"] for r in rows})

    baseline = next((c for c in BASELINE if c in configs), None)

    out = []
    out.append(f"_Median of {trials} trials. Throughput in committed "
               f"transactions/second; higher is better. The small figure under "
               f"each cell is that cell's max/min across trials -- `!` marks "
               f"{max_spread:.2f}x or worse, where the run was too noisy for "
               f"the median to mean much._\n")

    # --- throughput -------------------------------------------------------
    out.append("\n## Throughput\n")
    ratio_head = (f"zstm vs {CONFIG_LABEL[baseline]}" if baseline
                  else "zstm vs RSTM")
    for b in benches:
        out.append(f"\n### {b}\n")
        out.append("| threads | " + " | ".join(CONFIG_LABEL[c] for c in configs) +
                   f" | {ratio_head} |")
        out.append("|---:|" + "---:|" * (len(configs) + 1))
        for p in thread_counts:
            cells = [fmt_cell(tput, (b, p, c), max_spread) for c in configs]
            z = med(tput, (b, p, "zstm-ala"))
            r = med(tput, (b, p, baseline)) if baseline else None
            ratio = f"{z / r:.2f}x" if z and r else "--"
            out.append(f"| {p} | " + " | ".join(cells) + f" | {ratio} |")

    # --- scaling ----------------------------------------------------------
    out.append("\n## Scaling (throughput relative to that config at 1 thread)\n")
    for b in benches:
        out.append(f"\n### {b}\n")
        out.append("| threads | " + " | ".join(CONFIG_LABEL[c] for c in configs) + " |")
        out.append("|---:|" + "---:|" * len(configs))
        for p in thread_counts:
            cells = []
            for c in configs:
                v, base = med(tput, (b, p, c)), med(tput, (b, 1, c))
                cells.append(f"{v / base:.2f}x" if v and base else "--")
            out.append(f"| {p} | " + " | ".join(cells) + " |")

    # --- aborts -----------------------------------------------------------
    out.append("\n## Abort rate (aborts per committed transaction)\n")
    out.append("_RSTM CGL is a single global lock and never aborts._\n")
    for b in benches:
        out.append(f"\n### {b}\n")
        out.append("| threads | " + " | ".join(CONFIG_LABEL[c] for c in configs) + " |")
        out.append("|---:|" + "---:|" * len(configs))
        for p in thread_counts:
            cells = []
            for c in configs:
                a, t = med(aborts, (b, p, c)), med(txns, (b, p, c))
                cells.append(f"{a / t:.3f}" if t else "--")
            out.append(f"| {p} | " + " | ".join(cells) + " |")

    # --- spread -----------------------------------------------------------
    out.append("\n## Measurement spread\n")
    flagged = []
    for b in benches:
        for p in thread_counts:
            for c in configs:
                s = spread(tput, (b, p, c))
                if s is not None and s >= max_spread:
                    flagged.append((s, b, p, c))
    flagged.sort(reverse=True)

    total = sum(1 for b in benches for p in thread_counts for c in configs
                if spread(tput, (b, p, c)) is not None)
    if not flagged:
        out.append(f"_No cell reached {max_spread:.2f}x max/min across "
                   f"{trials} trials._\n")
    else:
        out.append(f"_{len(flagged)} of {total} cells reached "
                   f"{max_spread:.2f}x max/min across {trials} trials and are "
                   f"marked `!` above. Differences at or below a cell's own "
                   f"spread are not results._\n")
        out.append("| spread | workload | threads | config |")
        out.append("|---:|---|---:|---|")
        for s, b, p, c in flagged:
            out.append(f"| {s:.2f}x | {b} | {p} | {CONFIG_LABEL[c]} |")

    text = "\n".join(out) + "\n"
    OUT.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
