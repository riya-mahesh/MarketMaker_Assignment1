# Risk-check exceptions: how often, how costly, and the fix

## Summary

- The market maker's four risk checks report a failure by **throwing a C++ exception**.
- They fail on ordinary messages, not just in emergencies: **73 throws** across one run
  of the 7 scenarios, and **72 of them simply return** (only one leads to a halt).
- Each throw costs **~3 µs**, and the first one of a run **~19 µs**.
- Replacing the exceptions with **error flags** (Carl Cook's "slowpath removal") sends
  **exactly the same orders**, makes message handling **5–12× faster on average**, and
  gets the `gap` halt's cancels out **~3× sooner**.

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

## The fix: error flags

From Carl Cook's CppCon 2017 talk (slide 16, "Slowpath removal"): instead of handling each
error where it's found, collect all of them into one `errorFlags` value and write
*"if (!errorFlags) sendOrderToExchange(); else HandleError(errorFlags);"*, keeping the error
handler out of line (*"ensure that error handling code will not be inlined"*).

In `cook_flags/`:

- **One number for all checks.** `RiskGate::Flags()` evaluates the same four conditions and
  sets **one bit** per failure (book invalid, sequence gap, loss limit, buy blocked, sell blocked).
- **One branch on the quoting path.** `Requote()` tests that number once; if nothing is set,
  it quotes as before. The two position checks become two bit tests.
- **Rare cases out of line.** Halting and "nothing to do" go to `HandleRiskFlags()`, marked
  never-inline and cold, so it stays out of the quoting code.
- **Same behaviour.** Same checks, same order, same outcomes; nothing is thrown.

## Performance improvement

Both versions, 30 runs each, alternating so machine noise affects them equally.
**Both send exactly the `.expected` orders in every scenario.** (Full tables: `results.md`.)

**Handler time:** average time to process one market data message or exchange reply.
Most failed checks happen on messages that send no order, so this is where their cost shows.

| Scenario | Exceptions | Error flags | Faster by |
|---|---|---|---|
| basic | 1,914 ns | 346 ns | 5.5× |
| empty_side | 4,662 ns | 503 ns | 9.3× |
| gap | 6,661 ns | 578 ns | 11.5× |
| loss | 2,409 ns | 234 ns | 10.3× |
| position | 1,566 ns | 264 ns | 5.9× |
| quiet | 3,139 ns | 317 ns | 9.9× |
| sweep | 2,399 ns | 350 ns | 6.9× |

**Tick-to-trade:** median time from a market message arriving to the order it triggered
leaving. It only changes where an order is sent *after* a failed check.

| Scenario | Exceptions | Error flags | Why it changes |
|---|---|---|---|
| gap | 4,604 ns | 1,646 ns | The halt's cancels were sent from inside the `catch` |
| position | 583 ns | 438 ns | Asks quoted after the bid side's position check failed |
| loss | 458 ns | 375 ns | Same as `position` |
| basic, empty_side, sweep, quiet | unchanged | | No check fails on the way to an order |

## Takeaways

- The design doc's premise fails in practice: these exceptions are thrown on routine
  messages, and each costs ~3 µs (~19 µs the first time).
- Cook's error flags remove that cost without changing a single order: message handling is
  5–12× faster on average, and orders sent after a failed check leave sooner.

## Reproduce

```sh
sh app/experiments/risk_checks/count_throws.sh   # throw counts and costs -> throws_data.md
sh app/experiments/risk_checks/run.sh            # exceptions vs. error flags -> results.md
```
