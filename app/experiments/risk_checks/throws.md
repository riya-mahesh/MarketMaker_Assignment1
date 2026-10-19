# Risk-check exceptions: how often, how costly, and the fix

## Summary

- The market maker's four risk checks report a failure by **throwing a C++ exception**.
- They fail on ordinary messages, not just in emergencies: **73 throws** across one run
  of the 7 scenarios, and **72 of them simply return** (only one leads to a halt).
- Each throw costs **~3 µs**, and the first one of a run **~19 µs**.
- Replacing the exceptions with plain checks sends **exactly the same orders**, makes
  message handling **6–14× faster on average**, and gets the `gap` halt's cancels out
  **3× sooner**.

## Background: the four checks

`app/risk/risk.h` defines the checks; `app/market_maker.cpp` catches them.

| Check | Fails when | What the app then does |
|---|---|---|
| Book invalid | One side of the book is empty, or bid ≥ ask | Skips this message; quotes stay |
| Position limit | Quoting 100 more shares would pass ±500 | Skips that side; the other side still quotes |
| Sequence gap | A market data message was missed | **Halts** (cancels all orders) the first time; ignores every later message |
| Loss limit | The loss passes $100 (detected on the timer) | Ignores every later message (the halt itself happens without an exception) |

The design doc argues exceptions "are free when not thrown". That's true, but here they
**are** thrown, routinely.

## What we measured

- **Build:** a copy of the app with logging added to `risk.h` and `market_maker.cpp`
  (`instrumented/`). The checks and their outcomes are unchanged.
- **Timed interval:** from **just before `throw`** to **the first line of the `catch`**:
  creating the exception object and unwinding the stack to the handler.
- **Runs:** every scenario 30 times; times are medians.

## How often they're thrown (per run)

| Scenario | Book invalid | Position limit | Gap: halt | Ignored while halted | **Total** | **Time spent throwing** |
|---|---|---|---|---|---|---|
| basic | 2 | – | – | – | **2** | 24 µs |
| empty_side | 9 | – | – | – | **9** | 47 µs |
| gap | 2 | – | 1 | 6 | **9** | 53 µs |
| loss | 10 | 13 | – | 10 | **33** | 115 µs |
| position | 2 | 12 | – | – | **14** | 59 µs |
| quiet | 3 | – | – | – | **3** | 26 µs |
| sweep | 3 | – | – | – | **3** | 26 µs |

- Every scenario throws at least twice at the start, before both sides of the book exist.
- In `loss` and `gap`, about **half of all messages** throw.

## What one throw costs

| Throw | Time per throw |
|---|---|
| First throw of the run (C++ runtime loads its unwinding tables) | 18–20 µs |
| Book invalid | 2.8–4.5 µs |
| Position limit | 2.7–2.8 µs |
| Ignored while halted | 3.4–3.5 µs |
| Gap, leading to the halt | 4.3 µs |

For scale: a typical message is handled in **~0.04 µs**, so one throw costs as much as
handling ~70 messages. These times include some overhead from the logging itself; an
isolated benchmark gives ~2 µs per throw.

## The fixes

Both keep the **same checks, in the same order, with the same outcomes**; only the way
a failure is reported changes.

- **Return codes** (`return_codes/`)
  - Each check **returns** a result (`Ok`, `BookInvalid`, …) instead of throwing.
  - The caller tests it with an ordinary `if`, and returns at once if already halted.
  - `[[nodiscard]]` makes the compiler warn if a result is ignored, which keeps the
    design doc's safety argument that a failure can't be silently skipped.
- **Cook's flags** (`cook_flags/`)
  - From Carl Cook's CppCon 2017 talk (slide 16, "Slowpath removal"): instead of a chain of
    checks, compute one `errorFlags` value and write
    *"if (!errorFlags) sendOrderToExchange(); else HandleError(errorFlags);"*.
  - Here each condition sets **one bit** of a single number, the quoting code makes **one
    branch** on it, and the rare cases go to a separate function that is never inlined
    (Cook: *"ensure that error handling code will not be inlined"*).

## Performance improvement

All three versions, 30 runs each, alternating so machine noise affects them equally.
**All three send exactly the `.expected` orders in every scenario.**
(Full tables: `results.md`.)

**Handler time:** average time to process one market data message or exchange reply.
Most failed checks happen on messages that send no order, so this is where their cost shows.

| Scenario | Exceptions | Return codes | Cook's flags | Faster by |
|---|---|---|---|---|
| basic | 1,788 ns | 294 ns | 293 ns | 6× |
| empty_side | 4,268 ns | 409 ns | 428 ns | 10× |
| gap | 5,911 ns | 436 ns | 445 ns | 14× |
| loss | 2,283 ns | 209 ns | 209 ns | 11× |
| position | 1,429 ns | 227 ns | 229 ns | 6× |
| quiet | 2,714 ns | 258 ns | 267 ns | 11× |
| sweep | 2,024 ns | 304 ns | 298 ns | 7× |

**Tick-to-trade:** median time from a market message arriving to the order it triggered
leaving. It only changes where an order is sent *after* a failed check.

| Scenario | Exceptions | Return codes | Cook's flags | Why it changes |
|---|---|---|---|---|
| gap | 4,500 ns | 1,480 ns | 1,562 ns | The halt's cancels were sent from inside the `catch` |
| position | 542 ns | 417 ns | 416 ns | Asks quoted after the bid side's position check failed |
| loss | 458 ns | 375 ns | 375 ns | Same as `position` |
| basic, empty_side, sweep | unchanged | | | No check fails on the way to an order |

## Takeaways

- The design doc's premise fails in practice: these exceptions are thrown on routine
  messages, and each costs ~3 µs (~19 µs the first time).
- Either fix removes that cost without changing a single order.
- Return codes and Cook's flags measure the same here: nearly all the cost was the
  exception itself. Cook's extra savings (fewer branches, rare code kept out of line) are
  a few nanoseconds, below what this machine's ~42 ns clock and run-to-run noise resolve.

## Reproduce

```sh
sh app/experiments/risk_checks/count_throws.sh   # throw counts and costs -> throws_data.md
sh app/experiments/risk_checks/run.sh            # three versions compared -> results.md
```
