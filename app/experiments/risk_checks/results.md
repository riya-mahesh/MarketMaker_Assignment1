Times in ns, over 30 runs of each version.

Tick-to-trade per order

| Scenario | Orders per run | Same orders as .expected | Exceptions (baseline): mean | Exceptions (baseline): median | Error flags (fix): mean | Error flags (fix): median |
|---|---|---|---|---|---|---|
| basic | 14 | yes | 1,128 | 458 | 1,241 | 458 |
| empty_side | 6 | yes | 2,141 | 959 | 2,459 | 1,000 |
| gap | 4 | yes | 4,926 | 4,604 | 3,144 | 1,646 |
| loss | 21 | yes | 1,319 | 458 | 970 | 375 |
| position | 30 | yes | 1,052 | 583 | 888 | 438 |
| quiet | 2 | yes | 5,939 | 5,188 | 5,558 | 5,500 |
| sweep | 11 | yes | 1,548 | 709 | 1,573 | 750 |

Handler time per market data message and execution report

| Scenario | Messages per run | Same orders as .expected | Exceptions (baseline): mean | Exceptions (baseline): median | Error flags (fix): mean | Error flags (fix): median |
|---|---|---|---|---|---|---|
| basic | 44 | yes | 1,914 | 83 | 346 | 83 |
| empty_side | 22 | yes | 4,662 | 1,000 | 503 | 42 |
| gap | 16 | yes | 6,661 | 3,375 | 578 | 42 |
| loss | 78 | yes | 2,409 | 480 | 234 | 42 |
| position | 87 | yes | 1,566 | 83 | 264 | 42 |
| quiet | 28 | yes | 3,139 | 42 | 317 | 42 |
| sweep | 39 | yes | 2,399 | 42 | 350 | 42 |
