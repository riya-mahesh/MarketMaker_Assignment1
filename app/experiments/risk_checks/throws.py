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
    rows = []  # (scenario, type, action, [ns ...], count per run)
    for scn in scenarios:
        times = defaultdict(list)
        first = []
        for _ in range(runs):
            p = subprocess.run([str(out / "market_maker_instrumented"), str(scn), "--out",
                                str(out / "instrumented" / scn.stem)],
                               check=True, capture_output=True, text=True)
            throws = [line.split() for line in p.stderr.splitlines() if line.startswith("THROW ")]
            for i, (_, kind, action, ns) in enumerate(throws):
                (first if i == 0 else times[(kind, action)]).append(int(ns))
        rows.append((scn.stem, times, first))

    print(f"Risk-check exceptions per run, and the time from just before `throw` to the start of\n"
          f"the matching catch, in ns, over {runs} runs. The first throw of each run is shown\n"
          f"separately because it is much slower (the runtime loads its unwinding tables).\n")
    print("| Scenario | Exception | What the catch does | Throws per run | Median ns per throw |")
    print("|---|---|---|---|---|")
    for name, times, first in rows:
        if first:
            print(f"| {name} | (first throw of the run) | | 1 | {statistics.median(first):,.0f} |")
        for (kind, action), ns in sorted(times.items()):
            print(f"| {name} | {kind} | {action.replace('_', ' ')} | {len(ns) // runs} "
                  f"| {statistics.median(ns):,.0f} |")
    print("\n| Scenario | Throws per run | Time spent in throws per run (mean ns) |")
    print("|---|---|---|")
    for name, times, first in rows:
        per_run = (sum(len(v) for v in times.values()) + len(first)) // runs
        total = (sum(sum(v) for v in times.values()) + sum(first)) / runs
        print(f"| {name} | {per_run} | {total:,.0f} |")


if __name__ == "__main__":
    main()
