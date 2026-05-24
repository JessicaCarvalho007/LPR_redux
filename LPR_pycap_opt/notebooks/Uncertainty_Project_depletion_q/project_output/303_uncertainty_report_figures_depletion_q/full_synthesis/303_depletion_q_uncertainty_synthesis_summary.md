# 303 depletion_q Uncertainty Synthesis Summary

## Workflow represented

This synthesis summarizes the depletion-q uncertainty workflow:

- 301a: individual known-error effects for transmissivity and storage
- 301b: combined T/S known-error interaction effects
- 302a: individual probability-weighted uncertainty for transmissivity and storage
- 302b: joint T/S probability-weighted uncertainty
- 304: robust-decision interpretation of the joint T/S uncertainty

## Main physical interpretation

The combined analyses show that transmissivity and storage act together through the hydraulic diffusivity ratio:

diffusivity factor = T factor / S factor

When T and S change in the same direction, their effects mostly cancel because T/S stays close to baseline. When T increases while S decreases, T/S increases and streamflow decreases. When T decreases while S increases, T/S decreases and streamflow increases.

## Joint probability-weighted headline results

| Metric | Value |
|---|---:|
| Mean probability-weighted absolute streamflow error (cfs) | 0.179871 |
| Mean probability-weighted streamflow shortfall (cfs) | 0.093121 |
| Mean streamflow standard deviation (cfs) | 0.235015 |
| Mean probability of streamflow shortfall | 0.356345 |

## Highest-risk joint grid scenario

- T factor: 1.20
- S factor: 0.80
- Diffusivity factor: 1.500
- Mean streamflow change from baseline: -0.747752 cfs

## Most protective joint grid scenario

- T factor: 0.80
- S factor: 1.20
- Diffusivity factor: 0.667
- Mean streamflow change from baseline: 0.637182 cfs

## Notes on probability of streamflow shortfall

The probability-of-shortfall metric is threshold-based and can look more step-like or oscillatory than magnitude-based metrics. It is useful as a diagnostic, but the probability-weighted shortfall magnitude, absolute error, standard deviation, lower-percentile streamflow, and the 304 robust-decision figures provide a more complete decision interpretation.
