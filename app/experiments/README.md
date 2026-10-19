# Experiments

Measurements supporting the Assignment 1 critique of the market maker. Nothing here
changes what the app trades: `make verify` passes, and every experiment checks that each
version sends exactly the orders in `sim/fixtures/*.expected`.

| # | Experiment | Design decision examined | Result in one line |
|---|---|---|---|
| 1 | [Corrected evaluation](#1-corrected-evaluation) | §2.1 Evaluation (flaw) | The original report takes one end time per delivery and averages deliveries that sent no order; per-order tick-to-trade fixes both |
| 2 | [Cached top of book](#2-cached-top-of-book) | §2.2.1 Top of book (good decision) | Searching the price ladder instead makes the median order ~129× slower |
| 3 | [Risk checks](#3-risk-checks-exceptions-vs-error-flags) | §2.2.3 Risk checks (flaw) | Exceptions are thrown on routine messages; Cook's error flags make message handling 5–11× faster |

All results below come from **one run** of each scenario per version (all scripts run back to back).

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
- **Statistics.** Each scenario is run **once** per version. The **mean**, **median** (the
  typical value, unaffected by a few slow outliers) and **standard deviation** (the spread;
  sample standard deviation) in every table are taken **over the individual orders, or
  messages, of that run**, e.g. the 14 orders of `basic`. Nothing is averaged across runs.
  A single run is noisy (one slow order can move a mean), so the median is the more
  reliable figure. `RUNS=n sh <script>` collects the orders of n runs instead.
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

### Flaw 1: one end time per delivery matched at the end of the handler

- `Requote()` can send a bid and then an ask. Only afterwards, at the end of the handler,
  does `latency_.Record()` take a single end time.
- `analysis.h` then counts **one** matched latency sample per delivery, t(handler end) − t(tick): it ends
  after both orders and the work that follows them, and counts 1 sample instead of 2 orders.

- **Bid sent:** when the bid left (the tap's `Send` time). This is the bid's tick-to-trade.
- **Ask sent:** when the ask left. This is the ask's tick-to-trade.
- **Handler finished:** when `latency_.Record()` ran at the end of the handler. This is the
  single number the original report counts for the delivery.

Times in ns; mean, median and standard deviation over the two-order deliveries of one run:

| Scenario | No of deliveries with 2 orders per run| Bid sent: mean | Median | Std dev | Ask sent: mean | Median | Std dev | Handler finished (original report): mean | Median | Std dev |
|---|---|---|---|---|---|---|---|---|---|---|
| basic | 3 | 1,556 | 417 | 2,045 | 2,514 | 708 | 3,200 | 2,556 | 750 | 3,200 |
| empty_side | 3 | 1,667 | 750 | 1,809 | 2,583 | 1,083 | 2,817 | 2,639 | 1,125 | 2,842 |
| gap | 2 | 4,688 | 4,688 | 1,503 | 5,771 | 5,771 | 30 | 5,896 | 5,896 | 147 |
| loss | 5 | 1,025 | 375 | 1,390 | 1,733 | 875 | 2,066 | 1,767 | 875 | 2,071 |
| position | 11 | 575 | 333 | 743 | 1,060 | 666 | 1,230 | 1,098 | 709 | 1,232 |
| quiet | 1 | 3,250 | 3,250 | 0 | 5,375 | 5,375 | 0 | 5,417 | 5,417 | 0 |
| sweep | 5 | 1,000 | 542 | 1,097 | 1,609 | 834 | 1,782 | 1,634 | 834 | 1,790 |

- The original's single sample is later than **both** orders: in `basic`, a median 750 ns
  where the bid actually left after 417 ns and the ask after 708 ns.
- It is effectively the **ask's** tick-to-trade: once the ask is sent, the handler only
  returns and reads the clock, so "handler finished" lands one clock step (~42 ns) later.
- The ~300 to 500 ns between the bid and the ask is the ask's pre-send work: its
  quote-history entry, its `fprintf` to `decisions.log`, and building the message.
- The bid, the order that leaves first, is overstated 1.5× to 2.3× (median) in most scenarios.
- `quiet` has only one such delivery, so its mean equals its median and its std dev is 0.


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
- Reports the count, mean, median and standard deviation of tick-to-trade latency over the orders of the run,
  e.g. for `basic`: `corrected tick-to-trade: 14 orders, mean 1104 ns, median 438 ns, std dev 1740 ns`.

**Result.** The original report's samples vs. the corrected samples (ns; statistics over the deliveries and the orders of one run):

| Scenario | Original: samples per run | Mean | Median | Std dev | Corrected: orders per run | Mean | Median | Std dev |
|---|---|---|---|---|---|---|---|---|
| basic | 54 | 1,991 | 83 | 12,030 | 14 | 1,104 | 438 | 1,740 |
| empty_side | 42 | 2,228 | 42 | 9,188 | 6 | 2,125 | 958 | 2,176 |
| gap | 36 | 2,926 | 42 | 9,890 | 4 | 5,229 | 5,750 | 1,070 |
| loss | 118 | 1,414 | 42 | 5,245 | 21 | 1,192 | 375 | 1,437 |
| position | 117 | 1,042 | 42 | 4,641 | 30 | 958 | 500 | 1,274 |
| quiet | 48 | 1,413 | 42 | 7,631 | 2 | 4,312 | 4,312 | 1,503 |
| sweep | 59 | 1,148 | 42 | 6,501 | 11 | 1,231 | 709 | 1,379 |

### Conclusions

- **The original mostly measures non-trading work.** Its median sample (42 to 83 ns) is a
  delivery that sent nothing; a typical order takes 375 to 5,750 ns.
- **A mean alone is not reliable.** A few slow orders (e.g. the cold first quotes) pull the
  mean tick-to-trade up, so the corrected report also gives the median and standard
  deviation over the orders.
- In `gap`, `quiet` and `sweep` the original reported latency (mean tick-to-trade latency) is
  below the true mean tick-to-trade (diluted by cheap no-order samples); in the other four it is
  above.
---

## 2. Cached top of book

**Files:** `top_of_book/` (the baseline book and the measurement).

### The decision (design doc §2.2.1, "Top of book") and why it is good

- `Requote()` needs the best bid and ask on **every** market data message and exchange
  report, **before** it decides whether to send an order. Reading them is on the hot path.
- The book keeps them in a 32-byte `BookTop` (one 128-byte cache line), updated only when an
  order at or better than the best changes, instead of searching the price ladder for them.
- This is **deliberate denormalization**: a duplicate of exactly the data the hot path reads.
  Carl Cook (CppCon 2017, slide 28): *"denormalized data is not a sin … better than
  trampling your cache."*

### What the experiment does

- **Question:** how much tick-to-trade does the cached top of book save?
- **Baseline:** the same app with the cache removed (`top_of_book/full_scan/`): no `top_`, no
  `RecomputeBest`, and `top()` searches the price ladder on every call (bids from $2,000 down,
  asks from $0 up, each stopping at the first non-empty price level). Nothing else changes.
- **Method:** both versions run every scenario once. For each order, tick-to-trade is the
  tap's send time minus the arrival time of the message that triggered it; mean, median and
  standard deviation are over the orders of the run. Each run's orders are checked against
  `.expected`.

### Results

Tick-to-trade per order, in ns:

| Scenario | Orders in the run | Same orders as `.expected` (both versions) | Cached top of book: mean | Cached: median | Cached: std dev | Full ladder scan: mean | Full scan: median | Full scan: std dev | Full scan slower by (median) |
|---|---|---|---|---|---|---|---|---|---|
| basic | 14 | yes | 1,220 | 458 | 1,978 | 85,922 | 85,958 | 4,335 | 188× |
| empty_side | 6 | yes | 2,403 | 1,208 | 2,315 | 84,466 | 86,230 | 5,736 | 71× |
| gap | 4 | yes | 4,844 | 5,292 | 1,268 | 43,302 | 42,750 | 43,420 | 8× |
| loss | 21 | yes | 1,339 | 458 | 1,564 | 79,911 | 77,250 | 5,319 | 169× |
| position | 30 | yes | 957 | 520 | 1,262 | 79,121 | 77,230 | 4,200 | 149× |
| quiet | 2 | yes | 5,500 | 5,500 | 1,650 | 81,521 | 81,521 | 1,915 | 15× |
| sweep | 11 | yes | 1,246 | 709 | 1,474 | 79,674 | 80,333 | 2,525 | 113× |
| **All scenarios** | **88** | **yes** | **1,505** | **604** | **1,841** | **79,251** | **77,626** | **12,312** | **129×** |

### Why: memory read per top-of-book lookup

| | Cached top of book | Full ladder scan |
|---|---|---|
| Memory read to find the best bid and ask | 32 bytes | ~200,000 price levels × 8 bytes ≈ 1.6 MB |
| 128-byte cache lines touched | 1 | ~12,500 |
| Compared with the 128 KB L1 data cache | negligible | ~12× its size, on every lookup |

### Conclusions

- **The cache changes only speed.** Both versions send exactly the `.expected` orders in all
  7 scenarios.
- **It saves ~77 µs per order.** The median order leaves after 604 ns with the cache and
  77,626 ns with the full scan, about 129× slower, because every scan reads ~1.6 MB before
  the order can be priced.
- **The saving is smaller where orders skip the lookup.** In `gap`, half the orders are the
  halt's cancels, which are sent before the top of book is read; `quiet`'s two orders are its
  cold first quotes, which are slow in both versions.
- **It matches approach adopted by a few other sources:** the QuantCup 1 winning order book also keeps
  `bidMax`/`askMin` over a price-indexed array.
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
with it, and the time elapsed. One run per scenario; times in ns.

Throws in the run (the counts are identical every run):

| Scenario | Book invalid | Position limit | Gap: halt | Ignored while halted | **Total** | Time spent throwing in the run |
|---|---|---|---|---|---|---|
| basic | 2 | – | – | – | **2** | 41,916 |
| empty_side | 9 | – | – | – | **9** | 51,666 |
| gap | 2 | – | 1 | 6 | **9** | 49,291 |
| loss | 10 | 13 | – | 10 | **33** | 110,290 |
| position | 2 | 12 | – | – | **14** | 63,206 |
| quiet | 3 | – | – | – | **3** | 24,458 |
| sweep | 3 | – | – | – | **3** | 22,666 |

Cost of one throw (statistics over the throws of all 7 scenarios):

| Throw | What the catch does | Throws | Mean | Median | Std dev |
|---|---|---|---|---|---|
| First throw of a run (the C++ runtime loads its unwinding tables) | skip tick | 7 | 22,738 | 20,916 | 7,219 |
| Book invalid | skip tick | 24 | 3,276 | 2,938 | 775 |
| Position limit | skip side | 25 | 2,695 | 2,625 | 188 |
| Sequence gap | **halt** | 1 | 4,250 | 4,250 | – (one throw) |
| Sequence gap | ignore (already halted) | 6 | 3,396 | 3,354 | 98 |
| Loss limit | ignore (already halted) | 10 | 3,371 | 3,354 | 82 |

- **73 throws** in one run of the 7 scenarios; **72 of them just return**, only one halts.
- In `gap` and `loss`, about half of all messages throw.
- A throw costs ~3 µs (~21 µs for the first of a run); a typical message is handled in
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

Both versions, one run per scenario; statistics over the messages or orders of that run.
**Both send exactly the `.expected` orders in every scenario.** Times in ns.

**Handler time** per market data message or exchange report (most failed checks happen on
messages that send no order, so this is where their cost shows):

| Scenario | Messages per run | Exceptions: mean | Median | Std dev | Error flags: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|
| basic | 44 | 2,100 | 83 | 11,222 | 384 | 83 | 1,212 |
| empty_side | 22 | 4,102 | 1,042 | 12,203 | 884 | 42 | 3,203 |
| gap | 16 | 6,068 | 4,646 | 12,632 | 547 | 42 | 1,601 |
| loss | 78 | 2,064 | 480 | 5,593 | 208 | 42 | 649 |
| position | 87 | 1,296 | 83 | 6,171 | 213 | 42 | 542 |
| quiet | 28 | 2,217 | 42 | 9,361 | 238 | 42 | 967 |
| sweep | 39 | 2,105 | 83 | 10,076 | 412 | 42 | 1,604 |

**Tick-to-trade** per order:

| Scenario | Orders per run | Exceptions: mean | Median | Std dev | Error flags: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|
| basic | 14 | 1,101 | 416 | 1,695 | 1,432 | 459 | 2,372 |
| empty_side | 6 | 2,063 | 980 | 2,033 | 5,083 | 958 | 6,723 |
| gap | 4 | 4,822 | 5,270 | 1,316 | 2,958 | 2,542 | 3,096 |
| loss | 21 | 1,161 | 417 | 1,278 | 873 | 375 | 1,302 |
| position | 30 | 889 | 500 | 1,117 | 699 | 396 | 899 |
| quiet | 2 | 3,708 | 3,708 | 1,296 | 4,250 | 4,250 | 1,237 |
| sweep | 11 | 1,341 | 708 | 1,628 | 2,163 | 708 | 3,441 |

### Conclusions

- **The design doc's premise fails in practice.** The exceptions are thrown on routine
  messages, 72 of 73 times only to return, at ~3 µs each (~21 µs the first time).
- **Error flags remove that cost without changing a single order.** Mean handler time falls
  5–11× in every scenario and its standard deviation 4–11×; in `gap`, the median falls from
  4,646 ns to 42 ns.
- **Tick-to-trade improves where an order follows a failed check:** the halt's cancels in
  `gap` (median 5,270 → 2,542 ns), and the asks quoted while the bid is blocked in `loss` and
  `position`. Elsewhere no check fails on the way to an order, so it is unchanged within noise.
- Single-run noise: in `empty_side` and `sweep` one slow order raises the error-flags mean
  and std dev, while the medians are unchanged. `quiet` sends only its 2 cold first quotes.

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
