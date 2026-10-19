Times in ns, over 30 runs of each version.

Tick-to-trade per order

| Scenario | Orders per run | Same orders as .expected | Exceptions (baseline): mean | Exceptions (baseline): median | Error flags (fix): mean | Error flags (fix): median |
|---|---|---|---|---|---|---|
| basic | 14 | yes | 1,005 | 417 | 1,085 | 458 |
| empty_side | 6 | yes | 1,997 | 917 | 2,256 | 1,000 |
| gap | 4 | yes | 4,534 | 4,459 | 2,524 | 1,458 |
| loss | 21 | yes | 1,240 | 458 | 892 | 375 |
| position | 30 | yes | 948 | 542 | 780 | 417 |
| quiet | 2 | yes | 4,842 | 4,376 | 4,874 | 4,729 |
| sweep | 11 | yes | 1,347 | 667 | 1,393 | 709 |

Handler time per market data message and execution report

| Scenario | Messages per run | Same orders as .expected | Exceptions (baseline): mean | Exceptions (baseline): median | Error flags (fix): mean | Error flags (fix): median |
|---|---|---|---|---|---|---|
| basic | 44 | yes | 1,752 | 83 | 305 | 83 |
| empty_side | 22 | yes | 4,238 | 980 | 443 | 42 |
| gap | 16 | yes | 6,247 | 3,416 | 461 | 42 |
| loss | 78 | yes | 2,273 | 459 | 218 | 42 |
| position | 87 | yes | 1,406 | 83 | 235 | 42 |
| quiet | 28 | yes | 2,589 | 42 | 273 | 42 |
| sweep | 39 | yes | 1,996 | 42 | 306 | 42 |
