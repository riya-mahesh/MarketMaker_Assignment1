# Experiments

Measurements supporting the Assignment 1 critique of the market maker. Nothing here
changes what the app trades: `make verify` passes, and every experiment checks that each
version sends exactly the orders in `sim/fixtures/*.expected`.

| # | Experiment | Design decision examined | Result in one line |
|---|---|---|---|
| 1 | [Corrected evaluation](#1-corrected-evaluation) | §2.1 Evaluation (flaw) | The original report takes one end time per delivery and averages deliveries that sent no order; per-order tick-to-trade fixes both |
| 2 | [Cached top of book](#2-cached-top-of-book) | §2.2.1 Top of book (good decision) | Searching the price ladder instead makes the median order ~124× slower |
| 3 | [Risk checks](#3-risk-checks-exceptions-vs-error-flags) | §2.2.3 Risk checks (flaw) | Exceptions are thrown on routine messages; Cook's error flags make message handling 6–12× faster |

All results below come from one session (all scripts run back to back).

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
  - **Handler time**: for each market data message or exchange report, the time the app
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
sh app/experiments/risk_checks/count_throws.sh  # 3. how often exceptions are thrown, and their cost
sh app/experiments/risk_checks/run.sh           # 3. exceptions vs. error flags
```

Each script prints its tables and saves a copy under `build/experiments/`.

---

## 1. Corrected evaluation

**Files:** `analysis_corrected.h` (the corrected report, printed after the original one by
every run of `build/market_maker`), `evaluation/` (measurement).

### Definition: tick-to-trade

- Measured **per order**: the time the order leaves minus the time the market data message
  that triggered it arrived. STAC-T1: *"the egress time of the trade message minus the
  ingress time of the market data message triggering the trade."*
- A tick that triggers a bid and an ask gives **two** latencies:
  L(buy) = t(buy sent) − t(tick) and L(sell) = t(sell sent) − t(tick).

### Flaw 1: one end time per delivery

- `Requote()` can send a bid and then an ask. Only afterwards, at the end of the handler,
  does `latency_.Record()` take a single end time.
- `analysis.h` then counts **one** sample per delivery, t(handler end) − t(tick): it ends
  after both orders and the work that follows them, and counts 1 sample instead of 2.

**Evidence.** Deliveries that sent a bid and an ask (ns, 30 runs):

| Scenario | Such deliveries per run | Original sample (handler end): mean | Median | Std dev | Bid tick-to-trade: mean | Median | Std dev | Ask tick-to-trade: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | 3 | 2,158 | 750 | 2,092 | 1,294 | 375 | 1,397 | 2,107 | 708 | 2,091 |
| empty_side | 3 | 2,475 | 1,125 | 2,148 | 1,516 | 708 | 1,383 | 2,421 | 1,083 | 2,141 |
| gap | 2 | 4,910 | 4,688 | 663 | 3,752 | 4,062 | 991 | 4,794 | 4,584 | 674 |
| loss | 5 | 1,825 | 896 | 2,097 | 1,051 | 375 | 1,531 | 1,784 | 875 | 2,085 |
| position | 11 | 1,185 | 709 | 1,414 | 642 | 333 | 967 | 1,141 | 667 | 1,411 |
| quiet | 1 | 5,583 | 4,874 | 1,481 | 3,579 | 3,021 | 1,436 | 5,533 | 4,833 | 1,481 |
| sweep | 5 | 1,731 | 834 | 1,867 | 1,044 | 459 | 1,270 | 1,693 | 792 | 1,868 |

- The original's single sample is later than **both** orders: in `basic`, a median 750 ns
  where the bid actually left after 375 ns and the ask after 708 ns.
- The bid, the order that leaves first, is overstated 1.6× to 2.4× (median) in every
  scenario except `gap`, whose two-order deliveries are its cold first quotes.

### Flaw 2: deliveries with no trading decision are averaged in

- `Record()` also runs at the end of every **timer tick** (which never quotes) and every
  market data message or exchange report that **leaves our quotes unchanged**.
- `analysis.h` matches and averages all of them, although no order was sent.

**Evidence.** What the original report averages, per run (the counts are identical every run):

| Scenario | Samples averaged | Timer ticks | Messages / reports with no order | Messages / reports that sent orders | Orders sent |
|---|---|---|---|---|---|
| basic | 54 | 10 | 33 | 11 | 14 |
| empty_side | 42 | 20 | 19 | 3 | 6 |
| gap | 36 | 20 | 14 | 2 | 4 |
| loss | 118 | 39 | 63 | 16 | 21 |
| position | 117 | 30 | 68 | 19 | 30 |
| quiet | 48 | 20 | 27 | 1 | 2 |
| sweep | 59 | 20 | 33 | 6 | 11 |

- In `gap`, 34 of the 36 samples sent no order, and 20 of them are timer ticks.
- Only 2% (`quiet`) to 20% (`basic`) of the averaged samples come from deliveries that
  sent an order.

### Fix: per-order tick-to-trade (`analysis_corrected.h`)

- Iterates over the capture tap's **sends** instead of the deliveries: for each order,
  L = t(send) − t(entry) of the delivery that triggered it. Both timestamps are the tap's.
- A delivery with two orders gives two latencies; a delivery with none gives none.
- Counts every order the app sends, including the loss-limit halt's cancels, which the
  timer triggers.
- Reports the count, mean, median and standard deviation, e.g.
  `corrected tick-to-trade: 14 orders, mean 1372 ns, median 416.5 ns, std dev 2366 ns`.

**Result.** The original report's samples vs. the corrected samples (ns, 30 runs):

| Scenario | Original: samples per run | Mean | Median | Std dev | Corrected: orders per run | Mean | Median | Std dev |
|---|---|---|---|---|---|---|---|---|
| basic | 54 | 1,330 | 83 | 7,550 | 14 | 971 | 417 | 1,349 |
| empty_side | 42 | 2,171 | 42 | 8,822 | 6 | 1,968 | 958 | 1,854 |
| gap | 36 | 2,487 | 42 | 8,609 | 4 | 4,273 | 4,333 | 993 |
| loss | 118 | 1,507 | 83 | 5,394 | 21 | 1,272 | 459 | 1,593 |
| position | 117 | 1,047 | 42 | 6,024 | 30 | 954 | 542 | 1,260 |
| quiet | 48 | 1,459 | 42 | 8,006 | 2 | 4,556 | 4,479 | 1,750 |
| sweep | 59 | 1,246 | 42 | 7,135 | 11 | 1,290 | 667 | 1,571 |

### Conclusions

- **The original mostly measures non-trading work.** Its median sample (42 to 83 ns) is a
  delivery that sent nothing; a typical order takes 417 to 4,479 ns.
- **Its mean is unreliable.** Its standard deviation is 3.5 to 6 times its mean, because a few
  cold deliveries of tens of µs dominate.
- **Its error has no fixed direction.** In `gap`, `quiet` and `sweep` the original mean is
  below the true tick-to-trade (diluted by cheap no-order samples); in the other four it is
  above. The result depends on the scenario's mix of events, not only on the app's speed.

---

## 2. Cached top of book

**Files:** `top_of_book/` (baseline book, measurement).

### The decision (design doc §2.2.1, "Top of book"): a good one

- `Requote()` needs the best bid and ask on **every** market data message and exchange
  report, **before** deciding whether to send an order.
- The book keeps them in a 32-byte `BookTop` (fits in one 128-byte cache line), updated only
  when an order at or better than the best changes, instead of searching the price ladder.
- This is **deliberate denormalization**: a duplicate of exactly the data the hot path reads.
  Carl Cook (CppCon 2017, slide 28): *"denormalized data is not a sin … better than
  trampling your cache."*

### Experiment: replace the cache with a full ladder scan

- **Baseline** (`top_of_book/full_scan/`): the app's book with the cache removed (no `top_`,
  no `RecomputeBest`). `top()` scans the price ladder on every call: bids from $2,000 down,
  asks from $0 up, each stopping at the first non-empty level.
- Everything else in the book and the app is unchanged.
- Both versions, 30 alternating runs per scenario; tick-to-trade per order.

### Result (ns)

| Scenario | Orders per run | Same orders | Cached: mean | Median | Std dev | Full scan: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|---|
| basic | 14 | yes | 1,126 | 417 | 1,764 | 80,100 | 77,334 | 7,732 |
| empty_side | 6 | yes | 2,278 | 1,000 | 2,296 | 82,656 | 79,979 | 7,317 |
| gap | 4 | yes | 5,087 | 4,667 | 1,312 | 44,837 | 50,020 | 39,266 |
| loss | 21 | yes | 1,331 | 438 | 1,716 | 80,430 | 77,646 | 6,339 |
| position | 30 | yes | 981 | 562 | 1,359 | 79,624 | 77,375 | 4,982 |
| quiet | 2 | yes | 4,881 | 4,979 | 1,481 | 85,519 | 82,896 | 6,999 |
| sweep | 11 | yes | 1,491 | 709 | 2,032 | 80,656 | 77,854 | 5,617 |
| **All scenarios** | **88** | **yes** | **1,515** | **625** | **1,957** | **78,781** | **77,583** | **12,719** |

### Why: memory read per lookup

| | Cached top of book | Full ladder scan |
|---|---|---|
| Memory read to find the best bid and ask | 32 bytes | ~200,000 price levels × 8 bytes ≈ 1.6 MB |
| 128-byte cache lines touched | 1 | ~12,500 |
| Compared with the 128 KB L1 data cache | negligible | ~12× its size, on every message |

### Conclusions

- **Same orders, far less work.** Both versions send exactly the `.expected` orders in all 7
  scenarios. The median order leaves after 625 ns with the cache and 77,583 ns with the
  full scan, about 124× slower.
- **`gap`** differs less and has a large spread because half its orders are the halt's
  cancels, which are sent before the top of book is read.
- **Matches industry practice:** the QuantCup 1 winning order book also keeps
  `bidMax`/`askMin` over a price-indexed array.
- **Caveat:** the full scan is the literal, worst-case "search the book". A search starting
  near the current prices would close much of the gap in these short, calm scenarios.

---

## 3. Risk checks: exceptions vs. error flags

**Files:** `risk_checks/` (instrumented build, fixed build, measurements).

### The decision (design doc §2.2.3, "Risk checks")

- Every failed risk check **throws an exception**, which the quoting code catches.
- The design doc's argument: exceptions "are free when not thrown, and once they are thrown,
  we are no longer in the hotpath."

| Check | Fails when | What the app then does |
|---|---|---|
| Book invalid | One side of the book is empty, or bid ≥ ask | Skips this message; quotes stay |
| Position limit | Quoting 100 more shares would pass ±500 | Skips that side; the other side still quotes |
| Sequence gap | A market data message was missed | **Halts** (cancels all orders) the first time; ignores every later message |
| Loss limit | The loss passes $100 (detected on the timer) | Ignores every later message (the halt itself needs no exception) |

The app's other exceptions (`std::out_of_range` from the book, `std::invalid_argument` from
decoding, `std::runtime_error` from the decision log) are fatal errors that never occur here.

### Flaw: the exceptions are thrown on routine messages

- **Book invalid** throws on every message while a side of the book is empty: the start of
  every scenario, and `empty_side` from 5 to 12 ms.
- **Position limit** throws on every message while the position is at the limit, in
  `QuoteSide(Buy)`, **before** the ask is quoted (`position`, `loss`).
- **Sequence gap / loss limit** throw on every message for the rest of the run after a halt,
  and the halt's cancels are sent from inside the `catch` (`gap`, `loss`).
- Each throw allocates the exception object and unwinds the stack, so "no longer in the
  hotpath" does not hold: the next order, or the next message, waits for it.

**Evidence.** `instrumented/` adds logging to `risk.h` and `market_maker.cpp`: each throw
records the time just before `throw`, and each `catch` reports the exception, what it does
with it, and the time elapsed. 30 runs per scenario; times in ns.

Throws per run (the counts are identical every run):

| Scenario | Book invalid | Position limit | Gap: halt | Ignored while halted | **Total** | Time throwing per run: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|---|
| basic | 2 | – | – | – | **2** | 28,181 | 26,188 | 7,481 |
| empty_side | 9 | – | – | – | **9** | 46,425 | 43,584 | 7,271 |
| gap | 2 | – | 1 | 6 | **9** | 48,699 | 46,730 | 6,096 |
| loss | 10 | 13 | – | 10 | **33** | 120,976 | 117,412 | 8,239 |
| position | 2 | 12 | – | – | **14** | 59,519 | 57,020 | 6,961 |
| quiet | 3 | – | – | – | **3** | 27,569 | 26,709 | 3,363 |
| sweep | 3 | – | – | – | **3** | 27,297 | 26,479 | 3,857 |

Cost of one throw (all scenarios together):

| Throw | What the catch does | Mean | Median | Std dev |
|---|---|---|---|---|
| First throw of a run (the C++ runtime loads its unwinding tables) | skip tick | 21,291 | 20,020 | 4,742 |
| Book invalid | skip tick | 3,208 | 2,875 | 647 |
| Position limit | skip side | 2,864 | 2,708 | 572 |
| Sequence gap | **halt** | 4,120 | 3,980 | 338 |
| Sequence gap | ignore (already halted) | 3,635 | 3,458 | 1,375 |
| Loss limit | ignore (already halted) | 3,511 | 3,375 | 752 |

- **73 throws** in one run of the 7 scenarios; **72 of them just return**, only one halts.
- In `gap` and `loss`, about half of all messages throw.
- A throw costs ~3 µs (~20 µs for the first of a run); a typical message is handled in
  ~0.04 µs. Nothing records these throws: `decisions.log` only shows orders and the halt.
- The logging adds some overhead between throws; an isolated benchmark gives ~2 µs per throw.

### Fix: error flags (`cook_flags/`)

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

### Result

Both versions, 30 alternating runs per scenario. **Both send exactly the `.expected` orders
in every scenario.** Times in ns.

**Handler time** per market data message or exchange report (most failed checks happen on
messages that send no order, so this is where their cost shows):

| Scenario | Messages per run | Exceptions: mean | Median | Std dev | Error flags: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|
| basic | 44 | 1,962 | 83 | 10,368 | 332 | 83 | 1,054 |
| empty_side | 22 | 4,576 | 959 | 14,047 | 469 | 42 | 1,400 |
| gap | 16 | 6,729 | 3,375 | 17,046 | 555 | 42 | 1,640 |
| loss | 78 | 2,379 | 500 | 8,032 | 234 | 42 | 808 |
| position | 87 | 1,504 | 83 | 7,880 | 247 | 42 | 750 |
| quiet | 28 | 2,922 | 42 | 12,672 | 325 | 42 | 1,300 |
| sweep | 39 | 2,366 | 42 | 11,722 | 345 | 42 | 1,094 |

**Tick-to-trade** per order:

| Scenario | Orders per run | Exceptions: mean | Median | Std dev | Error flags: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|
| basic | 14 | 1,109 | 458 | 1,687 | 1,227 | 417 | 2,022 |
| empty_side | 6 | 2,220 | 938 | 2,355 | 2,321 | 958 | 2,499 |
| gap | 4 | 4,939 | 4,584 | 1,196 | 2,983 | 1,958 | 2,897 |
| loss | 21 | 1,307 | 458 | 1,666 | 957 | 375 | 1,689 |
| position | 30 | 978 | 542 | 1,408 | 826 | 417 | 1,352 |
| quiet | 2 | 5,403 | 5,083 | 2,007 | 5,753 | 5,667 | 1,786 |
| sweep | 11 | 1,520 | 708 | 2,126 | 1,559 | 709 | 2,092 |

### Conclusions

- **The design doc's premise fails in practice.** The exceptions are thrown on routine
  messages, 72 of 73 times only to return, at ~3 µs each (~20 µs the first time).
- **Error flags remove that cost without changing a single order.** Mean handler time falls
  6–12× in every scenario and its standard deviation ~10×; in `gap`, the median falls from
  3,375 ns to 42 ns.
- **Tick-to-trade improves where an order follows a failed check:** the halt's cancels in
  `gap` (median 4,584 → 1,958 ns), and the asks quoted while the bid is blocked in `loss` and
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
