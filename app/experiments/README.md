# Experiments

Measurements supporting the Assignment 1 critique of the market maker. Nothing here
changes what the app trades: `make verify` passes, and every experiment checks that each
version sends exactly the orders in `sim/fixtures/*.expected`.

| # | Experiment | Design decision examined | Result in one line |
|---|---|---|---|
| 1 | [Corrected evaluation](#1-corrected-evaluation) | §2.1 Evaluation (flaw) | The original report takes one end time per delivery and averages deliveries that sent no order; per-order tick-to-trade fixes both |
| 2 | [Cached top of book](#2-cached-top-of-book) | §2.2.1 Top of book (good decision) | Searching the price ladder instead makes the median order ~129× slower |
| 3 | [Risk checks](#3-risk-checks-exceptions-vs-error-flags) | §2.2.3 Risk checks (flaw) | Exceptions are thrown on routine messages; Cook's error flags make message handling 5–13× faster |
| 4 | [Decision log](#4-decision-log-fprintf-vs-binary-record) | §2.2.4 Decision log (flaw) | Formatting a text log line before every `Send` costs ~300 ns per order; a binary record makes median tick-to-trade 3.7× faster |

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
sh app/experiments/risk_checks/run.sh           # 3. exceptions vs. error flags: handler time
sh app/experiments/risk_checks/orders_after_throw.sh  # 3. tick-to-trade of orders sent after a throw
sh app/experiments/decision_log/run.sh          # 4. fprintf vs. binary decision log
```

Each script prints its tables and saves a copy under `build/experiments/`.

---

## 1. Corrected evaluation

**Files** (`evaluation/`): `analysis_corrected.h` (the corrected report, printed after the
original one by every run of `build/market_maker`), `run.sh` + `measure.py` (measurement).

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

### Fix: per-order tick-to-trade (`evaluation/analysis_corrected.h`)

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

**Files** (`risk_checks/`): experiment A `instrumented/`, `count_throws.sh`; the fix
`error_flags/`; experiment B `run.sh`; experiment C `orders_after_throw.sh`.

The **hot path** here is everything from a market message arriving to its order being sent
and the handler finishing, all on the single trading thread.

### The decision under test (design doc §2.2.3)

- Every failed risk check **throws** a `RiskViolation`; `Requote()` or `QuoteSide()` catches
  it to skip the message, block one side, or halt.
- The design doc's argument: exceptions "are free when not thrown, and once they are thrown,
  we are no longer in the hotpath."
- We test the second half. A throw allocates the exception and unwinds the stack to the
  `catch` on the trading thread, before the handler can continue.

| Check | Fails when | The `catch` then |
|---|---|---|
| Book invalid | A side of the book is empty, or bid ≥ ask | Returns: skip this message |
| Position limit | 100 more shares would pass ±500 | Returns: skip that side; the other side still quotes |
| Sequence gap | A market data message was missed | **Halts** the first time; returns on every later message |
| Loss limit | The loss passes $100 (found on the timer) | Returns on every later message |

### Experiment A: how often checks throw, and what one throw costs

- **Setup:** `instrumented/` reads the clock just before each `throw` and again on the first
  line of its `catch`; the log line is printed afterwards, so it is not timed. One run per
  scenario.
- **Metric:** time per throw, i.e. the cost of the exception itself (allocation and
  unwinding), the part the design doc treats as free.

Throws in one run, by check, and the total time spent throwing (ns):

| Scenario | Book invalid | Position limit | Gap: halt | Ignored while halted | Total throws | Time spent throwing |
|---|---|---|---|---|---|---|
| basic | 2 | – | – | – | 2 | 81,000 |
| empty_side | 9 | – | – | – | 9 | 54,124 |
| gap | 2 | – | 1 | 6 | 9 | 66,043 |
| loss | 10 | 13 | – | 10 | 33 | 121,086 |
| position | 2 | 12 | – | – | 14 | 61,418 |
| quiet | 3 | – | – | – | 3 | 41,167 |
| sweep | 3 | – | – | – | 3 | 32,708 |

Cost of one throw, over the throws of all 7 scenarios (ns):

| Throw | Throws | Mean | Median | Std dev |
|---|---|---|---|---|
| First throw of a run (the runtime loads its unwinding tables) | 7 | 33,167 | 26,375 | 17,436 |
| Book invalid | 24 | 3,839 | 3,375 | 1,427 |
| Position limit | 25 | 2,683 | 2,625 | 161 |
| Gap, leading to the halt | 1 | 5,667 | 5,667 | – |
| Ignored while halted (gap) | 6 | 4,417 | 4,646 | 411 |
| Ignored while halted (loss limit) | 10 | 3,400 | 3,354 | 202 |

- **73 throws** across the 7 scenarios; **72 only return**, one halts.
- One throw costs ~3 µs (~26 µs for the first in a run); handling a typical message takes
  ~0.04 µs. In `gap` and `loss` about half of all messages throw.

### The fix: error flags (`error_flags/`)

Carl Cook's "slowpath removal" (CppCon 2017, slide 16): *"if (!errorFlags)
sendOrderToExchange(); else HandleError(errorFlags);"*.

- `RiskGate::Flags()` runs the **same four checks** and sets **one bit per failure**; nothing
  is thrown.
- `Requote()` makes **one branch** on that value; a blocked side is a bit test.
- The rare work (halting) is in `HandleRiskFlags()`, kept out of line (`[[gnu::noinline,
  gnu::cold]]`). Same checks, same order, same outcomes.

### Experiment B: handler time

- **Setup:** the exceptions build and the error-flags build run every scenario once; both
  send exactly the `.expected` orders.
- **Metric:** handler time per market data message or exchange report (tap arrival → end of
  the handler). Most throws happen on messages that send no order, which tick-to-trade cannot
  see; handler time shows how long they keep the hot path busy for the next trade causing a delay.

Handler time (ns):

| Scenario | Messages | Exceptions: mean | Median | Std dev | Error flags: mean | Median | Std dev | Mean faster by |
|---|---|---|---|---|---|---|---|---|
| basic | 44 | 2,192 | 83 | 11,869 | 419 | 83 | 1,449 | 5× |
| empty_side | 22 | 5,585 | 1,125 | 18,388 | 492 | 42 | 1,422 | 11× |
| gap | 16 | 7,700 | 3,417 | 20,620 | 612 | 42 | 2,074 | 13× |
| loss | 78 | 3,065 | 458 | 9,389 | 257 | 42 | 1,018 | 12× |
| position | 87 | 1,666 | 83 | 9,266 | 247 | 42 | 734 | 7× |
| quiet | 28 | 3,333 | 42 | 14,752 | 326 | 42 | 1,391 | 10× |
| sweep | 39 | 2,409 | 42 | 11,829 | 323 | 42 | 941 | 7× |

### Experiment C: tick-to-trade of the orders sent after a throw

- **Why:** an order sent in the same handler after a throw waits for it: the ask after a
  failed position check (`loss`, `position`), and the halt's cancels, sent from inside the
  `catch` (`gap`). Over all orders this cost is diluted, so these orders are measured alone.
- **Setup:** the instrumented build labels each order "after a throw" or not (a flag cleared
  at the start of every handler and set by any `catch`). Both timed builds send the same orders
  in the same sequence, so the labels carry over. The labelling build is never timed.
- **Metric:** tick-to-trade per labelled order (tap arrival → order sent).

Orders sent after a throw in the same handler (ns):

| Scenario | Such orders | Exceptions: mean | Median | Std dev | Error flags: mean | Median | Std dev | Saved: mean | Saved: median |
|---|---|---|---|---|---|---|---|---|---|
| gap | 2 | 4,396 | 4,396 | 147 | 292 | 292 | 59 | 4,104 | 4,104 |
| loss | 3 | 3,125 | 3,083 | 72 | 305 | 292 | 24 | 2,819 | 2,791 |
| position | 2 | 3,104 | 3,104 | 29 | 416 | 416 | 59 | 2,688 | 2,688 |

Control: orders with no throw before them in their handler show no consistent difference
(e.g. `loss`: median 375 ns in both versions).

### Conclusions: why throwing on risk failures is the wrong design

- **The throws are routine, not exceptional.** 72 of 73 are ordinary outcomes (the book is not
  yet two-sided, the position is at its limit, the app is already halted) that end in a plain
  `return`. That is using exceptions for control flow, which Cook warns against (slide 22).
- **"No longer in the hotpath" is false.** Unwinding runs on the trading thread before it can
  continue, so the hot path pays for it in two ways:
  - **Orders wait:** an order sent after a throw takes ~2.7–4.1 µs instead of ~0.3–0.4 µs
    (7–15× slower).
  - **Messages wait:** a throwing message keeps the handler busy ~3 µs instead of ~0.04 µs;
    mean handler time is 5–13× higher, so in a live market the next tick, possibly one that
    should trade, would queue behind it (the simulator delivers back to back, so this wait is
    not measured here).
- **The safety argument does not need exceptions.** Error flags run the same checks with the
  same outcomes (identical orders in every scenario), keep every failure explicit in one
  branch, and move the rare halt code out of line.

---

## 4. Decision log: fprintf vs. binary record

**Files** (`decision_log/`): the fix `deferred/`; the log-write timing `timed/`; `run.sh` +
`measure.py` (measurement).

### The decision under test (design doc §2.2.4)

- Every order is written to `decisions.log` **before** it is sent, so that if the process dies
  mid-send the log still shows what we intended to have on the exchange ("write-ahead").
- `OrderManager::SendQuote()` does this with `fprintf`: it formats a text line (time, action,
  side, price, shares, token) and copies it into the C library's file buffer, then calls
  `Send`.

### Flaw: slow work on the hot path, before every order

- Formatting numbers into text and going through stdio sits between the market message and
  the order leaving, on **every** order. With a bid and an ask, the ask also waits for the
  bid's log line.
- The write-ahead rule only needs the record to exist before `Send`, not the formatted text.

### Fix: binary record, formatted at shutdown (`deferred/`)

- `Record()` appends a small fixed-size binary entry (time, action, side, price, shares,
  token) to a buffer reserved at startup: a few stores, no formatting, no stdio.
- The entries are formatted into exactly the same text when the log is closed at the end of
  the run, so `decisions.log` is byte-for-byte unchanged, and each order is still recorded
  before it is sent.
- This is the core of how production trading systems log (e.g. NanoLog, Quill): record raw
  values on the hot path, format later. Cook (slide 54): *"Do expensive work only when you
  have spare time."*

### Experiments

- **Setup:** the original build and the fixed build run every scenario once. Both send exactly
  the `.expected` orders, and their `decisions.log` files are identical in every scenario.
- **Metrics** (ns; mean, median and std dev over the run's log writes or orders):
  - **Cost of one log write:** clock reads just before and just after `log_.Record()` in a
    separate timed build of each version (`timed/`); the result is printed afterwards, so the
    printing is not timed.
  - **Tick-to-trade** per order (tap arrival → order sent). Every order is logged before it is
    sent, so all orders are affected.

Cost of one decision-log write:

| Scenario | Writes | fprintf: mean | Median | Std dev | Binary record: mean | Median | Std dev |
|---|---|---|---|---|---|---|---|
| basic | 14 | 536 | 292 | 776 | 131 | 42 | 358 |
| empty_side | 6 | 1,125 | 458 | 1,738 | 312 | 41 | 705 |
| gap | 2 | 2,229 | 2,229 | 2,210 | 833 | 833 | 1,120 |
| loss | 20 | 423 | 292 | 522 | 90 | 20 | 313 |
| position | 30 | 369 | 292 | 363 | 68 | 0 | 271 |
| quiet | 2 | 1,480 | 1,480 | 1,266 | 896 | 896 | 1,267 |
| sweep | 11 | 549 | 333 | 638 | 174 | 0 | 523 |

Tick-to-trade:

| Scenario | Orders | fprintf: mean | Median | Std dev | Binary record: mean | Median | Std dev | Median faster by |
|---|---|---|---|---|---|---|---|---|
| basic | 14 | 1,310 | 416 | 2,194 | 458 | 84 | 868 | 5.0× |
| empty_side | 6 | 3,986 | 1,062 | 4,868 | 1,021 | 312 | 1,255 | 3.4× |
| gap | 4 | 5,188 | 4,688 | 1,071 | 3,583 | 3,854 | 1,088 | 1.2× |
| loss | 21 | 1,298 | 417 | 1,569 | 907 | 125 | 1,543 | 3.3× |
| position | 30 | 922 | 520 | 1,189 | 469 | 84 | 941 | 6.2× |
| quiet | 2 | 4,104 | 4,104 | 1,503 | 3,958 | 3,958 | 3,065 | 1.0× |
| sweep | 11 | 1,379 | 666 | 1,737 | 515 | 208 | 794 | 3.2× |
| **All scenarios** | **88** | **1,606** | **625** | **2,205** | **836** | **167** | **1,387** | **3.7×** |

- Cancels are not logged by the app, so `gap` (2 halt cancels) and `loss` (1) have fewer
  writes than orders.

### Conclusions: why formatting the log before `Send` is the wrong design

- **It puts the slowest step right before the order.** A typical `fprintf` log write takes
  ~290–460 ns (median), comparable to the whole tick-to-trade of a typical order.
- **The write-ahead goal doesn't need it.** A binary record taken before `Send` keeps the same
  guarantee and the same final log, at ≤ ~40 ns (below this machine's ~42 ns clock step).
- **Orders leave much sooner:** median tick-to-trade falls from 625 ns to 167 ns over all
  orders (3.7×), and 3–6× in every scenario where orders are not just cold first quotes
  (`quiet`) or unlogged halt cancels (`gap`). The saving exceeds the write itself, since
  `fprintf` also displaces the hot path's code and data from the CPU caches.

---

## Sources

- STAC-T1.EMINI overview (tick-to-trade definition):
  https://docs.stacresearch.com/system/files/central/t1_emini_overview.pdf
- Carl Cook, "When a Microsecond Is an Eternity: High Performance Trading Systems in C++",
  CppCon 2017 (slide 16: "Slowpath removal"; slide 22: exceptions are "zero cost if they
  don't throw" but "don't use exceptions for control flow"; slide 28: "denormalized data is
  not a sin"; slide 52: measure end to end; slide 54: "do expensive work only when you have
  spare time"):
  https://isocpp.org/blog/2018/09/cppcon-2017-when-a-microsecond-is-an-eternity-high-performance-trading-syst
- QuantCup 1 winning matching engine, which tracks `askMin`/`bidMax` over a price-indexed
  array: https://gist.github.com/2855852
- Yang, Park & Ousterhout, "NanoLog: A Nanosecond Scale Logging System", USENIX ATC 2018
  (binary log records on the hot path, formatted offline):
  https://www.usenix.org/conference/atc18/presentation/yang-stephen
- Quill, an asynchronous low-latency C++ logger (raw arguments queued on the hot path,
  formatted by a backend thread): https://quillcpp.readthedocs.io/en/latest/overview.html
