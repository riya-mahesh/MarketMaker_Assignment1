# This file was generated with the help of Claude Code.
#
# Runs the instrumented build on every scenario and summarizes its THROW lines:
#   THROW <type> <action> <ns from just before `throw` to the start of the catch>
#
# Usage: python3 -I throws.py <build dir> <runs>
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def main():
    out, runs = Path(sys.argv[1]), int(sys.argv[2])
    scenarios = sorted(Path("sim/fixtures").glob("*.scn"))
    rows = []  # (scenario, {(type, action): [ns ...]}, [first-throw ns ...])
    per_run_totals = {}  # scenario -> one list of throw times per run
    for scn in scenarios:
        times = defaultdict(list)
        first = []
        per_run_totals[scn.stem] = []
        for _ in range(runs):
            p = subprocess.run([str(out / "market_maker_instrumented"), str(scn), "--out",
                                str(out / "instrumented" / scn.stem)],
                               check=True, capture_output=True, text=True)
            throws = [line.split() for line in p.stderr.splitlines() if line.startswith("THROW ")]
            per_run_totals[scn.stem].append([int(ns) for (_, _, _, ns) in throws])
            for i, (_, kind, action, ns) in enumerate(throws):
                (first if i == 0 else times[(kind, action)]).append(int(ns))
        rows.append((scn.stem, times, first))

    def cells(values):
        sd = statistics.stdev(values) if len(values) > 1 else 0.0
        return f"{statistics.mean(values):,.0f} | {statistics.median(values):,.0f} | {sd:,.0f}"

    print(f"Risk-check exceptions: how many per run, and the time from just before `throw` to\n"
          f"the start of the matching catch, in ns, over {runs} runs. The first throw of each\n"
          f"run is listed separately because it is much slower (the runtime loads its\n"
          f"unwinding tables).\n")
    print("| Scenario | Exception | What the catch does | Throws per run | Mean | Median | Std dev |")
    print("|---|---|---|---|---|---|---|")
    for name, times, first in rows:
        if first:
            print(f"| {name} | (first throw of the run) | | 1 | {cells(first)} |")
        for (kind, action), ns in sorted(times.items()):
            print(f"| {name} | {kind} | {action.replace('_', ' ')} | {len(ns) // runs} | {cells(ns)} |")
    print("\nCost of one throw by type, all scenarios together, in ns:\n")
    print("| Throw | What the catch does | Throws | Mean | Median | Std dev |")
    print("|---|---|---|---|---|---|")
    first_all = [x for _, _, first in rows for x in first]
    print(f"| first throw of the run | | {len(first_all)} | {cells(first_all)} |")
    by_type = defaultdict(list)
    for _, times, _ in rows:
        for key, ns in times.items():
            by_type[key] += ns
    for (kind, action), ns in sorted(by_type.items()):
        print(f"| {kind} | {action.replace('_', ' ')} | {len(ns)} | {cells(ns)} |")
    print("\nTime spent throwing in one run, in ns:\n")
    print("| Scenario | Throws per run | Mean | Median | Std dev |")
    print("|---|---|---|---|---|")
    for name, times, first in rows:
        per_run = (sum(len(v) for v in times.values()) + len(first)) // runs
        totals = [sum(t) for t in per_run_totals[name]]
        print(f"| {name} | {per_run} | {cells(totals)} |")

if __name__ == "__main__":
    main()
