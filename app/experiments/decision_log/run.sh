#!/bin/sh
# Decision log formatted with fprintf before every Send (the app as it is) vs. the
# same log recorded as a binary entry and formatted at shutdown (deferred/).
#
# Builds four versions of build/market_maker:
#   baseline           the app as it is
#   deferred           the app with deferred/app/execution/decision_log.h
#   timed_baseline     baseline + timed/app/execution/orders.cpp (times each log write)
#   timed_deferred     deferred + timed/app/execution/orders.cpp
# then runs measure.py, which checks that both versions send exactly the .expected orders
# and write identical decisions.log files, and reports the cost of one log write and the
# tick-to-trade of every order. A copy of the tables goes to
# build/experiments/decision_log/results.md.
#
#   sh app/experiments/decision_log/run.sh            # one run per version per scenario
#   RUNS=10 sh app/experiments/decision_log/run.sh  # the orders of 10 runs
set -e
cd "$(dirname "$0")/../../.."

EXP=app/experiments/decision_log
OUT=build/experiments/decision_log
mkdir -p "$OUT"
CXXFLAGS="-std=c++20 -O2 -g -Wall -Wextra -Wpedantic"

make build/market_maker
cp build/market_maker "$OUT/market_maker_baseline"

${CXX:-c++} $CXXFLAGS -I "$EXP/deferred" -I . \
    app/main.cpp app/market_maker.cpp app/execution/orders.cpp app/market_data/book.cpp \
    build/libsim.a -o "$OUT/market_maker_deferred"

${CXX:-c++} $CXXFLAGS -I . \
    app/main.cpp app/market_maker.cpp "$EXP/timed/app/execution/orders.cpp" app/market_data/book.cpp \
    build/libsim.a -o "$OUT/market_maker_timed_baseline"

${CXX:-c++} $CXXFLAGS -I "$EXP/deferred" -I . \
    app/main.cpp app/market_maker.cpp "$EXP/timed/app/execution/orders.cpp" app/market_data/book.cpp \
    build/libsim.a -o "$OUT/market_maker_timed_deferred"

python3 -I "$EXP/measure.py" "$OUT" "${RUNS:-1}" | tee "$OUT/results.md"
