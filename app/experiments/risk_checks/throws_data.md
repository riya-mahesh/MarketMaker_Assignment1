Risk-check exceptions per run, and the time from just before `throw` to the start of
the matching catch, in ns, over 30 runs. The first throw of each run is shown
separately because it is much slower (the runtime loads its unwinding tables).

| Scenario | Exception | What the catch does | Throws per run | Median ns per throw |
|---|---|---|---|---|
| basic | (first throw of the run) | | 1 | 23,917 |
| basic | BookInvalid | return:skip tick | 1 | 3,875 |
| empty_side | (first throw of the run) | | 1 | 21,271 |
| empty_side | BookInvalid | return:skip tick | 8 | 2,750 |
| gap | (first throw of the run) | | 1 | 25,020 |
| gap | BookInvalid | return:skip tick | 1 | 3,916 |
| gap | SequenceGap | halt | 1 | 4,104 |
| gap | SequenceGap | return:already halted | 6 | 3,458 |
| loss | (first throw of the run) | | 1 | 24,792 |
| loss | BookInvalid | return:skip tick | 9 | 2,833 |
| loss | LossLimitBreached | return:already halted | 10 | 3,416 |
| loss | PositionLimit | return:side blocked | 13 | 2,709 |
| position | (first throw of the run) | | 1 | 23,104 |
| position | BookInvalid | return:skip tick | 1 | 3,958 |
| position | PositionLimit | return:side blocked | 12 | 2,709 |
| quiet | (first throw of the run) | | 1 | 21,792 |
| quiet | BookInvalid | return:skip tick | 2 | 3,458 |
| sweep | (first throw of the run) | | 1 | 21,521 |
| sweep | BookInvalid | return:skip tick | 2 | 3,500 |

| Scenario | Throws per run | Time spent in throws per run (mean ns) |
|---|---|---|
| basic | 2 | 31,950 |
| empty_side | 9 | 47,317 |
| gap | 9 | 56,722 |
| loss | 33 | 129,849 |
| position | 14 | 64,933 |
| quiet | 3 | 29,311 |
| sweep | 3 | 30,447 |
