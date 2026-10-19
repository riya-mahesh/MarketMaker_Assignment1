# This file was generated with the help of Claude Code.
#
# Runs build/market_maker many times per scenario and measures the two flaws in the
# original latency report (app/evaluation/analysis.h) and its correction
# (app/experiments/evaluation/analysis_corrected.h):
#
#   Flaw 1  One end time per delivery. For each delivery that sends two orders (a bid
#           and an ask), compares the original's single sample (handler end minus
#           arrival) with each order's own tick-to-trade (its Send minus arrival).
#   Flaw 2  Non-trading deliveries averaged in. Counts, per run, the deliveries the
#           original averages: timer ticks, market data and execution reports that
#           send no order, and those that do.
#   Fix     The original's samples (every delivery's handler end minus arrival) vs. the
#           corrected samples (every order's Send minus its triggering arrival).
#
# All times come from capture.csv (the simulator's tap) except the handler end, which
# is the app's own latency_log.csv. Statistics are mean, median and sample std dev.
#
# Usage: python3 -I measure.py <output dir> <runs>
import csv
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def stats(values):
    if not values:
        return "– | – | –"
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{statistics.mean(values):,.0f} | {statistics.median(values):,.0f} | {sd:,.0f}"


def deliveries(run_dir):
    """One dict per delivery: kind, entry, handler end, and the wall times of its sends."""
    completed = {}
    with open(run_dir / "latency_log.csv") as f:
        for row in csv.DictReader(f):
            completed[(row["kind"], row["key"])] = int(row["completed_ns"])
    out = {}
    with open(run_dir / "capture.csv") as f:
        for row in csv.DictReader(f):
            if row["record"] == "delivery":
                key = row["sim_time_ns"] if row["kind"] == "timer" else row["seq"]
                out[row["delivery"]] = {"kind": row["kind"], "entry": int(row["wall_ns"]),
                                        "end": completed[(row["kind"], key)], "sends": []}
            else:
                out[row["delivery"]]["sends"].append(int(row["wall_ns"]))
    return list(out.values())


def main():
    out, runs = Path(sys.argv[1]), int(sys.argv[2])
    scenarios = sorted(Path("sim/fixtures").glob("*.scn"))
    counts = {}                      # scenario -> per-run delivery counts (identical every run)
    two = defaultdict(lambda: {"handler": [], "first": [], "second": [], "n": 0})
    original = defaultdict(list)
    corrected = defaultdict(list)

    for _ in range(runs):
        for scn in scenarios:
            s = scn.stem
            run_dir = out / s
            subprocess.run(["build/market_maker", str(scn), "--out", str(run_dir)],
                           check=True, capture_output=True)
            ds = deliveries(run_dir)
            counts[s] = {
                "all": len(ds),
                "timer": sum(d["kind"] == "timer" and not d["sends"] for d in ds),
                "no_order": sum(d["kind"] != "timer" and not d["sends"] for d in ds),
                "sent": sum(bool(d["sends"]) for d in ds),
                "orders": sum(len(d["sends"]) for d in ds),
            }
            for d in ds:
                original[s].append(d["end"] - d["entry"])
                corrected[s] += [t - d["entry"] for t in d["sends"]]
                if len(d["sends"]) == 2:
                    two[s]["handler"].append(d["end"] - d["entry"])
                    two[s]["first"].append(d["sends"][0] - d["entry"])
                    two[s]["second"].append(d["sends"][1] - d["entry"])
                    two[s]["n"] += 1

    print(f"Times in ns. Statistics are over the individual samples (orders or deliveries) of {runs} run(s) per scenario.\n")

    print("Flaw 2: what the original report averages, per run\n")
    print("| Scenario | Samples averaged | Timer ticks | Messages/reports with no order "
          "| Messages/reports that sent orders | Orders sent |")
    print("|---|---|---|---|---|---|")
    for scn in scenarios:
        c = counts[scn.stem]
        print(f"| {scn.stem} | {c['all']} | {c['timer']} | {c['no_order']} | {c['sent']} | {c['orders']} |")

    print("\nFlaw 1: deliveries that send two orders (bid, then ask); times from the delivery's arrival\n")
    print("| Scenario | Deliveries with 2 orders, per run | Bid sent: mean | median | std dev "
          "| Ask sent: mean | median | std dev | Handler finished (original report): mean | median | std dev |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for scn in scenarios:
        t = two[scn.stem]
        if t["n"]:
            print(f"| {scn.stem} | {t['n'] // runs} | {stats(t['first'])} "
                  f"| {stats(t['second'])} | {stats(t['handler'])} |")

    print("\nFix: original samples vs. corrected (per-order) samples\n")
    print("| Scenario | Original: samples per run | mean | median | std dev "
          "| Corrected: orders per run | mean | median | std dev |")
    print("|---|---|---|---|---|---|---|---|---|")
    for scn in scenarios:
        s = scn.stem
        print(f"| {s} | {len(original[s]) // runs} | {stats(original[s])} "
              f"| {len(corrected[s]) // runs} | {stats(corrected[s])} |")


if __name__ == "__main__":
    main()
