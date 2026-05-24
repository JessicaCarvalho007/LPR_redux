# depletion_q Transmissivity Uncertainty Summary

## Purpose

This workflow evaluates how uncertainty in transmissivity affects the `depletion_q` Pareto designs for the Little Plover River model. The baseline pumping plans were optimized using the baseline transmissivity assumption, then those same pumping plans were re-evaluated under changed transmissivity values.

The main hydrologic relationship is:

streamflow = 8.6 cfs - depletion

## Baseline validation

Notebook 300 confirmed that the depletion-q baseline re-evaluation reproduces the archived objective space.

- Members attempted: 296
- Members successful: 296
- Hydrologic validation passed: True
- Maximum pumping-objective difference: NA cfs
- Maximum depletion difference: 4.972497019251065e-06 cfs

## Known transmissivity error

For the fixed baseline Pareto designs:

| Scenario | Mean streamflow (cfs) | Mean depletion (cfs) | Mean streamflow change from baseline (cfs) | Max absolute streamflow error (cfs) |
|---|---:|---:|---:|---:|
| T -10% | 6.027578 | 2.572422 | 0.176498 | 0.254079 |
| Baseline T | 5.851079 | 2.748921 | 0.000000 | 0.000000 |
| T +10% | 5.684937 | 2.915063 | -0.166142 | 0.235623 |

Interpretation: the known-error analysis shows how the baseline pumping plans perform if the true transmissivity is lower or higher than assumed during optimization. The sign of the streamflow change indicates whether the alternate transmissivity assumption increases or decreases predicted Little Plover streamflow for the same pumping plans.

## Probability-weighted transmissivity uncertainty

The probability-weighted analysis treats transmissivity as a normally distributed uncertain parameter centered on the baseline value.

| Metric | Value (cfs) |
|---|---:|
| Mean probability-weighted absolute streamflow error | 0.126483 |
| Max probability-weighted absolute streamflow error | 0.180805 |
| Mean probability-weighted streamflow shortfall | 0.061058 |
| Max probability-weighted streamflow shortfall | 0.086471 |
| Mean streamflow standard deviation | 0.157468 |
| Max streamflow standard deviation | 0.225241 |

The absolute streamflow error measures the expected magnitude of error from uncertain transmissivity. The streamflow shortfall metric is more management-focused because it counts only the cases where uncertainty produces lower streamflow than the baseline prediction.

## Main working conclusion

The depletion-q version of the workflow now directly evaluates the tradeoff between pumping and Little Plover depletion/streamflow. This is cleaner than the earlier fish-dollars objective because the Pareto front is aligned with the hydrologic question. The current results provide a validated baseline, a known-error transmissivity test, and a probability-weighted transmissivity uncertainty analysis.
