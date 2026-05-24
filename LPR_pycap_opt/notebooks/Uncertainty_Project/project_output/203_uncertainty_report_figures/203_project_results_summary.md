# Project Results Summary — Transmissivity Uncertainty

## Purpose of the analysis

This analysis evaluates how uncertainty in transmissivity (T) affects the hydrologic performance of baseline Pareto-front pumping designs from the fish-dollars PyCap optimization.

The main hydrologic metrics are:

- Total pumping, expressed as effective pumping after the fish-dollars cutoff rule.
- Depletion, represented by `lpr:total_combined:bdpl`.
- Streamflow, calculated as streamflow = 8.6 cfs - depletion.

The analysis is separated into two related questions:

1. Known T error: What happens if T is actually 10% lower or 10% higher than the baseline value?
2. Unknown T uncertainty: What is the probability-weighted streamflow cost when T is treated as uncertain?

---

## Fixed baseline Pareto designs under known T error

The baseline fish-dollars Pareto-front designs were held fixed and re-evaluated hydrologically under alternate transmissivity assumptions.

| Scenario | T value | Mean streamflow (cfs) | Mean depletion (cfs) | Mean streamflow change from baseline (cfs) | Max absolute streamflow error (cfs) |
|---|---:|---:|---:|---:|---:|
| T -10% | 1530.0 | 6.055205 | 2.544795 | 0.160708 | 0.254155 |
| Baseline T | 1700.0 | 5.894497 | 2.705503 | 0.000000 | 0.000000 |
| T +10% | 1870.0 | 5.743844 | 2.856156 | -0.150653 | 0.235821 |

### Interpretation

For the fixed baseline Pareto designs, the direction of the T effect is consistent:

- Lower T (-10%) produced less depletion and higher streamflow.
- Higher T (+10%) produced more depletion and lower streamflow.

This means that, for this model setup, assuming the baseline T when the true T is higher would tend to overestimate streamflow and underestimate depletion. That is the more management-relevant risk direction because it makes the stream appear less impacted than it would be under the higher-T assumption.

The mean baseline streamflow across the fixed designs was 5.894497 cfs, with mean depletion of 2.705503 cfs. Relative to that baseline:

- T -10% changed mean streamflow by 0.160708 cfs.
- T +10% changed mean streamflow by -0.150653 cfs.

The maximum absolute streamflow errors were:

- 0.254155 cfs for T -10%.
- 0.235821 cfs for T +10%.

---

## Probability-weighted unknown T uncertainty

The unknown-T analysis treated transmissivity as a discrete normal probability model centered on the baseline T value. Each baseline Pareto design was re-evaluated across sampled T values, and the resulting streamflow values were weighted by the probability assigned to each T value.

| Metric | Value (cfs) |
|---|---:|
| Mean probability-weighted absolute streamflow error | 0.114961 |
| Max probability-weighted absolute streamflow error | 0.180857 |
| Mean probability-weighted streamflow shortfall | 0.055357 |
| Max probability-weighted streamflow shortfall | 0.086574 |
| Mean streamflow standard deviation | 0.143166 |
| Max streamflow standard deviation | 0.225284 |

### Interpretation

The probability-weighted absolute streamflow error represents the expected magnitude of streamflow error caused by uncertainty in T. It treats streamflow being too high or too low as equally important.

The probability-weighted streamflow shortfall is more conservative and management-focused. It only counts cases where uncertain T produces lower streamflow than the baseline-T prediction. This is useful because lower-than-expected streamflow is the risk direction most relevant to ecological flow protection.

The probability-weighted results show that T uncertainty introduces a measurable but relatively bounded amount of streamflow uncertainty across the baseline Pareto designs. The largest uncertainty costs occur where the design is most sensitive to T, rather than being uniform across the full Pareto front.

---

## Original MOU front comparison

Original 05_MOU tradeoff fronts were loaded for: original_baseline, original_T_minus_10pct, original_T_plus_10pct. These represent fully re-optimized Pareto fronts under each T scenario. In contrast, the fixed-design re-evaluations hold the baseline Pareto-front pumping designs constant and only change T during re-evaluation.

The original-front comparison and fixed-design re-evaluation answer different questions:

- Fixed-design re-evaluation: What happens to the already-selected baseline Pareto designs if T is wrong?
- Original MOU comparison: How does the optimized tradeoff front move when the model is re-optimized under a different T?

This distinction matters. If the fixed baseline designs plot far from the re-optimized front for the same T scenario, that indicates potential optimality loss or cost of wrongness. In other words, the selected design can still be evaluated under the corrected T value, but it may no longer represent the best tradeoff under that corrected T assumption.

---

## Main finding

The main finding is that transmissivity uncertainty affects the predicted streamflow/depletion tradeoff even when pumping designs are held fixed. Higher transmissivity tends to increase depletion and reduce streamflow for the same baseline Pareto designs. Therefore, uncertainty in T can create both hydrologic prediction error and management risk, especially when the baseline design is evaluated under a T value that differs from the true system behavior.

The probability-weighted analysis extends this by summarizing uncertainty across a distribution of possible T values, rather than only evaluating the two known-error cases. This provides a compact way to describe the expected cost of T uncertainty for each Pareto-front design.
