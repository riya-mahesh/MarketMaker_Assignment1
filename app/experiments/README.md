# Experiments

Supporting measurements for the Assignment 1 critique. Nothing here changes what
the market maker trades: `make verify` passes with all of it in place.

| Path | What it is |
|---|---|
| `analysis_corrected.h` | Corrected latency report: tick-to-trade per order (printed after the original report by every run of `build/market_maker`) |
| `top_of_book/` | Experiment: cached top of book vs. scanning the price ladder for the best bid and ask |
| `risk_checks/` | Experiment: risk checks that throw exceptions vs. Cook's error flags |

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
  so background load/ noise on the machine affects both alike.
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
  reads about 1.6 MB of ladder (200,000 price levels x 8 bytes in the worst case), against a
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

## Risk checks: exceptions vs. error flags (`risk_checks/`)

**Decision tested (design doc §2.2.3, "Risk checks").** Every check throws a
`RiskViolation` when it fails, on the grounds that "exceptions are free when not
thrown, and once they are thrown, we are no longer in the hotpath."

### Every throw and catch in the app

| Where it is thrown | Exception | Caught where | What happens |
|---|---|---|---|
| `risk.h` `CheckBook` | `RiskViolation(BookInvalid)` | `Requote()` | **Returns**: skip this message, resting quotes stay |
| `risk.h` `CheckPosition` | `RiskViolation(PositionLimit)` | `QuoteSide()` | **Returns**: that side is skipped, the other side still quotes |
| `risk.h` `CheckStanding` | `RiskViolation(SequenceGap)` | `Requote()` | First time: **halts** (cancel all). Every later message: **returns** |
| `risk.h` `CheckStanding` | `RiskViolation(LossLimitBreached)` | `Requote()` | **Returns** (the halt itself happens in `OnTimer` without an exception) |
| `book.cpp` `Lookup`, `Apply(AddOrder)` | `std::out_of_range` (ref or price outside the tables) | `main()` | Fatal: the run stops with an error. Never thrown in these scenarios |
| `wire.h` `Decode` | `std::invalid_argument` (wrong message size) | `main()` | Fatal. Never thrown |
| `decision_log.h` constructor | `std::runtime_error` (cannot open the log) | `main()` | Fatal, at startup. Never thrown |

Only the four `RiskViolation` throws happen in normal operation, and all but one
of them (the first `SequenceGap`) end in a plain `return`. Nothing records them:
`decisions.log` only shows orders and the halt reason.

### How often they are thrown, and what each throw costs

`count_throws.sh` builds the app with `instrumented/` copies of `risk.h` and
`market_maker.cpp` that take the wall time just before every `throw` and again
at the start of its `catch`. Everything else is unchanged.
Per run (30 runs per scenario; times are medians):

| Scenario | Exception | What the catch does | Throws per run | ns per throw |
|---|---|---|---|---|
| every scenario | the first throw of the run (`BookInvalid`) | return: skip tick | 1 | 18,042 to 19,896 |
| basic | BookInvalid | return: skip tick | 1 | 3,917 |
| empty_side | BookInvalid | return: skip tick | 8 | 2,875 |
| gap | BookInvalid | return: skip tick | 1 | 4,458 |
| gap | SequenceGap | **halt** | 1 | 4,250 |
| gap | SequenceGap | return: already halted | 6 | 3,500 |
| loss | BookInvalid | return: skip tick | 9 | 2,792 |
| loss | LossLimitBreached | return: already halted | 10 | 3,375 |
| loss | PositionLimit | return: side blocked | 13 | 2,667 |
| position | BookInvalid | return: skip tick | 1 | 3,583 |
| position | PositionLimit | return: side blocked | 12 | 2,792 |
| quiet | BookInvalid | return: skip tick | 2 | 3,438 |
| sweep | BookInvalid | return: skip tick | 2 | 3,354 |

| Scenario | Throws per run | Of which halt | Time spent throwing per run (ns, mean) |
|---|---|---|---|
| basic | 2 | 0 | 23,876 |
| empty_side | 9 | 0 | 46,579 |
| gap | 9 | 1 | 52,539 |
| loss | 33 | 0 | 114,996 |
| position | 14 | 0 | 59,417 |
| quiet | 3 | 0 | 26,344 |
| sweep | 3 | 0 | 26,092 |

