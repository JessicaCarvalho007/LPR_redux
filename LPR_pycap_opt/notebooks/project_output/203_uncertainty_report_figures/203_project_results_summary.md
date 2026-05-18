# 203 Project Results Summary — Transmissivity Uncertainty

## What was evaluated

The baseline `fish_dollars` Pareto-front designs were held fixed and re-evaluated hydrologically using PyCap. The main evaluation metrics were:

- effective total pumping, in cfs
- streamflow depletion, in cfs
- streamflow, calculated as 8.6 cfs minus depletion

## Known T error: +/-10%

| Scenario | T value | Mean streamflow (cfs) | Mean depletion (cfs) | Mean streamflow change from baseline (cfs) | Max absolute streamflow error (cfs) |
|---|---:|---:|---:|---:|---:|
| T -10% | 1530.0 | 6.055205 | 2.544795 | 0.160708 | 0.254155 |
| Baseline T | 1700.0 | 5.894497 | 2.705503 | 0.000000 | 0.000000 |
| T +10% | 1870.0 | 5.743844 | 2.856156 | -0.150653 | 0.235821 |

Interpretation: increasing transmissivity increased depletion and lowered streamflow; decreasing transmissivity reduced depletion and increased streamflow.

## Unknown T uncertainty: probability-weighted results

Assuming T follows a normal distribution centered on the baseline value, the probability-weighted results were:

- mean probability-weighted absolute streamflow error: 0.114961 cfs
- max probability-weighted absolute streamflow error: 0.180857 cfs
- mean probability-weighted streamflow shortfall: 0.055357 cfs
- max probability-weighted streamflow shortfall: 0.086574 cfs
- mean streamflow standard deviation across designs: 0.143166 cfs
- max streamflow standard deviation across designs: 0.225284 cfs

The streamflow shortfall metric is one-sided. It only counts cases where uncertain T produces less streamflow than the baseline-T prediction. This is useful because lower-than-expected streamflow is the management risk.

## Files created by Notebook 203

- `203_compact_results_summary.csv`
- `203_representative_designs.csv`
- `203_known_T_error_pumping_vs_streamflow.png`
- `203_probability_weighted_expected_streamflow_band.png`
- `203_probability_weighted_streamflow_shortfall.png`
- `203_probability_weighted_absolute_streamflow_error.png`
- `203_T_probability_weights.png`
- `203_project_results_summary.md`
