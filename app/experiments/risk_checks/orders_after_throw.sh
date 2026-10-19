#!/bin/sh
# Tick-to-trade of the orders that are sent after a risk-check throw in the same handler
# (the direct hot-path cost of an exception), exceptions vs. error flags.
#
# Builds three versions of build/market_maker:
#   labeler      instrumented/ (risk.h, market_maker.cpp, execution/orders.cpp): prints one
#                SEND line per order saying whether a check threw earlier in that handler.
#                Used only to label orders, never to time them.
#   baseline     the app as it is (exceptions)
#   error_flags  the app with error_flags/ (no exceptions)
# then runs orders_after_throw.py. Both timed versions send the same orders in the same
# sequence, so the labels from the labeler apply to them order by order.
# A copy of the tables goes to build/experiments/risk_checks/orders_after_throw.md.
#
#   sh app/experiments/risk_checks/orders_after_throw.sh          # one run per scenario
#   RUNS=10 sh app/experiments/risk_checks/orders_after_throw.sh  # orders of 10 runs
set -e
cd "$(dirname "$0")/../../.."

EXP=app/experiments/risk_checks
OUT=build/experiments/risk_checks
mkdir -p "$OUT"
CXXFLAGS="-std=c++20 -O2 -g -Wall -Wextra -Wpedantic"

make build/market_maker
cp build/market_maker "$OUT/market_maker_baseline"

${CXX:-c++} $CXXFLAGS -I "$EXP/instrumented" -I . \
    app/main.cpp "$EXP/instrumented/app/market_maker.cpp" "$EXP/instrumented/app/execution/orders.cpp" \
    app/market_data/book.cpp build/libsim.a -o "$OUT/market_maker_labeler"

${CXX:-c++} $CXXFLAGS -I "$EXP/error_flags" -I . \
    app/main.cpp "$EXP/error_flags/app/market_maker.cpp" app/execution/orders.cpp \
    app/market_data/book.cpp build/libsim.a -o "$OUT/market_maker_error_flags"

python3 -I "$EXP/orders_after_throw.py" "$OUT" "${RUNS:-1}" | tee "$OUT/orders_after_throw.md"
