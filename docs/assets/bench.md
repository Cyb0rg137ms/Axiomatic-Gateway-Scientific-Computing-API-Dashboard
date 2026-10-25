| problem | expected | v1 answer | v1 ms | v2 status | verified | v2 ms |
|---|---|---|---|---|---|---|
| syllogism | proved | proved | 0.06 | proved | True | 0.22 |
| modus_ponens | proved | proved | 0.04 | proved | True | 0.16 |
| needs_factoring | proved | not proved ✗ | 0.04 | proved | True | 0.4 |
| transitivity_chain | proved | not proved ✗ | 0.47 | proved | True | 36.75 |
| peano_s0_ne_0 | proved | proved | 0.07 | proved | True | 0.16 |
| peano_ss0_ne_s0 | proved | proved | 0.25 | proved | True | 0.57 |
| zfc_empty_has_no_members | proved | proved | 3.08 | proved | True | 0.27 |
| drinker_style_non_theorem | saturated | proved ✗ | 0.01 | saturated | None | 0.04 |
| satisfiable_set | saturated | not proved | 0.15 | saturated | None | 0.15 |
| php_3_2 | proved | proved | 24.07 | proved | True | 5.55 |
| php_4_3 | proved | not proved ✗ | 6524.58 | proved | True | 752.59 |
| php_5_4 | proved | not proved ✗ | 14657.46 | unknown (budget) | None | 10008.49 |

| n | m | SAT/instances | median ms | max ms |
|---|---|---|---|---|
| 20 | 85 | 7/10 | 0.52 | 0.81 |
| 30 | 128 | 7/10 | 1.53 | 2.61 |
| 40 | 170 | 6/10 | 3.91 | 8.33 |
| 50 | 213 | 8/10 | 7.99 | 22.73 |

/prove latency (in-process TestClient, 200 reps): cold p50 3.5 ms / p95 4.706 ms; cache hit p50 2.804 ms / p95 3.575 ms
