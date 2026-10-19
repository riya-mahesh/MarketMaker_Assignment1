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
