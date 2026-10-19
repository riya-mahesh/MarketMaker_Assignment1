#!/bin/sh
# Cached top of book vs. full ladder scan, on every scenario in sim/fixtures/.
#
# Builds two versions of build/market_maker that differ only in app/market_data/book.{h,cpp}:
#   stored_top  the app as it is (build/market_maker, built by make)
#   full_scan   the same app linked with full_scan/app/market_data/book.{h,cpp}
# then runs measure.py, which checks both send exactly the .expected orders and
# reports mean, median and standard deviation of tick-to-trade per scenario.
# A copy of the table goes to build/experiments/top_of_book/results.md.
#
#   sh app/experiments/top_of_book/run.sh            # one run per version per scenario (RUNS=n for more)
#   RUNS=10 sh app/experiments/top_of_book/run.sh  # statistics over the orders of 10 runs
set -e
cd "$(dirname "$0")/../../.."

EXP=app/experiments/top_of_book
OUT=build/experiments/top_of_book
mkdir -p "$OUT"

make build/market_maker
cp build/market_maker "$OUT/market_maker_stored_top"

${CXX:-c++} -std=c++20 -O2 -g -Wall -Wextra -Wpedantic -I "$EXP/full_scan" -I . \
    app/main.cpp app/market_maker.cpp app/execution/orders.cpp \
    "$EXP/full_scan/app/market_data/book.cpp" build/libsim.a \
    -o "$OUT/market_maker_full_scan"

python3 -I "$EXP/measure.py" "$OUT" "${RUNS:-1}" | tee "$OUT/results.md"
