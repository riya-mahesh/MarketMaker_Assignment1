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
