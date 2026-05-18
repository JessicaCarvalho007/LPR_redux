# Checkpoint 5 — Optimized Uncertainty Project Structure

## Status

The uncertainty analysis notebooks have been reorganized into a dedicated `Uncertainty_Project` directory.

## Key improvements

- Shared helper functions were moved to `uncertainty_project_helpers.py`.
- Notebooks now have Boolean cache switches with `RERUN_REEVALUATION`.
- Re-evaluation results are cached in `cached_reevaluations/`.
- Final figures/tables are organized in `project_output/`.
- Notebook 203 includes original 05_MOU front comparison plots for baseline, T -10%, and T +10%.
- Plot styling is centralized and editable through `PLOT_STYLE`, `SCENARIO_COLORS`, and `SCENARIO_LABELS`.

## Next suggested work

- Run 200–203 from inside `Uncertainty_Project`.
- Check that 203 finds all three original tradeoff CSVs.
- After successful run, commit the `Uncertainty_Project` folder to the repository.
