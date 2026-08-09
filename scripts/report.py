#!/usr/bin/env python3
"""
Turn results/raw.csv into markdown tables (results/tables.md).

Each cell is the median across trials -- medians rather than means because a
single descheduled run on a shared VM skews a mean badly.
"""

import collections
import csv
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "results" / "raw.csv"
OUT = ROOT / "results" / "tables.md"

CONFIG_ORDER = ["zstm-ala", "rstm-word-norec", "rstm-int-norec", "rstm-word-cgl"]
CONFIG_LABEL = {
    "zstm-ala": "zstm (ALA)",
    "rstm-word-norec": "RSTM NOrec (word)",
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


def fmt(n):
    return f"{n:,.0f}" if n is not None else "--"


def main():
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

    out = []
    out.append(f"_Median of {trials} trials. Throughput in committed "
               f"transactions/second; higher is better._\n")

    # --- throughput -------------------------------------------------------
    out.append("\n## Throughput\n")
    for b in benches:
        out.append(f"\n### {b}\n")
        out.append("| threads | " + " | ".join(CONFIG_LABEL[c] for c in configs) +
                   " | zstm vs RSTM NOrec (word) |")
        out.append("|---:|" + "---:|" * (len(configs) + 1))
        for p in thread_counts:
            cells = [fmt(med(tput, (b, p, c))) for c in configs]
            z = med(tput, (b, p, "zstm-ala"))
            r = med(tput, (b, p, "rstm-word-norec"))
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
    out.append("_Max/min throughput across trials, worst cell per config. "
               "A large spread means the box was noisy and small differences "
               "should not be read as real._\n")
    out.append("| config | worst spread | where |")
    out.append("|---|---:|---|")
    for c in configs:
        worst, where = 1.0, ""
        for b in benches:
            for p in thread_counts:
                vals = tput.get((b, p, c))
                if vals and len(vals) > 1 and min(vals) > 0:
                    s = max(vals) / min(vals)
                    if s > worst:
                        worst, where = s, f"{b} p={p}"
        out.append(f"| {CONFIG_LABEL[c]} | {worst:.2f}x | {where or '--'} |")

    text = "\n".join(out) + "\n"
    OUT.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
