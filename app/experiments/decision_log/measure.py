# This file was generated with the help of Claude Code.
#
# Decision log before Send: fprintf (baseline) vs. a binary record formatted at shutdown
# (deferred). Reports, per scenario:
#
#   log write  the time of one log_.Record() call, from the timed builds (a clock read just
#              before and just after the call).
#   tick-to-trade  per order, from the untimed builds: the capture tap's Send time minus
#              the tap's entry time of the delivery that triggered it.
#
# Also checks that both versions send exactly the .expected orders and write identical
# decisions.log files. Statistics (mean, median, sample std dev) are over the log writes,
# or the orders, of the run(s).
#
# Usage: python3 -I measure.py <build dir> <runs>
import csv
import statistics
import subprocess
import sys
from pathlib import Path

VERSIONS = {"baseline": "fprintf before Send", "deferred": "Binary record, formatted at shutdown"}


def stats(values):
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{statistics.mean(values):,.0f} | {statistics.median(values):,.0f} | {sd:,.0f}"


def run(binary, scn, out_dir):
    p = subprocess.run([str(binary), str(scn), "--out", str(out_dir)],
                       check=True, capture_output=True, text=True)
    if (out_dir / "orders.txt").read_text() != scn.with_suffix(".expected").read_text():
        sys.exit(f"{binary.name} on {scn.stem}: orders differ from .expected")
    return p.stderr


def tick_to_trade(out_dir):
    entry, latencies = {}, []
    with open(out_dir / "capture.csv") as f:
        for row in csv.DictReader(f):
            if row["record"] == "delivery":
                entry[row["delivery"]] = int(row["wall_ns"])
            else:
                latencies.append(int(row["wall_ns"]) - entry[row["delivery"]])
    return latencies


def main():
    out, runs = Path(sys.argv[1]), int(sys.argv[2])
    scenarios = sorted(Path("sim/fixtures").glob("*.scn"))
    writes = {(v, s.stem): [] for v in VERSIONS for s in scenarios}
    t2t = {(v, s.stem): [] for v in VERSIONS for s in scenarios}
    same_log = {s.stem: True for s in scenarios}
    for _ in range(runs):
        for scn in scenarios:
            for v in VERSIONS:  # alternate versions so background load affects both alike
                d = out / v / scn.stem
                run(out / f"market_maker_{v}", scn, d)
                t2t[(v, scn.stem)] += tick_to_trade(d)
                stderr = run(out / f"market_maker_timed_{v}", scn, out / f"timed_{v}" / scn.stem)
                writes[(v, scn.stem)] += [int(l.split()[1]) for l in stderr.splitlines() if l.startswith("LOG ")]
            same_log[scn.stem] &= ((out / "baseline" / scn.stem / "decisions.log").read_bytes()
                                   == (out / "deferred" / scn.stem / "decisions.log").read_bytes())

    a, b = VERSIONS["baseline"], VERSIONS["deferred"]
    print(f"Times in ns; statistics over the log writes or orders of {runs} run(s) per version.")
    print("Both versions send exactly the .expected orders in every scenario.\n")
    print("Cost of one decision-log write (log_.Record), per order:\n")
    print(f"| Scenario | Writes | {a}: mean | Median | Std dev | {b}: mean | Median | Std dev |")
    print("|---|---|---|---|---|---|---|---|")
    for scn in scenarios:
        s = scn.stem
        print(f"| {s} | {len(writes[('baseline', s)]) // runs} | {stats(writes[('baseline', s)])} "
              f"| {stats(writes[('deferred', s)])} |")
    print("\nTick-to-trade per order:\n")
    print(f"| Scenario | Orders | decisions.log identical | {a}: mean | Median | Std dev "
          f"| {b}: mean | Median | Std dev | Median faster by |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for scn in scenarios:
        s = scn.stem
        base, fix = t2t[("baseline", s)], t2t[("deferred", s)]
        ratio = statistics.median(base) / statistics.median(fix)
        print(f"| {s} | {len(base) // runs} | {'yes' if same_log[s] else 'NO'} | {stats(base)} "
              f"| {stats(fix)} | {ratio:.1f}× |")
    all_base = [x for s in scenarios for x in t2t[("baseline", s.stem)]]
    all_fix = [x for s in scenarios for x in t2t[("deferred", s.stem)]]
    print(f"| **All scenarios** | {len(all_base) // runs} | {'yes' if all(same_log.values()) else 'NO'} "
          f"| {stats(all_base)} | {stats(all_fix)} "
          f"| {statistics.median(all_base) / statistics.median(all_fix):.1f}× |")


if __name__ == "__main__":
    main()
