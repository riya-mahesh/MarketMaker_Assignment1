Tick-to-trade per order, in ns, over 30 runs of each version.

| Scenario | Orders per run | Same orders as .expected (stored top / full scan) | Stored top: mean | Stored top: median | Full scan: mean | Full scan: median |
|---|---|---|---|---|---|---|
| basic | 14 | yes / yes | 695 | 291 | 50,985 | 51,333 |
| empty_side | 6 | yes / yes | 1,514 | 625 | 51,937 | 51,584 |
| gap | 4 | yes / yes | 3,331 | 2,980 | 29,078 | 29,188 |
| loss | 21 | yes / yes | 843 | 292 | 50,709 | 50,792 |
| position | 30 | yes / yes | 692 | 334 | 51,284 | 51,333 |
| quiet | 2 | yes / yes | 3,453 | 3,167 | 55,698 | 55,062 |
| sweep | 11 | yes / yes | 913 | 458 | 51,363 | 51,208 |
| **All scenarios** | 88 | yes / yes | **995** | **375** | **50,245** | **51,292** |
