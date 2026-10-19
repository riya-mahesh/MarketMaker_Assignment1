# This file was generated with the help of Claude Code.
#
# Runs both builds on every scenario, interleaved, and reports two timings:
#
#   tick-to-trade  per order: the capture tap's Send time minus the tap's entry
#                  time for the delivery that triggered it.
#   handler time   per market data message and execution report: the app's
#                  completion time (latency_log.csv) minus the tap's entry time.
#                  Most failed risk checks happen on messages that send no
#                  order, so their cost shows up here rather than in
#                  tick-to-trade.
#
# Usage: python3 -I measure.py <build dir with both binaries> <runs>
import csv
import statistics
import subprocess
import sys
from pathlib import Path

VERSIONS = ["baseline", "cook_flags"]
LABELS = {"baseline": "Exceptions (baseline)", "cook_flags": "Error flags (fix)"}


def timings(run_dir):
    completed = {}
    with open(run_dir / "latency_log.csv") as f:
        for row in csv.DictReader(f):
            completed[(row["kind"], row["key"])] = int(row["completed_ns"])
    entry, tick_to_trade, handler = {}, [], []
    with open(run_dir / "capture.csv") as f:
        for row in csv.DictReader(f):
            if row["record"] == "delivery":
                entry[row["delivery"]] = int(row["wall_ns"])
                if row["kind"] in ("md", "report"):
                    handler.append(completed[(row["kind"], row["seq"])] - int(row["wall_ns"]))
            else:
                tick_to_trade.append(int(row["wall_ns"]) - entry[row["delivery"]])
    return tick_to_trade, handler


def main():
    out, runs = Path(sys.argv[1]), int(sys.argv[2])
    scenarios = sorted(Path("sim/fixtures").glob("*.scn"))
    t2t = {(v, s.stem): [] for v in VERSIONS for s in scenarios}
    handler = {(v, s.stem): [] for v in VERSIONS for s in scenarios}
    orders_match = {(v, s.stem): True for v in VERSIONS for s in scenarios}

    for _ in range(runs):
        for scn in scenarios:
            for v in VERSIONS:  # alternate versions so background load affects both alike
                run_dir = out / v / scn.stem
                subprocess.run([str(out / f"market_maker_{v}"), str(scn), "--out", str(run_dir)],
                               check=True, capture_output=True)
                expected = scn.with_suffix(".expected").read_text()
                orders_match[(v, scn.stem)] &= (run_dir / "orders.txt").read_text() == expected
                a, b = timings(run_dir)
                t2t[(v, scn.stem)] += a
                handler[(v, scn.stem)] += b

    def cells(values):
        return f"{statistics.mean(values):,.0f} | {statistics.median(values):,.0f}"

    def table(title, data, unit_label):
        print(f"\n{title}\n")
        heads = " | ".join(f"{LABELS[v]}: mean | {LABELS[v]}: median" for v in VERSIONS)
        print(f"| Scenario | {unit_label} per run | Same orders as .expected | {heads} |")
        print("|---|---|---|" + "---|" * (2 * len(VERSIONS)))
        for scn in scenarios:
            s = scn.stem
            same = "yes" if all(orders_match[(v, s)] for v in VERSIONS) else "NO"
            row = " | ".join(cells(data[(v, s)]) for v in VERSIONS)
            print(f"| {s} | {len(data[('baseline', s)]) // runs} | {same} | {row} |")

    print(f"Times in ns, over {runs} runs of each version.")
    table("Tick-to-trade per order", t2t, "Orders")
    table("Handler time per market data message and execution report", handler, "Messages")


if __name__ == "__main__":
    main()
