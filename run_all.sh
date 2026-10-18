#!/bin/sh
# Runs every scenario in sim/fixtures/ and collects all outputs in build/out/<name>/:
#   capture.csv, latency_log.csv, orders.txt, decisions.log, trace.txt, report.txt
#
# trace.txt comes from a separate --trace run first (it only contains simulated
# time, so it is identical across runs); the second, untraced run then writes
# the CSVs and logs, so their latency numbers aren't slowed down by tracing.
#
#   sh run_all.sh
set -e
cd "$(dirname "$0")"

make build/market_maker

rm -rf build/out
for scn in sim/fixtures/*.scn; do
    name=$(basename "$scn" .scn)
    dir=build/out/$name
    ./build/market_maker "$scn" --out "$dir" --trace > /dev/null
    ./build/market_maker "$scn" --out "$dir" > "$dir/report.txt"
    if [ -f "sim/fixtures/$name.expected" ] && diff -q "sim/fixtures/$name.expected" "$dir/orders.txt" > /dev/null; then
        check="orders match .expected"
    else
        check="ORDERS DIFFER from .expected"
    fi
    printf '%-11s %-24s %s\n' "$name" "$(tr '\n' ' ' < "$dir/report.txt")" "$check"
done
