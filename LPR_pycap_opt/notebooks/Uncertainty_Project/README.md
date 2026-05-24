# LPR PyCap Uncertainty Project Notebooks

Recommended repo location:

```text
/workspaces/LPR_redux/LPR_pycap_opt/notebooks/Uncertainty_Project/
```

## Files

- `uncertainty_project_helpers.py` — shared helper functions for loading PyCap/PEST files, re-evaluating designs, calculating uncertainty metrics, and plotting.
- `200_validate_fish_dollars_baseline_reevaluation.ipynb` — validates baseline re-evaluation against original archived outputs.
- `201_reevaluate_baseline_pareto_under_T_scenarios.ipynb` — known T error analysis for baseline designs under T -10%, baseline T, and T +10%.
- `202_probability_weighted_T_uncertainty_cost.ipynb` — probability-weighted uncertainty cost analysis for uncertain T.
- `203_uncertainty_report_figures.ipynb` — polished report figures and original 05_MOU front comparison.

## Cache / rerun switch

Notebooks 200–202 include:

```python
RERUN_REEVALUATION = False
```

- `False`: use cached reevaluation CSVs if they already exist.
- `True`: force the notebook to rerun the PyCap re-evaluations.

Cached results are saved in:

```text
Uncertainty_Project/cached_reevaluations/
```

Final outputs are saved in:

```text
Uncertainty_Project/project_output/
```

## Workflow order

Run in this order:

1. `200_validate_fish_dollars_baseline_reevaluation.ipynb`
2. `201_reevaluate_baseline_pareto_under_T_scenarios.ipynb`
3. `202_probability_weighted_T_uncertainty_cost.ipynb`
4. `203_uncertainty_report_figures.ipynb`

## Original 05_MOU comparison inputs

Notebook 203 looks for these CSVs in this folder, the parent notebooks folder, or `LPR_pycap_opt/notebooks/`:

```text
fish_dollars_baseline_0.0_1.0_0.01_tradeoff.csv
fish_dollars_Tmin10per_0.0_1.0_0.01_tradeoff.csv
fish_dollars_Tplus10per_0.0_1.0_0.01_tradeoff.csv
```

The expected columns are:

```text
real_name, Total Pumping (cfs), Streamflow (cfs), Depletion (cfs)
```
