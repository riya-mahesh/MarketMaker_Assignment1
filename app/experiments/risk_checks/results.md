Times in ns, over 30 runs of each version.

Tick-to-trade per order

| Scenario | Orders per run | Same orders as .expected | Exceptions (baseline): mean | Exceptions (baseline): median | Return codes: mean | Return codes: median | Cook flags: mean | Cook flags: median |
|---|---|---|---|---|---|---|---|---|
| basic | 14 | yes | 967 | 417 | 1,049 | 417 | 1,034 | 417 |
| empty_side | 6 | yes | 1,931 | 958 | 2,055 | 958 | 2,177 | 979 |
| gap | 4 | yes | 4,290 | 4,500 | 2,325 | 1,480 | 2,378 | 1,562 |
| loss | 21 | yes | 1,219 | 458 | 834 | 375 | 834 | 375 |
| position | 30 | yes | 928 | 542 | 747 | 417 | 763 | 416 |
| quiet | 2 | yes | 5,125 | 4,625 | 4,382 | 4,375 | 4,738 | 4,354 |
| sweep | 11 | yes | 1,425 | 708 | 1,395 | 708 | 1,332 | 709 |

Handler time per market data message and execution report

| Scenario | Messages per run | Same orders as .expected | Exceptions (baseline): mean | Exceptions (baseline): median | Return codes: mean | Return codes: median | Cook flags: mean | Cook flags: median |
|---|---|---|---|---|---|---|---|---|
| basic | 44 | yes | 1,788 | 83 | 294 | 42 | 293 | 83 |
| empty_side | 22 | yes | 4,268 | 1,000 | 409 | 42 | 428 | 42 |
| gap | 16 | yes | 5,911 | 3,375 | 436 | 42 | 445 | 42 |
| loss | 78 | yes | 2,283 | 500 | 209 | 42 | 209 | 42 |
| position | 87 | yes | 1,429 | 83 | 227 | 42 | 229 | 42 |
| quiet | 28 | yes | 2,714 | 42 | 258 | 42 | 267 | 42 |
| sweep | 39 | yes | 2,024 | 42 | 304 | 42 | 298 | 42 |
