Risk-check exceptions per run, and the time from just before `throw` to the start of
the matching catch, in ns, over 30 runs. The first throw of each run is shown
separately because it is much slower (the runtime loads its unwinding tables).

| Scenario | Exception | What the catch does | Throws per run | Median ns per throw |
|---|---|---|---|---|
| basic | (first throw of the run) | | 1 | 19,188 |
| basic | BookInvalid | return:skip tick | 1 | 3,917 |
| empty_side | (first throw of the run) | | 1 | 19,896 |
| empty_side | BookInvalid | return:skip tick | 8 | 2,875 |
| gap | (first throw of the run) | | 1 | 19,812 |
| gap | BookInvalid | return:skip tick | 1 | 4,458 |
| gap | SequenceGap | halt | 1 | 4,250 |
| gap | SequenceGap | return:already halted | 6 | 3,500 |
| loss | (first throw of the run) | | 1 | 19,770 |
| loss | BookInvalid | return:skip tick | 9 | 2,792 |
| loss | LossLimitBreached | return:already halted | 10 | 3,375 |
| loss | PositionLimit | return:side blocked | 13 | 2,667 |
| position | (first throw of the run) | | 1 | 18,042 |
| position | BookInvalid | return:skip tick | 1 | 3,583 |
| position | PositionLimit | return:side blocked | 12 | 2,792 |
| quiet | (first throw of the run) | | 1 | 19,042 |
| quiet | BookInvalid | return:skip tick | 2 | 3,438 |
| sweep | (first throw of the run) | | 1 | 18,875 |
| sweep | BookInvalid | return:skip tick | 2 | 3,354 |

| Scenario | Throws per run | Time spent in throws per run (mean ns) |
|---|---|---|
| basic | 2 | 23,876 |
| empty_side | 9 | 46,579 |
| gap | 9 | 52,539 |
| loss | 33 | 114,996 |
| position | 14 | 59,417 |
| quiet | 3 | 26,344 |
| sweep | 3 | 26,092 |
