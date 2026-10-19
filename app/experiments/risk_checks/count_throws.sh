#!/bin/sh
# Counts and times every risk-check exception in every scenario.
#
# Builds build/market_maker with instrumented/app/risk/risk.h and
# instrumented/app/market_maker.cpp, which report each throw (its type, what the
# catch did with it, and the time from just before `throw` to the start of the
# catch), then runs each scenario RUNS times and summarizes with throws.py.
# A copy of the tables goes to build/experiments/risk_checks/throws.md.
#
#   sh app/experiments/risk_checks/count_throws.sh          # one run per scenario (RUNS=n for more)
set -e
cd "$(dirname "$0")/../../.."

EXP=app/experiments/risk_checks
OUT=build/experiments/risk_checks
mkdir -p "$OUT"
make build/libsim.a

${CXX:-c++} -std=c++20 -O2 -g -Wall -Wextra -Wpedantic -I "$EXP/instrumented" -I . \
    app/main.cpp "$EXP/instrumented/app/market_maker.cpp" app/execution/orders.cpp \
    app/market_data/book.cpp build/libsim.a \
    -o "$OUT/market_maker_instrumented"

python3 -I "$EXP/throws.py" "$OUT" "${RUNS:-1}" | tee "$OUT/throws.md"
