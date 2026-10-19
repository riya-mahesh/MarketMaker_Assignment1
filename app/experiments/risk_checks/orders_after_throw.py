# This file was generated with the help of Claude Code.
#
# Splits every order into "sent after a risk-check throw in the same handler" or not
# (from the labeler build's SEND lines), then compares the tick-to-trade of each group
# between the exceptions build and the error-flags build.
#
# Tick-to-trade per order: the capture tap's Send time minus the tap's entry time of the
# delivery that triggered it (capture.csv). Statistics are over the orders of the run(s).
#
# Usage: python3 -I orders_after_throw.py <build dir> <runs>
import csv
import statistics
import subprocess
import sys
from pathlib import Path

TIMED = {"baseline": "Exceptions", "error_flags": "Error flags"}


def stats(values):
    if not values:
        return "– | – | –"
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{statistics.mean(values):,.0f} | {statistics.median(values):,.0f} | {sd:,.0f}"


def run(binary, scn, out_dir):
    p = subprocess.run([str(binary), str(scn), "--out", str(out_dir)],
                       check=True, capture_output=True, text=True)
    if (out_dir / "orders.txt").read_text() != scn.with_suffix(".expected").read_text():
        sys.exit(f"{binary.name} on {scn.stem}: orders differ from .expected")
    entry, latencies = {}, []
    with open(out_dir / "capture.csv") as f:
        for row in csv.DictReader(f):
            if row["record"] == "delivery":
                entry[row["delivery"]] = int(row["wall_ns"])
            else:
                latencies.append(int(row["wall_ns"]) - entry[row["delivery"]])
    return p.stderr, latencies


def main():
    out, runs = Path(sys.argv[1]), int(sys.argv[2])
    scenarios = sorted(Path("sim/fixtures").glob("*.scn"))
    rows = []
    for scn in scenarios:
        stderr, _ = run(out / "market_maker_labeler", scn, out / "labeler" / scn.stem)
        labels = [line.split()[1] == "1" for line in stderr.splitlines() if line.startswith("SEND ")]
        after = {v: [] for v in TIMED}
        other = {v: [] for v in TIMED}
        for _ in range(runs):
            for v in TIMED:
                _, lat = run(out / f"market_maker_{v}", scn, out / v / scn.stem)
                assert len(lat) == len(labels), f"{scn.stem}: {len(lat)} orders vs {len(labels)} labels"
                for is_after, l in zip(labels, lat):
                    (after if is_after else other)[v].append(l)
        rows.append((scn.stem, sum(labels), len(labels) - sum(labels), after, other))

    print(f"Tick-to-trade in ns; statistics over the orders of {runs} run(s) per version.\n")
    print("Orders sent after a risk-check throw in the same handler:\n")
    print("| Scenario | Such orders in the run | Exceptions: mean | Median | Std dev "
          "| Error flags: mean | Median | Std dev | Saved: mean | Saved: median |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for name, n_after, _, after, _ in rows:
        if n_after:
            saved_mean = statistics.mean(after["baseline"]) - statistics.mean(after["error_flags"])
            saved_median = statistics.median(after["baseline"]) - statistics.median(after["error_flags"])
            print(f"| {name} | {n_after} | {stats(after['baseline'])} | {stats(after['error_flags'])} "
                  f"| {saved_mean:,.0f} | {saved_median:,.0f} |")
    print("\nAll other orders (control: no throw before them in their handler):\n")
    print("| Scenario | Such orders in the run | Exceptions: mean | Median | Std dev "
          "| Error flags: mean | Median | Std dev |")
    print("|---|---|---|---|---|---|---|---|")
    for name, _, n_other, _, other in rows:
        print(f"| {name} | {n_other} | {stats(other['baseline'])} | {stats(other['error_flags'])} |")


if __name__ == "__main__":
    main()
