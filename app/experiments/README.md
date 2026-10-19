# Experiments

Measurements supporting the Assignment 1 critique of the market maker. Nothing here
changes what the app trades: `make verify` passes, and every experiment checks that each
version sends exactly the orders in `sim/fixtures/*.expected`.

| # | Experiment | Design decision examined | Result in one line |
|---|---|---|---|
| 1 | [Corrected evaluation](#1-corrected-evaluation) | §2.1 Evaluation | The original report averages the wrong interval over the wrong events; per-order tick-to-trade fixes both |
| 2 | [Cached top of book](#2-cached-top-of-book) | §2.2.1 Top of book (good decision) | Searching the price ladder instead makes the median order ~124× slower |
| 3 | [Risk checks](#3-risk-checks-exceptions-vs-error-flags) | §2.2.3 Risk checks (bad decision) | Exceptions are thrown on routine messages; Cook's error flags make message handling 6–12× faster |

## How the experiments work

- **Swapping one component.** Each alternative version lives in a folder that mirrors the
  app's paths (e.g. `top_of_book/full_scan/app/market_data/book.h`). Building with
  `-I <that folder>` ahead of `-I .` makes the app's `#include`s pick it up, so only the
  file under test changes. The app's own files are never edited.
- **Same trading.** Every run's `orders.txt` is compared with the scenario's `.expected` file.
- **Metrics** (all wall-clock nanoseconds):
  - **Tick-to-trade**: for each order, the time it was sent minus the time the message that
    triggered it arrived. Both timestamps come from the simulator's capture tap, outside the
    app. This follows STAC-T1: *"the egress time of the trade message minus the ingress time
    of the market data message triggering the trade."*
  - **Handler time**: for each market data message or exchange reply, the time the app
    finished handling it minus the time it arrived.
- **Statistics.** Each scenario is run 30 times per version, alternating versions so
  background load affects all alike; samples are pooled. Every table reports the **mean**,
  the **median** (the typical value, unaffected by a few slow outliers) and the **standard
  deviation** (the spread; sample standard deviation).
- **Machine.** Apple M4 Pro, Apple clang 17, `-O2`. Absolute times differ between sessions
  as the machine's load changes; compare versions **within** a table, not across tables.

```sh
sh app/experiments/evaluation/run.sh            # 1. original vs. corrected report
sh app/experiments/top_of_book/run.sh           # 2. cached top of book vs. full scan
sh app/experiments/risk_checks/count_throws.sh  # 3a. how often exceptions are thrown, and their cost
sh app/experiments/risk_checks/run.sh           # 3b. exceptions vs. error flags
```

Each script prints its tables and saves a copy under `build/experiments/`.

---

## 1. Corrected evaluation

**Files:** `analysis_corrected.h` (printed after the original report by every run of
`build/market_maker`), `evaluation/` (measurement).

### The problem with the original report (`app/evaluation/analysis.h`)

- **Wrong end point.** It measures each handler from arrival to *the end of the handler*,
  not to when the order left. Work done after the order is sent (the other side's order,
  logging) is counted, and a message that sends two orders gives one number instead of two.
- **Wrong events.** It averages over *every* delivery: messages that send no order, exchange
  replies, and timer ticks, which never send a quote. A run sends 2 to 30 orders but the
  report averages 36 to 118 deliveries.
- **Mean only.** One cold first message (tens of µs) dominates the average.

### The correction (`analysis_corrected.h`)

- Iterates over **orders**, not deliveries: one latency per order, ending at its own `Send`.
- Deliveries that send nothing contribute nothing; every order counts, including the
  loss-limit halt's cancels sent from the timer.
- Prints the count, mean, median and standard deviation, e.g.
  `corrected tick-to-trade: 14 orders, mean 1372 ns, median 416.5 ns, std dev 2366 ns`.

### Measurement

`evaluation/` runs the app 30 times per scenario and collects the samples each report
summarizes: every delivery's handler time (original) and every order's tick-to-trade
(corrected).

### Results (ns)

| Scenario | Original: samples per run | Mean | Median | Std dev | Corrected: orders per run | Mean | Median | Std dev |
|---|---|---|---|---|---|---|---|---|
| basic | 54 | 1,554 | 83 | 8,950 | 14 | 1,201 | 417 | 2,168 |
| empty_side | 42 | 2,348 | 42 | 9,738 | 6 | 2,237 | 1,000 | 2,216 |
| gap | 36 | 2,765 | 42 | 10,157 | 4 | 4,706 | 4,562 | 949 |
| loss | 118 | 1,565 | 83 | 6,159 | 21 | 1,328 | 458 | 1,830 |
| position | 117 | 1,065 | 42 | 6,087 | 30 | 974 | 542 | 1,362 |
| quiet | 48 | 1,668 | 42 | 9,362 | 2 | 5,541 | 5,208 | 2,229 |
| sweep | 59 | 1,454 | 42 | 9,029 | 11 | 1,465 | 708 | 1,969 |

### Conclusions

- **The original measures mostly non-trading work.** Its typical sample (median 42 to 83 ns)
  is a message that sends nothing; a typical order actually takes 417 to 5,208 ns.
- **Its mean is unreliable.** The standard deviation is about 4 to 6 times the mean: a few
  cold messages of tens of µs dominate it.
- **Its error has no fixed direction.** In `gap`, `quiet` and `sweep` the original mean is
  lower than the true tick-to-trade (diluted by cheap timer ticks and no-op messages); in
  the other four it is higher. The
  number depends on the scenario's mix of events, not only on the app's speed.
- **Fix:** measure per order from the tap's own timestamps (`Send` time minus arrival of the
  triggering message), and report the median and spread, not only the mean.

---

## 2. Cached top of book

**Files:** `top_of_book/` (baseline book, measurement).

### Decision tested (design doc §2.2.1, "Top of book")

- `Requote()` needs the best bid and ask on every market data message and exchange reply,
  **before** deciding whether to send an order.
- The book keeps them in a 32-byte struct (`top_`), updated only when an order at or better
  than the best changes. Reading the top of book is a copy of four fields.
- The design doc calls this "deliberate denormalization": a duplicate of exactly the data
  the hot path needs.

### Baseline: full ladder scan (`top_of_book/full_scan/`)

- The app's book with the cache removed: no `top_`, no `RecomputeBest`.
- `top()` searches the price ladder on every call: bids from $2,000 down, asks from $0 up,
  each stopping at the first non-empty price level. That reads about 200,000 levels × 8 bytes
  ≈ 1.6 MB per call, against 32 bytes for the cached copy.
- Everything else in the book and the app is unchanged.

### Measurement

Both versions, 30 alternating runs per scenario; tick-to-trade per order.

### Results (ns)

| Scenario | Orders per run | Same orders | Cached: mean | Median | Std dev | Full scan: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|---|
| basic | 14 | yes | 946 | 417 | 1,266 | 79,119 | 77,209 | 4,529 |
| empty_side | 6 | yes | 1,955 | 958 | 1,862 | 80,642 | 79,062 | 4,722 |
| gap | 4 | yes | 4,705 | 4,500 | 2,156 | 43,517 | 44,750 | 38,682 |
| loss | 21 | yes | 1,210 | 458 | 1,394 | 79,736 | 77,375 | 7,419 |
| position | 30 | yes | 921 | 542 | 1,162 | 79,576 | 77,333 | 4,909 |
| quiet | 2 | yes | 3,992 | 4,250 | 1,233 | 83,927 | 82,542 | 4,563 |
| sweep | 11 | yes | 1,326 | 708 | 1,634 | 80,674 | 77,604 | 6,658 |
| **All scenarios** | **88** | **yes** | **1,357** | **625** | **1,667** | **78,211** | **77,417** | **12,551** |

### Conclusions

- **Same orders, far less work.** Both versions trade identically; with the cache the median
  order leaves after 625 ns, with the full scan after 77,417 ns (~124× slower).
- **Why:** every scan reads ~1.6 MB, about 12× the M4 Pro's 128 KB L1 data cache, on every
  message; the cached copy is one 32-byte struct, a single cache line.
- **`gap`** has a smaller difference and a large spread because half its orders are the
  halt's cancels, which are sent before the top of book is read.
- **Matches industry practice.** Carl Cook (CppCon 2017, slide 28): *"denormalized data is not
  a sin … better than trampling your cache"*; the QuantCup 1 winning order book also keeps
  `bidMax`/`askMin` over a price-indexed array.

### Caveats

- The full scan is the literal, worst-case "search the book". A search starting near the
  current prices would close much of the gap in these short, calm scenarios.
- The scenarios are small (2 to 30 orders per run), hence 30 runs each.

---

## 3. Risk checks: exceptions vs. error flags

**Files:** `risk_checks/` (instrumented build, fixed build, measurements).

### Decision tested (design doc §2.2.3, "Risk checks")

The design doc throws an exception from every failed risk check, arguing exceptions "are free
when not thrown, and once they are thrown, we are no longer in the hotpath."

### The four checks

| Check | Fails when | What the app then does |
|---|---|---|
| Book invalid | One side of the book is empty, or bid ≥ ask | Skips this message; quotes stay |
| Position limit | Quoting 100 more shares would pass ±500 | Skips that side; the other side still quotes |
| Sequence gap | A market data message was missed | **Halts** (cancels all orders) the first time; ignores every later message |
| Loss limit | The loss passes $100 (detected on the timer) | Ignores every later message (the halt itself needs no exception) |

The other exceptions in the app (`std::out_of_range` from the book, `std::invalid_argument`
from decoding, `std::runtime_error` from the decision log) are fatal errors that never occur
in these scenarios.

### 3a. How often they are thrown, and what each throw costs

**Method.** `instrumented/` is the app with logging added to `risk.h` and `market_maker.cpp`:
each throw records the time just before `throw`, and each `catch` reports the exception type,
what it does with it, and the time elapsed. That interval is the exception's own cost:
creating the exception object and unwinding the stack. 30 runs per scenario.

**Throws per run** (the counts are identical every run; times in ns):

| Scenario | Book invalid | Position limit | Gap: halt | Ignored while halted | **Total** | Time throwing per run: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|---|
| basic | 2 | – | – | – | **2** | 31,532 | 30,521 | 8,755 |
| empty_side | 9 | – | – | – | **9** | 46,520 | 45,604 | 5,556 |
| gap | 2 | – | 1 | 6 | **9** | 58,592 | 58,668 | 7,271 |
| loss | 10 | 13 | – | 10 | **33** | 130,685 | 121,518 | 31,325 |
| position | 2 | 12 | – | – | **14** | 61,413 | 60,709 | 6,488 |
| quiet | 3 | – | – | – | **3** | 29,360 | 28,416 | 3,914 |
| sweep | 3 | – | – | – | **3** | 30,590 | 29,834 | 3,857 |

**Cost of one throw** (ns, all scenarios together):

| Throw | What the catch does | Mean | Median | Std dev |
|---|---|---|---|---|
| First throw of a run (the C++ runtime loads its unwinding tables) | skip tick | 24,408 | 23,458 | 5,881 |
| Book invalid | skip tick | 3,257 | 2,916 | 682 |
| Position limit | skip side | 2,973 | 2,750 | 1,658 |
| Sequence gap | **halt** | 4,722 | 4,333 | 2,332 |
| Sequence gap | ignore (already halted) | 3,594 | 3,458 | 719 |
| Loss limit | ignore (already halted) | 3,906 | 3,458 | 3,053 |

- **73 throws** in one run of the 7 scenarios; **72 of them just return**, only one halts.
- Every scenario throws at least twice at the start, before both sides of the book exist;
  in `gap` and `loss` about half of all messages throw.
- A throw costs ~3 µs (~23 µs for the first of a run), while a typical message is handled in
  ~0.04 µs. Nothing records these throws: `decisions.log` only shows orders and the halt.
- The logging adds some overhead between throws; an isolated benchmark gives ~2 µs per throw.

### The fix: error flags (`cook_flags/`)

From Carl Cook's CppCon 2017 talk, slide 16 ("Slowpath removal"): instead of handling each
error where it is found, collect them into one `errorFlags` value and write
*"if (!errorFlags) sendOrderToExchange(); else HandleError(errorFlags);"*, keeping the
handler out of line (*"ensure that error handling code will not be inlined"*).

- **One number for all checks.** `RiskGate::Flags()` evaluates the same four conditions and
  sets one bit per failure; nothing is thrown.
- **One branch on the quoting path.** `Requote()` tests that number once; the two per-side
  position checks become two bit tests.
- **Rare cases out of line.** Halting and "nothing to do" go to `HandleRiskFlags()`, marked
  `[[gnu::noinline, gnu::cold]]`.
- **Same behaviour.** Same checks, same order, same outcomes.

### 3b. Exceptions vs. error flags

**Method.** Both versions, 30 alternating runs per scenario. Two metrics: handler time,
because most failed checks happen on messages that send no order, and tick-to-trade.
**Both versions send exactly the `.expected` orders in every scenario.**

**Handler time** per market data message or exchange reply (ns):

| Scenario | Messages per run | Exceptions: mean | Median | Std dev | Error flags: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|
| basic | 44 | 1,985 | 83 | 10,658 | 318 | 83 | 956 |
| empty_side | 22 | 4,869 | 1,000 | 15,430 | 507 | 42 | 1,587 |
| gap | 16 | 6,878 | 3,375 | 17,511 | 554 | 42 | 1,706 |
| loss | 78 | 2,427 | 459 | 7,813 | 242 | 42 | 1,016 |
| position | 87 | 1,523 | 83 | 7,799 | 240 | 42 | 725 |
| quiet | 28 | 3,085 | 42 | 13,620 | 305 | 42 | 1,271 |
| sweep | 39 | 2,192 | 42 | 10,682 | 332 | 42 | 1,105 |

**Tick-to-trade** per order (ns):

| Scenario | Orders per run | Exceptions: mean | Median | Std dev | Error flags: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|
| basic | 14 | 1,088 | 417 | 1,646 | 1,161 | 458 | 1,795 |
| empty_side | 6 | 2,170 | 938 | 2,241 | 2,649 | 958 | 2,928 |
| gap | 4 | 4,885 | 4,584 | 1,238 | 3,015 | 1,688 | 3,022 |
| loss | 21 | 1,283 | 458 | 1,554 | 966 | 375 | 1,714 |
| position | 30 | 988 | 542 | 1,365 | 811 | 375 | 1,312 |
| quiet | 2 | 4,890 | 4,771 | 1,679 | 5,567 | 5,375 | 1,949 |
| sweep | 11 | 1,387 | 708 | 1,800 | 1,540 | 708 | 2,136 |

### Conclusions

- **The design doc's premise fails in practice.** The exceptions are thrown on routine
  messages, 72 of 73 times only to return, at ~3 µs each (~23 µs the first time).
- **Error flags remove that cost without changing a single order.** Mean handler time falls
  6–12× in every scenario, and its standard deviation ~10×; in `gap`, the median falls from
  3,375 ns to 42 ns.
- **Tick-to-trade improves where an order follows a failed check:** the halt's cancels in
  `gap` (median 4,584 → 1,688 ns), and the asks quoted while the bid is blocked in `loss` and
  `position`. Elsewhere no check fails on the way to an order, so it is unchanged within noise.
- `quiet` sends only its 2 cold first quotes, so its tick-to-trade is noise.

---

## Sources

- STAC-T1.EMINI overview (tick-to-trade definition):
  https://docs.stacresearch.com/system/files/central/t1_emini_overview.pdf
- Carl Cook, "When a Microsecond Is an Eternity: High Performance Trading Systems in C++",
  CppCon 2017 (slide 16: "Slowpath removal"; slide 22: exceptions are "zero cost if they
  don't throw" but "don't use exceptions for control flow"; slide 28: "denormalized data is
  not a sin"; slide 52: measure end to end):
  https://isocpp.org/blog/2018/09/cppcon-2017-when-a-microsecond-is-an-eternity-high-performance-trading-syst
- QuantCup 1 winning matching engine, which tracks `askMin`/`bidMax` over a price-indexed
  array: https://gist.github.com/2855852
