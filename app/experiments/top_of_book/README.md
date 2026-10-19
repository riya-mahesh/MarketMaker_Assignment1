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
