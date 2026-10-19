# This file was generated with the help of Claude Code.
#
# Collects, over many runs of build/market_maker, the samples behind each report:
#
#   original   analysis.h's per-delivery latency: the app's completion time
#              (latency_log.csv) minus the tap's entry time, for every delivery
#              (market data, execution reports and timer ticks).
#   corrected  analysis_corrected.h's tick-to-trade: the tap's Send time minus the
#              tap's entry time of the triggering delivery, for every order.
#
# Usage: python3 -I measure.py <output dir> <runs>
import csv
import statistics
import subprocess
import sys
from pathlib import Path


def stats(values):
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{statistics.mean(values):,.0f} | {statistics.median(values):,.0f} | {sd:,.0f}"


def samples(run_dir):
    completed = {}
    with open(run_dir / "latency_log.csv") as f:
        for row in csv.DictReader(f):
            completed[(row["kind"], row["key"])] = int(row["completed_ns"])
    entry, original, corrected = {}, [], []
    with open(run_dir / "capture.csv") as f:
        for row in csv.DictReader(f):
            if row["record"] == "delivery":
                entry[row["delivery"]] = int(row["wall_ns"])
                key = row["sim_time_ns"] if row["kind"] == "timer" else row["seq"]
                original.append(completed[(row["kind"], key)] - int(row["wall_ns"]))
            else:
                corrected.append(int(row["wall_ns"]) - entry[row["delivery"]])
    return original, corrected


def main():
    out, runs = Path(sys.argv[1]), int(sys.argv[2])
    scenarios = sorted(Path("sim/fixtures").glob("*.scn"))
    original = {s.stem: [] for s in scenarios}
    corrected = {s.stem: [] for s in scenarios}
    for _ in range(runs):
        for scn in scenarios:
            run_dir = out / scn.stem
            subprocess.run(["build/market_maker", str(scn), "--out", str(run_dir)],
                           check=True, capture_output=True)
            a, b = samples(run_dir)
            original[scn.stem] += a
            corrected[scn.stem] += b

    print(f"Times in ns, pooled over {runs} runs per scenario.\n")
    print("| Scenario | Original: samples per run | Original: mean | Original: median | Original: std dev "
          "| Corrected: orders per run | Corrected: mean | Corrected: median | Corrected: std dev |")
    print("|---|---|---|---|---|---|---|---|---|")
    for scn in scenarios:
        s = scn.stem
        print(f"| {s} | {len(original[s]) // runs} | {stats(original[s])} "
              f"| {len(corrected[s]) // runs} | {stats(corrected[s])} |")


if __name__ == "__main__":
    main()
