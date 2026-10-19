#!/bin/sh
# Original latency report (app/evaluation/analysis.h) vs. corrected tick-to-trade
# (app/experiments/analysis_corrected.h), on every scenario in sim/fixtures/.
#
# Builds build/market_maker and runs measure.py, which collects, over RUNS runs
# per scenario, the samples each report summarizes and prints their mean,
# median and standard deviation. A copy of the tables goes to
# build/experiments/evaluation/results.md.
#
#   sh app/experiments/evaluation/run.sh            # 30 runs per scenario
#   RUNS=10 sh app/experiments/evaluation/run.sh
set -e
cd "$(dirname "$0")/../../.."

OUT=build/experiments/evaluation
mkdir -p "$OUT"
make build/market_maker
python3 -I app/experiments/evaluation/measure.py "$OUT" "${RUNS:-30}" | tee "$OUT/results.md"
