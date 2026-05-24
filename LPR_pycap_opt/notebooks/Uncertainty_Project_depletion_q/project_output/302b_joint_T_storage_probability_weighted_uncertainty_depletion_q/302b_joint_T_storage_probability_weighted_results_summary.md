# 302b Joint T/S Probability-Weighted Uncertainty Summary

## Purpose

This notebook evaluates joint transmissivity-storage uncertainty for the baseline depletion-q Pareto pumping designs.

The joint probability model assumes T and S are independent:

joint probability = P(T) x P(S)

The 5x5 grid uses T and S factors from 0.80 to 1.20.

## Headline results

| Metric | Value |
|---|---:|
| Mean probability-weighted absolute streamflow error (cfs) | 0.179871 |
| Max probability-weighted absolute streamflow error (cfs) | 0.256745 |
| Mean probability-weighted streamflow shortfall (cfs) | 0.093121 |
| Max probability-weighted streamflow shortfall (cfs) | 0.131202 |
| Mean probability of streamflow shortfall | 0.356345 |
| Mean streamflow standard deviation (cfs) | 0.235015 |
| Max streamflow standard deviation (cfs) | 0.335214 |

## Highest-risk joint scenario

The highest-risk grid scenario by mean streamflow change was:

- T factor: 1.20
- S factor: 0.80
- Diffusivity factor T/S: 1.500
- Mean streamflow change from baseline: -0.747752 cfs

## Most protective joint scenario

The most protective grid scenario by mean streamflow change was:

- T factor: 0.80
- S factor: 1.20
- Diffusivity factor T/S: 0.667
- Mean streamflow change from baseline: 0.637182 cfs

## Interpretation guide

The joint T/S result should be interpreted through the hydraulic diffusivity ratio:

diffusivity factor = T factor / S factor

Higher T and lower S increase diffusivity and are expected to produce greater depletion and lower streamflow. Lower T and higher S decrease diffusivity and are expected to produce less depletion and higher streamflow.
