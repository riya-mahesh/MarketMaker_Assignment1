# This file was generated with the help of Claude Code.
#
# Runs both builds on every scenario, interleaved, and reports tick-to-trade.
#
# Tick-to-trade for one order = the capture tap's Send time minus the tap's
# entry time for the delivery that triggered it (both from capture.csv, written
# by the simulator, outside the app). Every order sent counts once.
#
# Usage: python3 -I measure.py <build dir with both binaries> <runs>
import csv
import statistics
import subprocess
import sys
from pathlib import Path

VERSIONS = ["stored_top", "full_scan"]


def tick_to_trade(capture_csv):
    entry = {}
    latencies = []
    with open(capture_csv) as f:
        for row in csv.DictReader(f):
            if row["record"] == "delivery":
                entry[row["delivery"]] = int(row["wall_ns"])
            else:
                latencies.append(int(row["wall_ns"]) - entry[row["delivery"]])
    return latencies


def main():
    out, runs = Path(sys.argv[1]), int(sys.argv[2])
    scenarios = sorted(Path("sim/fixtures").glob("*.scn"))
    results = {(v, s.stem): [] for v in VERSIONS for s in scenarios}
    orders_match = {(v, s.stem): True for v in VERSIONS for s in scenarios}

    for _ in range(runs):
        for scn in scenarios:
            for v in VERSIONS:  # alternate versions so background load affects both alike
                run_dir = out / v / scn.stem
                subprocess.run([str(out / f"market_maker_{v}"), str(scn), "--out", str(run_dir)],
                               check=True, capture_output=True)
                expected = scn.with_suffix(".expected").read_text()
                orders_match[(v, scn.stem)] &= (run_dir / "orders.txt").read_text() == expected
                results[(v, scn.stem)] += tick_to_trade(run_dir / "capture.csv")

    def cells(values):
        sd = statistics.stdev(values) if len(values) > 1 else 0.0
        return f"{statistics.mean(values):,.0f} | {statistics.median(values):,.0f} | {sd:,.0f}"

    print(f"Tick-to-trade per order, in ns, over {runs} runs of each version.\n")
    print("| Scenario | Orders per run | Same orders as .expected (stored top / full scan) "
          "| Stored top: mean | Stored top: median | Stored top: std dev "
          "| Full scan: mean | Full scan: median | Full scan: std dev |")
    print("|---|---|---|---|---|---|---|---|---|")
    for scn in scenarios:
        s = scn.stem
        same = " / ".join("yes" if orders_match[(v, s)] else "NO" for v in VERSIONS)
        print(f"| {s} | {len(results[('stored_top', s)]) // runs} | {same} "
              f"| {cells(results[('stored_top', s)])} | {cells(results[('full_scan', s)])} |")
    all_stored = [x for s in scenarios for x in results[("stored_top", s.stem)]]
    all_full = [x for s in scenarios for x in results[("full_scan", s.stem)]]
    print(f"| **All scenarios** | {len(all_stored) // runs} | "
          f"{'yes / yes' if all(orders_match.values()) else 'NO'} "
          f"| **{cells(all_stored).replace(' | ', '** | **')}** "
          f"| **{cells(all_full).replace(' | ', '** | **')}** |")


if __name__ == "__main__":
    main()
