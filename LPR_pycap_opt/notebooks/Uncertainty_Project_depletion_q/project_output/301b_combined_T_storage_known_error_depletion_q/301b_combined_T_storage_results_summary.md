# 301b Combined T/S Known-Error Interaction Summary

## Purpose

This notebook evaluated how the baseline depletion-q Pareto pumping designs respond when transmissivity (T) and storage (S) are perturbed together.

The goal is to determine whether the combined T/S response is approximately additive or whether there is an interaction effect.

## Combined scenario results

| Scenario | T factor | S factor | Mean streamflow change (cfs) | Max absolute streamflow error (cfs) | Mean streamflow shortfall (cfs) |
|---|---:|---:|---:|---:|---:|
| T +10%, S +10% | 1.1 | 1.1 | -0.000000 | 0.000000 | 0.000000 |
| T +10%, S -10% | 1.1 | 0.9 | -0.356789 | 0.501979 | 0.356789 |
| T -10%, S +10% | 0.9 | 1.1 | 0.329571 | 0.477856 | 0.000000 |
| T -10%, S -10% | 0.9 | 0.9 | -0.000000 | 0.000000 | 0.000000 |
| Baseline T, baseline S | 1.0 | 1.0 | 0.000000 | 0.000000 | 0.000000 |

## Interaction analysis

Interaction effect is calculated as:

interaction effect = combined streamflow change - (T-only streamflow change + S-only streamflow change)

| Scenario | Mean combined streamflow change (cfs) | Mean additive expected change (cfs) | Mean interaction effect (cfs) | Max abs interaction effect (cfs) |
|---|---:|---:|---:|---:|
| T +10%, S +10% | -0.000000 | -0.006152 | 0.006152 | 0.007390 |
| T +10%, S -10% | -0.356789 | -0.350156 | -0.006633 | 0.007904 |
| T -10%, S +10% | 0.329571 | 0.336489 | -0.006918 | 0.008304 |
| T -10%, S -10% | -0.000000 | -0.007516 | 0.007516 | 0.009030 |

## Interpretation guide

- Interaction near zero means T and S effects are mostly additive.
- Positive interaction means the combined case gives higher streamflow than the additive expectation.
- Negative interaction means the combined case gives lower streamflow than the additive expectation, which is the management-risk direction.

## Main use

This notebook helps connect parameter uncertainty to robust decision-making. If the worst combined T/S cases produce substantially larger streamflow shortfalls than either parameter alone, then a robust pumping plan should be evaluated under combined uncertainty, not only one-parameter-at-a-time uncertainty.
