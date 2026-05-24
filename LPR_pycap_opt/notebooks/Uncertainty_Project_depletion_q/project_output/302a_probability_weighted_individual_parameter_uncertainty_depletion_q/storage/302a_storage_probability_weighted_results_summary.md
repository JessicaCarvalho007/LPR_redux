# 302a Storage Probability-Weighted Uncertainty Summary

## Purpose

This notebook evaluates the probability-weighted hydrologic cost of uncertainty in Storage for the baseline depletion-q Pareto pumping designs.

The baseline pumping designs are held fixed. Only Storage is varied across a discrete normal probability distribution.

## Probability model

- Parameter: Storage
- Baseline value: 0.12
- Sigma fraction: 0.1
- Number of sigma each side: 2.0
- Number of sampled values: 11
- Minimum factor: 0.800000
- Maximum factor: 1.200000

## Headline results

| Metric | Value (cfs) |
|---|---:|
| Mean probability-weighted absolute streamflow error | 0.127274 |
| Max probability-weighted absolute streamflow error | 0.181505 |
| Mean probability-weighted streamflow shortfall | 0.068723 |
| Max probability-weighted streamflow shortfall | 0.097197 |
| Mean streamflow standard deviation | 0.159180 |
| Max streamflow standard deviation | 0.226763 |

## Interpretation guide

The absolute streamflow error measures the expected magnitude of uncertainty regardless of direction.

The streamflow shortfall metric is one-sided and management-focused. It counts only cases where the uncertain-parameter prediction gives lower streamflow than the baseline-parameter prediction.
