# 302a Transmissivity Probability-Weighted Uncertainty Summary

## Purpose

This notebook evaluates the probability-weighted hydrologic cost of uncertainty in Transmissivity for the baseline depletion-q Pareto pumping designs.

The baseline pumping designs are held fixed. Only Transmissivity is varied across a discrete normal probability distribution.

## Probability model

- Parameter: Transmissivity
- Baseline value: 1700.0
- Sigma fraction: 0.1
- Number of sigma each side: 2.0
- Number of sampled values: 11
- Minimum factor: 0.800000
- Maximum factor: 1.200000

## Headline results

| Metric | Value (cfs) |
|---|---:|
| Mean probability-weighted absolute streamflow error | 0.126483 |
| Max probability-weighted absolute streamflow error | 0.180805 |
| Mean probability-weighted streamflow shortfall | 0.061058 |
| Max probability-weighted streamflow shortfall | 0.086471 |
| Mean streamflow standard deviation | 0.157468 |
| Max streamflow standard deviation | 0.225241 |

## Interpretation guide

The absolute streamflow error measures the expected magnitude of uncertainty regardless of direction.

The streamflow shortfall metric is one-sided and management-focused. It counts only cases where the uncertain-parameter prediction gives lower streamflow than the baseline-parameter prediction.
