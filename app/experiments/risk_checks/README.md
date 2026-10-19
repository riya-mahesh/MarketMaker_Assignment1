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
