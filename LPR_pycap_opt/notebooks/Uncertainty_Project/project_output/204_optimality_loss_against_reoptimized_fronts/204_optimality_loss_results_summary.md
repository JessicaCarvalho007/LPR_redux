# 204 Results Summary — Optimality Loss Against Re-optimized Fronts

## Purpose

This notebook estimates an approximate optimality loss by comparing fixed baseline-design re-evaluations against original fully re-optimized MOU fronts.

The comparison uses interpolation along each original optimized front so each fixed-design result can be compared to the optimized-front value at approximately the same pumping rate.

## Interpretation of metrics

- Streamflow gap = optimized-front streamflow - fixed-design streamflow.
- Depletion gap = fixed-design depletion - optimized-front depletion.
- Positive values indicate that the fixed baseline design performs worse than the re-optimized front at similar pumping.

## Scenario summary

| Scenario | Comparable designs (%) | Mean streamflow loss (cfs) | Max streamflow loss (cfs) | Mean depletion loss (cfs) | Max depletion loss (cfs) |
|---|---:|---:|---:|---:|---:|
| T −10% | 100.0 | 0.021294 | 0.183040 | 0.021294 | 0.183040 |
| Baseline T | 99.4 | 0.000469 | 0.024309 | 0.000469 | 0.024309 |
| T +10% | 100.0 | 0.014979 | 0.200154 | 0.014979 | 0.200154 |

## Main takeaway

This analysis links the fixed-design T-sensitivity results to the fully re-optimized MOU fronts. If the fixed-design gaps are close to zero, the baseline Pareto designs remain close to optimal even when T changes. If the gaps are larger, that suggests an additional cost of wrongness: the selected baseline designs may no longer represent the best available tradeoff under the corrected transmissivity assumption.

Because this comparison relies on interpolation, it should be interpreted as an approximate optimality-loss diagnostic rather than an exact optimization metric.