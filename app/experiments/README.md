# Experiments

Supporting measurements for the Assignment 1 critique. Nothing here changes what
the market maker trades: `make verify` passes with all of it in place.

| Path | What it is |
|---|---|
| `analysis_corrected.h` | Corrected latency report: tick-to-trade per order (printed after the original report by every run of `build/market_maker`) |
| `top_of_book/` | Experiment: cached top of book vs. scanning the price ladder for the best bid and ask |

## Corrected evaluation (`analysis_corrected.h`)

Tick-to-trade is measured per order, as defined by the STAC-T1 benchmark: *"the
egress time of the trade message minus the ingress time of the market data
message triggering the trade."* Both timestamps come from the simulator's capture
tap: the order's `Send` time, and the entry time of the delivery being handled
when it was sent.

It differs from the original report (`app/evaluation/analysis.h`) in two ways:

1. **End point.** Each order ends at its own `Send`, not when the handler returns.
   A delivery that sends a bid and an ask yields two latencies, not one.
2. **Which events count.** Only orders count. Deliveries that send nothing
   (ordinary timer ticks, messages that leave our quotes unchanged) are not
   averaged in. Orders sent from the timer (the loss-limit halt's cancels) are
   trading decisions, so they do count.

Each run prints, for example (`basic`):

```
messages: 54
average latency: 1194.44 ns                           <- original report
corrected tick-to-trade: 14 orders, mean 767.929 ns   <- corrected report
```

## Cached top of book vs. full ladder scan (`top_of_book/`)

**Decision tested (design doc §2.2.1, "Top of book").** The book keeps a cached
copy of the best bid and ask (`top_` in `app/market_data/book.cpp`), updated
whenever an order at or better than the best changes. `Requote()` reads it on
every market data message and execution report, before deciding whether to send
an order.

**Baseline.** `top_of_book/full_scan/app/market_data/book.{h,cpp}` is the app's
book with the cache removed: no `top_`, no `RecomputeBest`, and `top()` searches
the price ladder on every call. Bids are scanned from the top of the ladder
($2,000) down and asks from $0 up, each stopping at the first non-empty price
level. Everything else in the book, and the rest of the app, is unchanged.

**Method.**

- Two builds of `build/market_maker` that differ only in the book files.
- Every scenario in `sim/fixtures/`, 30 runs of each build, alternating builds
  so background load on the machine affects both alike.
- Correctness: every run's `orders.txt` is compared with the scenario's
  `.expected` file.
- Metric: tick-to-trade per order, from the capture tap (`capture.csv`), pooled
  over the 30 runs; mean and median reported.

**Run it.**

```sh
sh app/experiments/top_of_book/run.sh          # writes top_of_book/results.md
RUNS=10 sh app/experiments/top_of_book/run.sh  # fewer runs
```

**Results** (Apple M4 Pro, Apple clang 17, `-O2`; times vary from run to run).
Tick-to-trade per order, in ns, over 30 runs of each version:

| Scenario | Orders per run | Same orders as `.expected` (stored top / full scan) | Stored top: mean | Stored top: median | Full scan: mean | Full scan: median |
|---|---|---|---|---|---|---|
| basic | 14 | yes / yes | 695 | 291 | 50,985 | 51,333 |
| empty_side | 6 | yes / yes | 1,514 | 625 | 51,937 | 51,584 |
| gap | 4 | yes / yes | 3,331 | 2,980 | 29,078 | 29,188 |
| loss | 21 | yes / yes | 843 | 292 | 50,709 | 50,792 |
| position | 30 | yes / yes | 692 | 334 | 51,284 | 51,333 |
| quiet | 2 | yes / yes | 3,453 | 3,167 | 55,698 | 55,062 |
| sweep | 11 | yes / yes | 913 | 458 | 51,363 | 51,208 |
| **All scenarios** | **88** | **yes / yes** | **995** | **375** | **50,245** | **51,292** |

**Reading the results.**

- Both versions send exactly the expected orders in every scenario, so the
  cache changes only speed.
- With the cache, the median order leaves 375 ns after the market data that
  triggered it; with the full scan, 51,292 ns (about 137x slower). Each scan
  reads about 1.6 MB of ladder (200,000 price levels x 8 bytes), against a
  32-byte struct for the cached top.
- Means are above medians because the first orders of each run are sent while
  the program is still cold.
- `quiet` and `gap` send only a few orders: `quiet`'s are its cold first quotes,
  and half of `gap`'s are cancels sent while halting, which return before the
  top of book is read.

**Caveats.**

- The full scan is the literal "search the book" alternative the design doc
  rejects, and the worst case. A search that starts near the current prices
  would close much of the gap in these short, calm scenarios.
- The scenarios are small (2 to 30 orders per run), hence 30 runs each.

## Sources

- STAC-T1.EMINI overview (tick-to-trade definition):
  https://docs.stacresearch.com/system/files/central/t1_emini_overview.pdf
- Carl Cook, "When a Microsecond Is an Eternity: High Performance Trading Systems
  in C++", CppCon 2017 (slide 28: "denormalized data is not a sin";
  slide 52: measure end to end):
  https://isocpp.org/blog/2018/09/cppcon-2017-when-a-microsecond-is-an-eternity-high-performance-trading-syst
- QuantCup 1 winning matching engine, which tracks `askMin`/`bidMax` over a
  price-indexed array: https://gist.github.com/2855852
