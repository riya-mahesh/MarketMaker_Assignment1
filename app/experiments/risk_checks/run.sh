#!/bin/sh
# Risk checks that throw (the app as it is) vs. Cook's error-flags fix.
#
# Builds two versions of build/market_maker:
#   baseline    the app as it is (build/market_maker, built by make)
#   cook_flags  Cook's "slowpath removal": all checks in one flags word, one branch,
#               and an out-of-line handler for the rare cases
# then runs measure.py, which checks both send exactly the .expected orders
# and reports mean, median and standard deviation of tick-to-trade and handler
# time per scenario. A copy of the tables goes to build/experiments/risk_checks/results.md.
#
#   sh app/experiments/risk_checks/run.sh            # 30 runs per version per scenario
#   RUNS=10 sh app/experiments/risk_checks/run.sh
set -e
cd "$(dirname "$0")/../../.."

EXP=app/experiments/risk_checks
OUT=build/experiments/risk_checks
mkdir -p "$OUT"

make build/market_maker
cp build/market_maker "$OUT/market_maker_baseline"

for v in cook_flags; do
    ${CXX:-c++} -std=c++20 -O2 -g -Wall -Wextra -Wpedantic -I "$EXP/$v" -I . \
        app/main.cpp "$EXP/$v/app/market_maker.cpp" app/execution/orders.cpp \
        app/market_data/book.cpp build/libsim.a \
        -o "$OUT/market_maker_$v"
done

python3 -I "$EXP/measure.py" "$OUT" "${RUNS:-30}" | tee "$OUT/results.md"