Across one run of all 7 scenarios that is 73 throws, of which 72 are routine
`return`s (only `gap`'s first `SequenceGap` halts), and each costs
2.7 to 4.5 µs (about 19 µs for the first throw of a run, when the C++ runtime
loads its unwinding tables). The figures include the instrumentation's own
logging between throws, so they are somewhat higher than an isolated
microbenchmark (about 2 µs per throw on this machine).

### Fix: error flags (`cook_flags/`)

From Carl Cook's CppCon 2017 talk, slide 16 ("Slowpath removal"): *"Avoid this:
if (checkForErrorA()) handleErrorA(); else if … else sendOrderToExchange(); … Aim
for this: int64_t errorFlags; … if (!errorFlags) sendOrderToExchange(); else
HandleError(errorFlags);"*, with the tip *"ensure that error handling code will
not be inlined."*

- `RiskGate::Flags()` evaluates the same four conditions into one word, one bit
  per failure; nothing is thrown.
- `Requote()` tests that word with a single branch; the two per-side position
  checks become two bit tests, and `QuoteSide()` no longer checks risk.
- The rare cases go to `HandleRiskFlags()`, marked `[[gnu::noinline, gnu::cold]]`.
- Same checks, same order, same outcomes.

### Results

`run.sh` builds both versions (only the files in `cook_flags/` differ), runs
every scenario 30 times per version, alternating versions, and compares every
run's orders with `.expected`. Times in ns.

**Both versions send exactly the `.expected` orders in every scenario.**

Tick-to-trade per order:

| Scenario | Orders per run | Exceptions: mean | Exceptions: median | Error flags: mean | Error flags: median |
|---|---|---|---|---|---|
| basic | 14 | 1,128 | 458 | 1,241 | 458 |
| empty_side | 6 | 2,141 | 959 | 2,459 | 1,000 |
| gap | 4 | 4,926 | 4,604 | 3,144 | 1,646 |
| loss | 21 | 1,319 | 458 | 970 | 375 |
| position | 30 | 1,052 | 583 | 888 | 438 |
| quiet | 2 | 5,939 | 5,188 | 5,558 | 5,500 |
| sweep | 11 | 1,548 | 709 | 1,573 | 750 |

Handler time per market data message and execution report (most failed checks
happen on messages that send no order, so this is where their cost shows):

| Scenario | Messages per run | Exceptions: mean | Exceptions: median | Error flags: mean | Error flags: median |
|---|---|---|---|---|---|
| basic | 44 | 1,914 | 83 | 346 | 83 |
| empty_side | 22 | 4,662 | 1,000 | 503 | 42 |
| gap | 16 | 6,661 | 3,375 | 578 | 42 |
| loss | 78 | 2,409 | 480 | 234 | 42 |
| position | 87 | 1,566 | 83 | 264 | 42 |
| quiet | 28 | 3,139 | 42 | 317 | 42 |
| sweep | 39 | 2,399 | 42 | 350 | 42 |

`gap`, message by message (median handler time, 30 runs). Message 8 is dropped,
so the app halts at message 9:

| Message | What happens | Exceptions | Error flags |
|---|---|---|---|
| md 1 | Bid added, no asks yet: book invalid (first throw of the run) | 57,792 | 104 |
| md 2 | Bid added, still invalid | 4,146 | 42 |
| md 3 | Ask arrives: book valid, quotes both sides (no check fails) | 5,354 | 5,521 |
| md 9 | Message 8 missing: gap, halt, cancel both quotes | 4,625 | 416 |
| md 10 to 13 | Halted: every message ignored | 3,416 to 3,625 | 41 to 84 |
| report 3 and 4 | Halted: cancel confirmations ignored | 3,333 to 3,375 | 42 to 83 |

The halt's two cancels leave 4,416 ns after the gap is detected with exceptions,
and 333 ns with error flags.

**Reading the results.**

- Error flags cut mean handler time 5x to 12x in every scenario; in `gap`, the
  scenario with the most throws per message, the median goes from 3,375 ns to 42 ns.
- Tick-to-trade improves wherever an order is sent after a failed check: the
  halt's cancels in `gap` (median 4,604 to 1,646 ns), and the asks quoted while
  the bid is blocked in `loss` and `position`. Elsewhere no check fails on the
  way to `Send`, so tick-to-trade is unchanged.
- `quiet` sends only its 2 cold first quotes, so its tick-to-trade is noise.
- Times here are from a separate set of runs from the throw counts above, so
  compare versions within a table rather than across tables.

**Run it.**

```sh
sh app/experiments/risk_checks/count_throws.sh   # counts and times every throw -> throws_data.md (report: throws.md)
sh app/experiments/risk_checks/run.sh            # exceptions vs. error flags -> results.md
```

## Sources

- STAC-T1.EMINI overview (tick-to-trade definition):
  https://docs.stacresearch.com/system/files/central/t1_emini_overview.pdf
- Carl Cook, "When a Microsecond Is an Eternity: High Performance Trading Systems
  in C++", CppCon 2017 (slide 22: exceptions are "zero cost if they don't throw",
  but "don't use exceptions for control flow"; slide 28: "denormalized data is
  not a sin"; slide 52: measure end to end):
  https://isocpp.org/blog/2018/09/cppcon-2017-when-a-microsecond-is-an-eternity-high-performance-trading-syst
- QuantCup 1 winning matching engine, which tracks `askMin`/`bidMax` over a
  price-indexed array: https://gist.github.com/2855852
