# 304 Robust Decision Summary

## Purpose

This notebook translates the joint T/S uncertainty results into decision-oriented quantities:

- the global streamflow uncertainty structure
- a local uncertainty interpretation near a selected pumping target
- probability of shortfall
- expected shortfall magnitude
- robust pumping limits by threshold and reliability

## Robust-yield selections

| Streamflow threshold (cfs) | Reliability | Selected member | Selected pumping (cfs) | Probability below threshold | Expected shortfall (cfs) |
|---:|---:|---|---:|---:|---:|
| 5.00 | 0.80 | gen=42_member=7200_pso | 35.3322 | 0.1464 | 0.0335 |
| 5.00 | 0.90 | gen=40_member=6799_pso | 34.9528 | 0.0515 | 0.0078 |
| 5.00 | 0.95 | gen=32_member=5452_pso | 34.8475 | 0.0296 | 0.0053 |
| 6.00 | 0.80 | gen=47_member=7961_pso | 32.8185 | 0.1464 | 0.0280 |
| 6.00 | 0.90 | gen=50_member=8483_pso | 32.1245 | 0.0515 | 0.0053 |
| 6.00 | 0.95 | gen=40_member=6749_pso | 32.0338 | 0.0296 | 0.0042 |
| 7.00 | 0.80 | gen=46_member=7840_pso | 27.8384 | 0.1464 | 0.0191 |
| 7.00 | 0.90 | gen=45_member=7623_pso | 26.8679 | 0.0515 | 0.0047 |
| 7.00 | 0.95 | gen=47_member=7933_pso | 26.4996 | 0.0296 | 0.0034 |

## Interpretation

- The global streamflow uncertainty figure shows the best-case, baseline, percentile, and worst-case structure under joint T/S uncertainty.
- The local uncertainty figure zooms in on one pumping neighborhood and illustrates the full uncertainty range plus two shortfall magnitudes relative to the local threshold.
- The probability and expected-shortfall plots translate that uncertainty structure into threshold-based risk metrics.
- The robust-yield bar chart shows how the maximum acceptable pumping objective changes as the streamflow threshold and reliability requirement become more stringent.
