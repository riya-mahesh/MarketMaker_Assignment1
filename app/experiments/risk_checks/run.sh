#!/bin/sh
# Risk checks that throw (the app as it is) vs. two fixes.
#
# Builds three versions of build/market_maker:
#   baseline      the app as it is (build/market_maker, built by make)
#   return_codes  checks return a [[nodiscard]] result; Requote()/QuoteSide() test it
#   cook_flags    Cook's "slowpath removal": all checks in one flags word, one branch,
#                 and an out-of-line handler for the rare cases
# then runs measure.py, which checks all three send exactly the .expected orders
# and reports mean and median tick-to-trade and handler time per scenario.
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

for v in return_codes cook_flags; do
    ${CXX:-c++} -std=c++20 -O2 -g -Wall -Wextra -Wpedantic -I "$EXP/$v" -I . \
        app/main.cpp "$EXP/$v/app/market_maker.cpp" app/execution/orders.cpp \
        app/market_data/book.cpp build/libsim.a \
        -o "$OUT/market_maker_$v"
done

python3 -I "$EXP/measure.py" "$OUT" "${RUNS:-30}" | tee "$EXP/results.md"
