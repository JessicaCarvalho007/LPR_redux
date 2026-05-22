"""
Shared helper functions for the LPR PyCap transmissivity uncertainty project.

This file is intentionally written as a single, well-commented helper module so the
notebooks can focus on project logic instead of repeating setup, data loading,
re-evaluation, and plotting utilities.

Recommended location in the repository:
    /workspaces/LPR_redux/LPR_pycap_opt/notebooks/Uncertainty_Project/

The helper functions assume you are working inside the LPR_redux repository and
that the original PyCap/PEST++ files are still in their normal locations:
    LPR_pycap_opt/scripts/
    LPR_pycap_opt/pycap_runs/pycap_pest/
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import copy
import importlib.util
import os
import sys
import traceback
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# =============================================================================
# Project-wide constants and editable plotting defaults
# =============================================================================

# Update this when changing shared helper behavior. The notebooks print this value
# so it is easy to confirm that Python is importing the intended helper file, not
# a stale/cached copy from another folder or kernel session.
HELPER_VERSION = "2026-05-19_202_203_normal_distribution_plot_fix"


GPM2CFS = 0.002228
HISTORIC_STREAMFLOW_CFS = 8.6
DEPLETION_OBS_NAME = "lpr:total_combined:bdpl"
PUMPING_COLUMN_FOR_HYDRO_PLOTS = "effective_total_pumping_cfs"

# Main plotting defaults. These can be copied and edited in a notebook.
PLOT_STYLE = {
    "figure.figsize": (8.5, 5.5),
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "lines.linewidth": 1.8,
    "lines.markersize": 4,
}

# Scenario colors are centralized so you can restyle figures easily.
SCENARIO_COLORS = {
    "baseline_T": "#2E86AB",
    "T_minus_10pct": "#3A923A",
    "T_plus_10pct": "#D1495B",
    "expected": "#E79AA5",  #9527F5
    "uncertainty_band": "#A6A6A6",
    "original_baseline": "#8FC3DA",
    "original_T_minus_10pct": "#8BCB8B",
    "original_T_plus_10pct": "#E79AA5",
}

SCENARIO_LABELS = {
    "baseline_T": "Baseline T",
    "T_minus_10pct": "T −10%",
    "T_plus_10pct": "T +10%",
    "original_baseline": "Original MOU baseline",
    "original_T_minus_10pct": "Original MOU T −10%",
    "original_T_plus_10pct": "Original MOU T +10%",
}


# =============================================================================
# Path helpers
# =============================================================================

def find_lpr_pycap_opt_dir(start: str | Path | None = None) -> Path:
    """
    Find the LPR_pycap_opt directory by walking upward from the current directory.

    This makes the notebooks more portable. They can live in:
        LPR_pycap_opt/notebooks/
    or:
        LPR_pycap_opt/notebooks/Uncertainty_Project/

    The function looks for the typical LPR_pycap_opt markers: scripts/ and
    pycap_runs/pycap_pest/.
    """
    start_path = Path.cwd() if start is None else Path(start).resolve()
    candidates = [start_path] + list(start_path.parents)
    for p in candidates:
        if (p / "scripts").exists() and (p / "pycap_runs" / "pycap_pest").exists():
            return p
    raise FileNotFoundError(
        "Could not locate LPR_pycap_opt. Start the notebook from within the "
        "LPR_redux/LPR_pycap_opt tree."
    )


def make_project_dirs(notebook_dir: str | Path, notebook_number: str, notebook_slug: str) -> dict[str, Path]:
    """
    Create and return standard output/cache directories for a notebook.
    """
    notebook_dir = Path(notebook_dir)
    output_dir = notebook_dir / "project_output" / f"{notebook_number}_{notebook_slug}"
    cache_dir = notebook_dir / "cached_reevaluations"
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return {"output_dir": output_dir, "cache_dir": cache_dir}


# =============================================================================
# Importing and initializing the original fish-dollars forward model
# =============================================================================

@dataclass
class FishDollarsContext:
    """Everything needed to call the original fish-dollars get_results() function."""
    run_name: str
    project_dir: Path
    run_dir: Path
    script_path: Path
    module: object
    initial_dict_master: dict
    bdplobs: object
    fishcurve: object
    ref_flow: float
    receipts: pd.DataFrame
    obsnames: list[str]
    base_T: float


def import_python_file(module_name: str, file_path: str | Path):
    """Import a Python file by path without modifying the repository."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Could not find Python file: {file_path}")
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def find_fish_dollars_script(project_dir: str | Path, run_dir: str | Path) -> Path:
    """
    Locate the source-of-truth fish-dollars forward script.

    Prefer the copy inside the run folder because that is the exact script copied
    into the PEST run. Fall back to LPR_pycap_opt/scripts/ if needed.
    """
    project_dir = Path(project_dir)
    run_dir = Path(run_dir)
    candidates = [
        run_dir / "run_pycap_standalone_opt_mou_fish_dollars.py",
        project_dir / "scripts" / "run_pycap_standalone_opt_mou_fish_dollars.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not find run_pycap_standalone_opt_mou_fish_dollars.py in the run "
        "folder or the scripts folder."
    )


def read_obsnames_from_instruction_file(run_dir: str | Path) -> list[str]:
    """Read observation names from allobs.out.ins using the convention in the original script."""
    ins_file = Path(run_dir) / "allobs.out.ins"
    if not ins_file.exists():
        raise FileNotFoundError(f"Missing instruction file: {ins_file}")
    return [line.split("!")[1].lower() for line in ins_file.read_text().splitlines()[1:]]


def load_fish_dollars_context(run_name: str, project_dir: str | Path | None = None) -> FishDollarsContext:
    """
    Load the original fish-dollars forward-model context for a PEST++ MOU run.

    The original instantiate() function uses relative paths, so this helper
    temporarily changes into the run directory, calls instantiate(), and then
    returns to the original working directory.
    """
    project_dir = find_lpr_pycap_opt_dir() if project_dir is None else Path(project_dir)
    run_dir = project_dir / "pycap_runs" / "pycap_pest" / f"run_{run_name}"
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory does not exist: {run_dir}")

    script_path = find_fish_dollars_script(project_dir, run_dir)
    module_name = f"fish_dollars_forward_{abs(hash(str(script_path))) % 10**8}"
    module = import_python_file(module_name, script_path)

    original_cwd = Path.cwd()
    os.chdir(run_dir)
    try:
        initial_dict_master, bdplobs, fishcurve, ref_flow, receipts = module.instantiate()
    finally:
        os.chdir(original_cwd)

    obsnames = read_obsnames_from_instruction_file(run_dir)
    base_T = float(initial_dict_master["project_properties"]["T"])

    return FishDollarsContext(
        run_name=run_name,
        project_dir=project_dir,
        run_dir=run_dir,
        script_path=script_path,
        module=module,
        initial_dict_master=initial_dict_master,
        bdplobs=bdplobs,
        fishcurve=fishcurve,
        ref_flow=ref_flow,
        receipts=receipts,
        obsnames=obsnames,
        base_T=base_T,
    )


# =============================================================================
# Loading PEST++ MOU population/archive data
# =============================================================================

def read_pareto_archive_summary(run_name: str, run_dir: str | Path) -> pd.DataFrame:
    """Read the PEST++ MOU Pareto archive summary CSV zip."""
    pareto_file = Path(run_dir) / f"{run_name}.pareto.archive.summary.csv.zip"
    if not pareto_file.exists():
        raise FileNotFoundError(f"Missing Pareto archive summary: {pareto_file}")
    df = pd.read_csv(pareto_file)
    df["member"] = df["member"].astype(str)
    return df


def select_final_feasible_front1(pareto_df: pd.DataFrame, n_test_members: int | None = None) -> pd.DataFrame:
    """
    Select final-generation, feasible, NSGA-II front-1 members.

    This is the design set used in this project.
    """
    required = {"member", "generation", "nsga2_front", "is_feasible", "ag_receipts", "fish_prob"}
    missing = required - set(pareto_df.columns)
    if missing:
        raise KeyError(f"Pareto archive summary is missing required columns: {sorted(missing)}")

    df = pareto_df.loc[
        (pareto_df["nsga2_front"] == 1) &
        (pareto_df["is_feasible"] == 1)
    ].copy()

    final_generation = df["generation"].max()
    df = df.loc[df["generation"] == final_generation].copy()
    df["member"] = df["member"].astype(str)

    if n_test_members is not None:
        df = df.head(int(n_test_members)).copy()

    if df.empty:
        raise ValueError("No final-generation feasible front-1 members found.")

    return df


def load_decision_variable_population(run_dir: str | Path) -> pd.DataFrame:
    """
    Load saved decision-variable populations from a PEST++ MOU run.

    We include all dv_pop csv zip files and initial_dvpop.csv if present because
    final archive members can come from any saved population.
    """
    run_dir = Path(run_dir)
    dv_files = sorted(run_dir.glob("*dv_pop.csv.zip"))
    frames = []

    for f in dv_files:
        try:
            frames.append(pd.read_csv(f, index_col=0))
        except Exception as err:
            print(f"Warning: could not read {f.name}: {err}")

    init_file = run_dir / "initial_dvpop.csv"
    if init_file.exists():
        frames.append(pd.read_csv(init_file, index_col=0))

    if not frames:
        raise FileNotFoundError(f"No dv_pop csv files were found in {run_dir}")

    dv_df = pd.concat(frames, axis=0)
    dv_df.index = dv_df.index.astype(str)
    dv_df = dv_df[~dv_df.index.duplicated(keep="first")]
    return dv_df


def load_observation_population(run_dir: str | Path) -> pd.DataFrame | None:
    """
    Load saved observation-population files, if they exist.

    These often contain non-objective outputs such as lpr:total_combined:bdpl.
    The function returns None if no obs_pop files are available.
    """
    run_dir = Path(run_dir)
    obs_files = sorted(run_dir.glob("*obs_pop.csv.zip")) + sorted(run_dir.glob("*obs_pop.csv"))
    frames = []

    for f in obs_files:
        try:
            frames.append(pd.read_csv(f, index_col=0))
        except Exception as err:
            print(f"Warning: could not read {f.name}: {err}")

    if not frames:
        return None

    obs_df = pd.concat(frames, axis=0)
    obs_df.index = obs_df.index.astype(str)
    obs_df = obs_df[~obs_df.index.duplicated(keep="first")]
    obs_df.columns = [str(c).lower() for c in obs_df.columns]
    return obs_df


def get_q_columns(df: pd.DataFrame) -> list[str]:
    """Return columns that look like pumping decision variables."""
    return [c for c in df.columns if str(c).lower().endswith("__q") or "_q" in str(c).lower()]


def get_obs_value(obs_df: pd.DataFrame | None, member: str, obs_name: str):
    """Safely fetch one observation from the archived obs_pop dataframe."""
    if obs_df is None:
        return np.nan
    obs_name = str(obs_name).lower()
    member = str(member)
    if member not in obs_df.index or obs_name not in obs_df.columns:
        return np.nan
    return obs_df.loc[member, obs_name]


# =============================================================================
# Re-evaluation helpers used by notebooks 200, 201, and 202
# =============================================================================

def effective_q_after_fish_dollars_cutoff(q_row: pd.Series, receipts: pd.DataFrame) -> pd.Series:
    """
    Reproduce the fish-dollars pumping cutoff from the original forward model.

    If a pumping decision is <= 70% of baseline parval1, the original script
    treats the well/farm as shut down and sets its pumping to zero. For hydrologic
    plots, this means effective pumping is the more honest x-axis than raw pumping.
    """
    q = q_row.copy()
    q.index = [str(i).lower() for i in q.index]
    q = q.loc[q.index.str.contains("_q")]
    local_receipts = receipts.loc[q.index]
    q.loc[q <= 0.7 * local_receipts.parval1] = 0.0
    return q


def make_initial_dict_with_T(initial_dict_master: dict, t_factor: float | None = None, t_value: float | None = None) -> dict:
    """Return a deep-copied PyCap project dictionary with T changed."""
    initial_dict = copy.deepcopy(initial_dict_master)
    if "project_properties" not in initial_dict:
        raise KeyError("initial_dict does not contain 'project_properties'.")
    if "T" not in initial_dict["project_properties"]:
        raise KeyError("initial_dict['project_properties'] does not contain 'T'.")

    base_T = float(initial_dict_master["project_properties"]["T"])
    if t_value is not None:
        initial_dict["project_properties"]["T"] = float(t_value)
    else:
        initial_dict["project_properties"]["T"] = base_T * float(1.0 if t_factor is None else t_factor)
    return initial_dict


def run_original_fish_dollars_get_results(
    q_row: pd.Series,
    context: FishDollarsContext,
    t_factor: float | None = 1.0,
    t_value: float | None = None,
) -> pd.Series:
    """
    Call the original fish-dollars get_results() function for one pumping design.

    The only intentional model change made here is the T value in
    project_properties. The pumping design is held fixed.
    """
    q_row = q_row.copy()
    q_row.index = [str(i).lower() for i in q_row.index]
    initial_dict = make_initial_dict_with_T(context.initial_dict_master, t_factor=t_factor, t_value=t_value)
    result = context.module.get_results(
        q_row,
        context.obsnames,
        initial_dict,
        context.bdplobs,
        context.fishcurve,
        context.ref_flow,
        context.receipts,
        write_csv=False,
    )
    return result


def reevaluate_designs(
    pareto_final: pd.DataFrame,
    dv_df: pd.DataFrame,
    q_cols: list[str],
    context: FishDollarsContext,
    scenarios: dict[str, float | dict],
    historic_streamflow_cfs: float = HISTORIC_STREAMFLOW_CFS,
    depletion_obs_name: str = DEPLETION_OBS_NAME,
    progress_every: int = 50,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Re-evaluate a set of Pareto designs under one or more T scenarios.

    Parameters
    ----------
    scenarios : dict
        Examples:
            {"baseline_T": 1.0, "T_plus_10pct": 1.1}
        or:
            {"T_factor_1.10": {"T_factor": 1.1, "probability_weight": 0.05}}
    """
    records = []
    errors = []
    scenario_items = list(scenarios.items())
    n_total = len(pareto_final) * len(scenario_items)
    counter = 0

    for scenario_label, scenario_info in scenario_items:
        if isinstance(scenario_info, dict):
            t_factor = scenario_info.get("T_factor", None)
            t_value = scenario_info.get("T_value", None)
            prob_weight = scenario_info.get("probability_weight", np.nan)
        else:
            t_factor = float(scenario_info)
            t_value = None
            prob_weight = np.nan

        t_value_actual = float(t_value) if t_value is not None else context.base_T * float(t_factor)
        t_factor_actual = t_value_actual / context.base_T

        print(f"\nScenario: {scenario_label} | T factor: {t_factor_actual:.6g} | T value: {t_value_actual:.6g}")

        for i, row in pareto_final.reset_index(drop=True).iterrows():
            counter += 1
            member = str(row["member"])
            if counter == 1 or counter % progress_every == 0 or counter == n_total:
                print(f"  Re-evaluating {counter} of {n_total}: scenario={scenario_label}, member={member}")

            q_row = dv_df.loc[member, q_cols].copy()
            try:
                reeval = run_original_fish_dollars_get_results(
                    q_row=q_row,
                    context=context,
                    t_factor=t_factor_actual,
                    t_value=t_value_actual,
                )
                q_eff = effective_q_after_fish_dollars_cutoff(q_row, context.receipts)

                raw_total_pumping_gpm = q_row.sum()
                effective_total_pumping_gpm = q_eff.sum()
                raw_total_pumping_cfs = raw_total_pumping_gpm * GPM2CFS
                effective_total_pumping_cfs = effective_total_pumping_gpm * GPM2CFS

                depletion_cfs = reeval.loc[depletion_obs_name] if depletion_obs_name in reeval.index else np.nan
                streamflow_cfs = historic_streamflow_cfs - depletion_cfs

                records.append({
                    "scenario": scenario_label,
                    "T_factor": t_factor_actual,
                    "T_value": t_value_actual,
                    "probability_weight": prob_weight,
                    "member": member,
                    "generation": row["generation"],
                    "ag_receipts_archive_baseline": row.get("ag_receipts", np.nan),
                    "fish_prob_archive_baseline": row.get("fish_prob", np.nan),
                    "ag_receipts_reeval": reeval.loc["ag_receipts"] if "ag_receipts" in reeval.index else np.nan,
                    "fish_prob_reeval": reeval.loc["fish_prob"] if "fish_prob" in reeval.index else np.nan,
                    "raw_total_pumping_gpm": raw_total_pumping_gpm,
                    "raw_total_pumping_cfs": raw_total_pumping_cfs,
                    "effective_total_pumping_gpm": effective_total_pumping_gpm,
                    "effective_total_pumping_cfs": effective_total_pumping_cfs,
                    "depletion_obs_name": depletion_obs_name,
                    "depletion_cfs": depletion_cfs,
                    "streamflow_cfs": streamflow_cfs,
                })
            except Exception as err:
                errors.append({
                    "scenario": scenario_label,
                    "member": member,
                    "error": repr(err),
                    "traceback": traceback.format_exc(),
                })

    results_long = pd.DataFrame(records)
    error_df = pd.DataFrame(errors)
    return results_long, error_df


def make_wide_by_scenario(
    results_long: pd.DataFrame,
    index_cols: list[str] | None = None,
    value_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Convert long scenario results to one row per member with scenario-suffixed columns."""
    if index_cols is None:
        index_cols = ["member", "generation", "raw_total_pumping_cfs", "effective_total_pumping_cfs"]
    if value_cols is None:
        value_cols = ["T_factor", "T_value", "depletion_cfs", "streamflow_cfs", "ag_receipts_reeval", "fish_prob_reeval"]

    base = results_long[index_cols].drop_duplicates("member").copy()
    wide = base.copy()
    for scen in results_long["scenario"].drop_duplicates():
        part = results_long.loc[results_long["scenario"] == scen, ["member"] + value_cols].copy()
        part = part.rename(columns={c: f"{c}__{scen}" for c in value_cols})
        wide = wide.merge(part, on="member", how="left")
    return wide


def add_known_T_error_metrics(results_long: pd.DataFrame, baseline_label: str = "baseline_T") -> pd.DataFrame:
    """
    Add change/error/shortfall metrics relative to a baseline-T re-evaluation.

    This function is intentionally idempotent. It first removes any existing
    baseline-relative metric columns, including pandas merge leftovers such as
    *_x and *_y columns, before rebuilding the metrics. That makes it safe to
    rerun notebook cells without restarting the kernel.
    """
    required_cols = {
        "scenario", "member", "depletion_cfs", "streamflow_cfs",
        "ag_receipts_reeval", "fish_prob_reeval",
    }
    missing = required_cols - set(results_long.columns)
    if missing:
        raise KeyError(
            "Cannot add baseline-relative T metrics. Missing columns: "
            f"{sorted(missing)}"
        )

    if baseline_label not in set(results_long["scenario"]):
        raise KeyError(f"Expected baseline scenario label {baseline_label!r}.")

    metric_base_cols = [
        "baseline_T_depletion_cfs",
        "baseline_T_streamflow_cfs",
        "baseline_T_ag_receipts",
        "baseline_T_fish_prob",
        "depletion_change_from_baseline_cfs",
        "streamflow_change_from_baseline_cfs",
        "streamflow_error_cfs",
        "absolute_streamflow_error_cfs",
        "streamflow_shortfall_below_baseline_cfs",
    ]

    metric_cols_to_drop = [
        c for c in results_long.columns
        if any(c == base or c.startswith(f"{base}_") for base in metric_base_cols)
    ]
    clean = results_long.drop(columns=metric_cols_to_drop, errors="ignore").copy()

    baseline_by_member = (
        clean.loc[clean["scenario"] == baseline_label, [
            "member", "depletion_cfs", "streamflow_cfs", "ag_receipts_reeval", "fish_prob_reeval"
        ]]
        .drop_duplicates("member")
        .rename(columns={
            "depletion_cfs": "baseline_T_depletion_cfs",
            "streamflow_cfs": "baseline_T_streamflow_cfs",
            "ag_receipts_reeval": "baseline_T_ag_receipts",
            "fish_prob_reeval": "baseline_T_fish_prob",
        })
    )

    out = clean.merge(baseline_by_member, on="member", how="left")
    out["depletion_change_from_baseline_cfs"] = out["depletion_cfs"] - out["baseline_T_depletion_cfs"]
    out["streamflow_change_from_baseline_cfs"] = out["streamflow_cfs"] - out["baseline_T_streamflow_cfs"]
    # Positive error means streamflow is lower than the baseline-T prediction.
    out["streamflow_error_cfs"] = out["baseline_T_streamflow_cfs"] - out["streamflow_cfs"]
    out["absolute_streamflow_error_cfs"] = out["streamflow_error_cfs"].abs()
    out["streamflow_shortfall_below_baseline_cfs"] = out["streamflow_error_cfs"].clip(lower=0)
    return out


def summarize_known_T_scenarios(results_long: pd.DataFrame) -> pd.DataFrame:
    """Summarize the known ±T scenario results."""
    rows = []
    for scen, group in results_long.groupby("scenario", sort=False):
        rows.append({
            "scenario": scen,
            "T_factor": group["T_factor"].iloc[0],
            "T_value": group["T_value"].iloc[0],
            "n_members": len(group),
            "mean_effective_total_pumping_cfs": group["effective_total_pumping_cfs"].mean(),
            "mean_depletion_cfs": group["depletion_cfs"].mean(),
            "mean_streamflow_cfs": group["streamflow_cfs"].mean(),
            "mean_streamflow_change_from_baseline_cfs": group["streamflow_change_from_baseline_cfs"].mean(),
            "mean_absolute_streamflow_error_cfs": group["absolute_streamflow_error_cfs"].mean(),
            "max_absolute_streamflow_error_cfs": group["absolute_streamflow_error_cfs"].max(),
            "mean_streamflow_shortfall_below_baseline_cfs": group["streamflow_shortfall_below_baseline_cfs"].mean(),
            "max_streamflow_shortfall_below_baseline_cfs": group["streamflow_shortfall_below_baseline_cfs"].max(),
        })
    return pd.DataFrame(rows)


# =============================================================================
# Probability-weighted uncertainty functions used by notebook 202
# =============================================================================

def make_discrete_normal_T_table(
    base_T: float,
    sigma_fraction: float = 0.10,
    n_values: int = 11,
    n_sigma_each_side: float = 2.0,
) -> pd.DataFrame:
    """Create a discrete normal distribution over T factors centered on baseline T."""
    if n_values < 3:
        raise ValueError("n_values should be at least 3.")
    sigma_T = float(base_T) * float(sigma_fraction)
    factors = np.linspace(1 - sigma_fraction * n_sigma_each_side, 1 + sigma_fraction * n_sigma_each_side, n_values)
    T_values = base_T * factors
    z = (T_values - base_T) / sigma_T
    raw_weights = np.exp(-0.5 * z**2)
    weights = raw_weights / raw_weights.sum()
    return pd.DataFrame({
        "scenario": [f"T_factor_{f:.3f}" for f in factors],
        "T_factor": factors,
        "T_value": T_values,
        "z_score": z,
        "probability_weight": weights,
    })


def weighted_quantile(values, weights, quantile: float) -> float:
    """
    Compute a weighted quantile for 1-D arrays.

    This version is intentionally defensive because the probability notebook can
    be re-run from cached CSVs. Cached files sometimes carry string/object dtypes
    or missing values. We remove non-finite values and normalize the weights
    before computing the quantile.
    """
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)

    valid = np.isfinite(values) & np.isfinite(weights) & (weights >= 0)
    values = values[valid]
    weights = weights[valid]

    if values.size == 0:
        return np.nan

    weight_sum = weights.sum()
    if weight_sum <= 0:
        return np.nan

    weights = weights / weight_sum
    sorter = np.argsort(values)
    values = values[sorter]
    weights = weights[sorter]
    cumulative = np.cumsum(weights)
    cumulative = cumulative / cumulative[-1]
    return np.interp(quantile, cumulative, values)


def summarize_probability_weighted_members(
    results_long: pd.DataFrame,
    streamflow_threshold_cfs: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Summarize probability-weighted uncertainty metrics for each Pareto member.

    Returns member_summary, scenario_summary, overall_summary.

    Important implementation note
    -----------------------------
    This function is deliberately written to be robust to two common notebook
    workflow issues:

    1. Cached CSVs can reload numeric columns as object/string columns. We coerce
       the key numeric columns before doing weighted calculations.
    2. Newer pandas versions changed the behavior of groupby.apply(). We try the
       newer include_groups=False call first and fall back to older behavior if
       the installed pandas version does not support it.
    """
    if results_long.empty:
        raise ValueError("results_long is empty; there are no probability scenarios to summarize.")

    # Work on a copy so the caller's dataframe is not modified unexpectedly.
    results = results_long.copy()

    # The probability-weighted calculations need these columns to be numeric.
    numeric_cols = [
        "T_factor", "T_value", "probability_weight", "depletion_cfs", "streamflow_cfs",
        "raw_total_pumping_cfs", "effective_total_pumping_cfs", "generation",
        "baseline_T_streamflow_cfs", "baseline_T_depletion_cfs",
        "streamflow_error_cfs", "absolute_streamflow_error_cfs",
        "streamflow_shortfall_below_baseline_cfs",
    ]
    for col in numeric_cols:
        if col in results.columns:
            results[col] = pd.to_numeric(results[col], errors="coerce")

    # Add baseline-relative metrics only if they are not already complete.
    # This prevents duplicate *_x/*_y columns if a notebook cell already called
    # add_known_T_error_metrics(), or if a cached dataframe already contains
    # baseline-relative columns from a previous run.
    required_metric_cols = {
        "baseline_T_streamflow_cfs",
        "baseline_T_depletion_cfs",
        "streamflow_error_cfs",
        "absolute_streamflow_error_cfs",
        "streamflow_shortfall_below_baseline_cfs",
    }
    has_complete_baseline_metrics = required_metric_cols.issubset(results.columns)

    if not has_complete_baseline_metrics:
        if "baseline_T" in set(results["scenario"]):
            results = add_known_T_error_metrics(results, baseline_label="baseline_T")
        else:
            baseline_scen = (
                results.assign(absdiff=(results["T_factor"] - 1.0).abs())
                .sort_values("absdiff")["scenario"]
                .iloc[0]
            )
            results = add_known_T_error_metrics(results, baseline_label=baseline_scen)

    if streamflow_threshold_cfs is not None:
        results["streamflow_below_threshold"] = results["streamflow_cfs"] < streamflow_threshold_cfs
    else:
        results["streamflow_below_threshold"] = False

    def summarize_member(group: pd.DataFrame) -> pd.Series:
        # Convert each group to clean NumPy arrays. This avoids pandas index
        # alignment surprises when using boolean masks with weight arrays.
        weights = group["probability_weight"].to_numpy(dtype=float)
        valid_weights = np.isfinite(weights) & (weights >= 0)
        weights = np.where(valid_weights, weights, 0.0)
        weight_sum = weights.sum()
        if weight_sum <= 0:
            raise ValueError(
                "Probability weights sum to zero for a Pareto member. Check the T probability table."
            )
        weights = weights / weight_sum

        streamflow = group["streamflow_cfs"].to_numpy(dtype=float)
        depletion = group["depletion_cfs"].to_numpy(dtype=float)
        baseline_streamflow = group["baseline_T_streamflow_cfs"].to_numpy(dtype=float)
        baseline_depletion = group["baseline_T_depletion_cfs"].to_numpy(dtype=float)
        streamflow_error = group["streamflow_error_cfs"].to_numpy(dtype=float)
        abs_error = group["absolute_streamflow_error_cfs"].to_numpy(dtype=float)
        shortfall = group["streamflow_shortfall_below_baseline_cfs"].to_numpy(dtype=float)

        expected_streamflow = np.sum(weights * streamflow)
        expected_depletion = np.sum(weights * depletion)
        streamflow_variance = np.sum(weights * (streamflow - expected_streamflow) ** 2)
        depletion_variance = np.sum(weights * (depletion - expected_depletion) ** 2)

        lower_than_baseline_mask = streamflow < baseline_streamflow
        risk_lower_than_baseline = np.sum(weights[lower_than_baseline_mask])

        if streamflow_threshold_cfs is not None:
            threshold_mask = group["streamflow_below_threshold"].to_numpy(dtype=bool)
            risk_below_threshold = np.sum(weights[threshold_mask])
        else:
            risk_below_threshold = np.nan

        return pd.Series({
            "generation": group["generation"].iloc[0],
            "raw_total_pumping_cfs": group["raw_total_pumping_cfs"].iloc[0],
            "effective_total_pumping_cfs": group["effective_total_pumping_cfs"].iloc[0],
            "baseline_T_streamflow_cfs": baseline_streamflow[0],
            "baseline_T_depletion_cfs": baseline_depletion[0],
            "expected_streamflow_cfs": expected_streamflow,
            "expected_depletion_cfs": expected_depletion,
            "expected_streamflow_bias_from_baseline_cfs": expected_streamflow - baseline_streamflow[0],
            "expected_depletion_bias_from_baseline_cfs": expected_depletion - baseline_depletion[0],
            "streamflow_std_cfs": np.sqrt(streamflow_variance),
            "depletion_std_cfs": np.sqrt(depletion_variance),
            "streamflow_p05_cfs": weighted_quantile(streamflow, weights, 0.05),
            "streamflow_p50_cfs": weighted_quantile(streamflow, weights, 0.50),
            "streamflow_p95_cfs": weighted_quantile(streamflow, weights, 0.95),
            "depletion_p05_cfs": weighted_quantile(depletion, weights, 0.05),
            "depletion_p50_cfs": weighted_quantile(depletion, weights, 0.50),
            "depletion_p95_cfs": weighted_quantile(depletion, weights, 0.95),
            "probability_weighted_absolute_streamflow_error_cfs": np.sum(weights * abs_error),
            "probability_weighted_streamflow_shortfall_cfs": np.sum(weights * shortfall),
            "probability_weighted_signed_streamflow_error_cfs": np.sum(weights * streamflow_error),
            "max_absolute_streamflow_error_cfs": np.nanmax(abs_error),
            "max_streamflow_shortfall_below_baseline_cfs": np.nanmax(shortfall),
            "probability_streamflow_lower_than_baseline": risk_lower_than_baseline,
            "probability_streamflow_below_threshold": risk_below_threshold,
        })

    grouped = results.groupby("member", sort=False, group_keys=False)
    try:
        member_summary = grouped.apply(summarize_member, include_groups=False).reset_index()
    except TypeError:
        # Older pandas does not support include_groups.
        member_summary = grouped.apply(summarize_member).reset_index()

    scenario_summary = (
        results.groupby(["scenario", "T_factor", "T_value", "probability_weight"], sort=False)
        .agg(
            n_members=("member", "count"),
            mean_streamflow_cfs=("streamflow_cfs", "mean"),
            mean_depletion_cfs=("depletion_cfs", "mean"),
            mean_streamflow_change_from_baseline_cfs=("streamflow_change_from_baseline_cfs", "mean"),
            mean_streamflow_shortfall_below_baseline_cfs=("streamflow_shortfall_below_baseline_cfs", "mean"),
            max_streamflow_shortfall_below_baseline_cfs=("streamflow_shortfall_below_baseline_cfs", "max"),
        )
        .reset_index()
    )

    overall_metrics = {
        "n_members": len(member_summary),
        "mean_probability_weighted_absolute_streamflow_error_cfs": member_summary["probability_weighted_absolute_streamflow_error_cfs"].mean(),
        "max_probability_weighted_absolute_streamflow_error_cfs": member_summary["probability_weighted_absolute_streamflow_error_cfs"].max(),
        "mean_probability_weighted_streamflow_shortfall_cfs": member_summary["probability_weighted_streamflow_shortfall_cfs"].mean(),
        "max_probability_weighted_streamflow_shortfall_cfs": member_summary["probability_weighted_streamflow_shortfall_cfs"].max(),
        "mean_streamflow_std_cfs": member_summary["streamflow_std_cfs"].mean(),
        "max_streamflow_std_cfs": member_summary["streamflow_std_cfs"].max(),
        "mean_probability_streamflow_lower_than_baseline": member_summary["probability_streamflow_lower_than_baseline"].mean(),
        "mean_probability_streamflow_below_threshold": member_summary["probability_streamflow_below_threshold"].mean(),
    }
    overall_summary = pd.DataFrame({"metric": list(overall_metrics.keys()), "value": list(overall_metrics.values())})
    return member_summary, scenario_summary, overall_summary


# =============================================================================
# Original MOU optimized-front tradeoff CSV helpers used by notebook 203
# =============================================================================

def _candidate_tradeoff_paths(project_dir: Path, notebook_dir: Path, filename: str) -> list[Path]:
    """Potential locations for user-created tradeoff CSVs."""
    return [
        notebook_dir / filename,
        notebook_dir.parent / filename,
        project_dir / "notebooks" / filename,
    ]


def read_tradeoff_csv(path: str | Path) -> pd.DataFrame:
    """Read a tradeoff CSV and standardize its hydrologic column names."""
    path = Path(path)
    df = pd.read_csv(path)
    rename = {
        "Total Pumping (cfs)": "total_pumping_cfs",
        "Streamflow (cfs)": "streamflow_cfs",
        "Depletion (cfs)": "depletion_cfs",
        "real_name": "real_name",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "streamflow_cfs" not in df.columns and "depletion_cfs" in df.columns:
        df["streamflow_cfs"] = HISTORIC_STREAMFLOW_CFS - df["depletion_cfs"]
    if "depletion_cfs" not in df.columns and "streamflow_cfs" in df.columns:
        df["depletion_cfs"] = HISTORIC_STREAMFLOW_CFS - df["streamflow_cfs"]
    return df


def load_original_mou_tradeoff_fronts(
    project_dir: str | Path,
    notebook_dir: str | Path,
    tradeoff_files: dict[str, str],
    warn_if_missing: bool = True,
) -> pd.DataFrame:
    """
    Load user-created original 05_MOU tradeoff CSVs for baseline, T-10%, and T+10%.

    The notebook can use these to compare fully re-optimized Pareto fronts, which
    is different from re-evaluating the baseline Pareto designs under alternate T.
    """
    project_dir = Path(project_dir)
    notebook_dir = Path(notebook_dir)
    frames = []

    for label, filename in tradeoff_files.items():
        found = None
        for candidate in _candidate_tradeoff_paths(project_dir, notebook_dir, filename):
            if candidate.exists():
                found = candidate
                break
        if found is None:
            msg = f"Missing tradeoff CSV for {label}: {filename}"
            if warn_if_missing:
                warnings.warn(msg)
            continue
        df = read_tradeoff_csv(found)
        df["scenario"] = label
        df["source_file"] = str(found)
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# =============================================================================
# Plotting helpers
# =============================================================================

def apply_plot_style(style: dict | None = None):
    """Apply project plotting defaults."""
    style = PLOT_STYLE if style is None else style
    plt.rcParams.update(style)


def save_figure(fig, outfile: str | Path, dpi: int | None = None):
    """Save a Matplotlib figure with consistent settings."""
    outfile = Path(outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(outfile, dpi=dpi or PLOT_STYLE.get("savefig.dpi", 300), bbox_inches="tight")
    plt.show()
    print("Saved:", outfile)


def sort_for_plot(df: pd.DataFrame, xcol: str = PUMPING_COLUMN_FOR_HYDRO_PLOTS) -> pd.DataFrame:
    """Sort by x variable and member if member exists."""
    sort_cols = [xcol]
    if "member" in df.columns:
        sort_cols.append("member")
    return df.sort_values(sort_cols).copy()


def plot_validation_grid_2x2(
    df: pd.DataFrame,
    plot_specs: list[dict],
    outfile: str | Path,
    figure_title: str = "Baseline re-evaluation validation",
):
    """
    Plot up to four one-to-one validation panels in a single 2x2 figure.

    Each entry in plot_specs should define:
        xcol, ycol, title, xlabel, ylabel

    This is useful for notebook 200 because the goal is to show, at a glance,
    whether archived results and re-evaluated results match for the main
    diagnostic outputs.
    """
    if len(plot_specs) > 4:
        raise ValueError("plot_validation_grid_2x2 supports a maximum of four panels.")

    fig, axes = plt.subplots(2, 2, figsize=(11, 9))
    axes = axes.ravel()

    for ax, spec in zip(axes, plot_specs):
        xcol = spec["xcol"]
        ycol = spec["ycol"]
        panel_df = df[[xcol, ycol]].dropna().copy()

        if panel_df.empty:
            ax.text(0.5, 0.5, "No data available", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(spec.get("title", "Validation panel"))
            continue

        ax.scatter(panel_df[xcol], panel_df[ycol], alpha=0.75, s=22)

        # The dashed 1:1 line is the target. Points on this line mean the
        # re-evaluation exactly reproduced the archived value.
        mn = min(panel_df[xcol].min(), panel_df[ycol].min())
        mx = max(panel_df[xcol].max(), panel_df[ycol].max())
        padding = 0.02 * (mx - mn) if mx > mn else 1.0
        ax.plot([mn - padding, mx + padding], [mn - padding, mx + padding], linestyle="--", color="0.35", label="1:1")
        ax.set_xlim(mn - padding, mx + padding)
        ax.set_ylim(mn - padding, mx + padding)
        ax.set_xlabel(spec.get("xlabel", xcol))
        ax.set_ylabel(spec.get("ylabel", ycol))
        ax.set_title(spec.get("title", "Validation panel"))
        ax.legend(loc="best")

    # Turn off any unused panels if fewer than four specs are supplied.
    for ax in axes[len(plot_specs):]:
        ax.axis("off")

    fig.suptitle(figure_title, y=1.02, fontsize=PLOT_STYLE.get("axes.titlesize", 13) + 1)
    save_figure(fig, outfile)


def plot_archive_vs_reevaluated_front(
    df: pd.DataFrame,
    outfile: str | Path,
    x_archive: str = "effective_total_pumping_archive_cfs",
    y_archive: str = "streamflow_archive_cfs",
    x_reeval: str = "effective_total_pumping_reeval_cfs",
    y_reeval: str = "streamflow_reeval_cfs",
    xlabel: str = "Effective total pumping after fish-dollars cutoff (cfs)",
    ylabel: str = "Streamflow = 8.6 cfs - depletion (cfs)",
    title: str = "Original archived front vs. re-evaluated front",
):
    """
    Plot the archived Pareto front and the re-evaluated Pareto front together.

    In notebook 200, this is the main visual test that the hydrologic tradeoff
    curve has been reproduced correctly. The archived front comes from the
    original MOU run outputs; the re-evaluated front comes from rerunning those
    same pumping designs through the original fish-dollars forward model.
    """
    required = [x_archive, y_archive, x_reeval, y_reeval]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Cannot plot archive vs re-evaluated front. Missing columns: {missing}")

    fig, ax = plt.subplots(figsize=(10, 6))

    archive_df = df[[x_archive, y_archive, "member"] if "member" in df.columns else [x_archive, y_archive]].dropna().copy()
    reeval_df = df[[x_reeval, y_reeval, "member"] if "member" in df.columns else [x_reeval, y_reeval]].dropna().copy()
    archive_df = archive_df.sort_values(x_archive)
    reeval_df = reeval_df.sort_values(x_reeval)

    ax.scatter(archive_df[x_archive], archive_df[y_archive], s=25, alpha=0.65,
               color=SCENARIO_COLORS.get("original_baseline"), label="Original archived front")
    ax.plot(archive_df[x_archive], archive_df[y_archive], alpha=0.75,
            color=SCENARIO_COLORS.get("original_baseline"))

    ax.scatter(reeval_df[x_reeval], reeval_df[y_reeval], s=18, alpha=0.65,
               color=SCENARIO_COLORS.get("expected"), label="Re-evaluated front")
    ax.plot(reeval_df[x_reeval], reeval_df[y_reeval], alpha=0.75,
            color=SCENARIO_COLORS.get("expected"))

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, linestyle='--', color='gray', linewidth=1, alpha=0.3)
    ax.legend()
    save_figure(fig, outfile)


def plot_one_to_one(df: pd.DataFrame, xcol: str, ycol: str, title: str, outfile: str | Path):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(df[xcol], df[ycol], alpha=0.75, s=25)
    mn = min(df[xcol].min(), df[ycol].min())
    mx = max(df[xcol].max(), df[ycol].max())
    ax.plot([mn, mx], [mn, mx], linestyle="--", color="0.35", label="1:1")
    ax.set_xlabel(xcol)
    ax.set_ylabel(ycol)
    ax.set_title(title)
    ax.legend()
    save_figure(fig, outfile)


def plot_scenario_lines(
    df: pd.DataFrame,
    xcol: str,
    ycols_by_scenario: dict[str, str],
    xlabel: str,
    ylabel: str,
    title: str,
    outfile: str | Path,
    colors: dict[str, str] | None = None,
    labels: dict[str, str] | None = None,
):
    """Plot multiple scenario columns against a shared x-axis."""
    colors = SCENARIO_COLORS if colors is None else colors
    labels = SCENARIO_LABELS if labels is None else labels
    plot_df = sort_for_plot(df, xcol=xcol)
    fig, ax = plt.subplots()
    for scen, ycol in ycols_by_scenario.items():
        if ycol not in plot_df.columns:
            continue
        ax.plot(
            plot_df[xcol], plot_df[ycol], marker="o", markersize=3,
            color=colors.get(scen, None), label=labels.get(scen, scen), alpha=0.9
        )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    save_figure(fig, outfile)


def plot_original_mou_tradeoffs(
    tradeoffs: pd.DataFrame,
    ycol: str,
    ylabel: str,
    title: str,
    outfile: str | Path,
    xcol: str = "total_pumping_cfs",
    colors: dict[str, str] | None = None,
    labels: dict[str, str] | None = None,
):
    """Plot original fully optimized MOU fronts from user-created tradeoff CSVs."""
    if tradeoffs.empty:
        print("No original MOU tradeoff data were loaded; skipping plot:", outfile)
        return
    colors = SCENARIO_COLORS if colors is None else colors
    labels = SCENARIO_LABELS if labels is None else labels
    fig, ax = plt.subplots()
    for scen, group in tradeoffs.groupby("scenario", sort=False):
        group = group.sort_values(xcol)
        ax.scatter(group[xcol], group[ycol], s=22, alpha=0.65, color=colors.get(scen, None))
        ax.plot(group[xcol], group[ycol], alpha=0.65, color=colors.get(scen, None), label=labels.get(scen, scen))
    ax.set_xlabel("Total pumping from original MOU front (cfs)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    save_figure(fig, outfile)


# =============================================================================
# Additional probability-distribution and combined-figure helpers for notebook 202
# =============================================================================

def _normal_pdf(x, mean: float, sigma: float):
    """Return the normal probability density function evaluated at x."""
    x = np.asarray(x, dtype=float)
    return (1.0 / (sigma * np.sqrt(2.0 * np.pi))) * np.exp(-0.5 * ((x - mean) / sigma) ** 2)


def infer_sigma_fraction_from_probability_table(T_probability_table: pd.DataFrame) -> float:
    """
    Infer the sigma of the T-factor probability model from the saved probability table.

    Preferred method:
        use the relationship T_factor = 1 + z_score * sigma_fraction.

    Fallback:
        compute the weighted standard deviation of T_factor around 1.0 using the
        discrete probability weights. This is robust even if z_score is absent.
    """
    table = T_probability_table.copy()
    if "T_factor" not in table.columns:
        raise KeyError("T_probability_table must contain 'T_factor'.")

    table["T_factor"] = pd.to_numeric(table["T_factor"], errors="coerce")

    if "z_score" in table.columns:
        table["z_score"] = pd.to_numeric(table["z_score"], errors="coerce")
        valid = table["z_score"].notna() & (table["z_score"] != 0) & table["T_factor"].notna()
        if valid.any():
            sigma_vals = ((table.loc[valid, "T_factor"] - 1.0).abs() / table.loc[valid, "z_score"].abs())
            sigma_vals = sigma_vals.replace([np.inf, -np.inf], np.nan).dropna()
            if not sigma_vals.empty:
                return float(sigma_vals.median())

    if "probability_weight" in table.columns:
        weights = pd.to_numeric(table["probability_weight"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        factors = table["T_factor"].to_numpy(dtype=float)
        valid = np.isfinite(factors) & np.isfinite(weights) & (weights >= 0)
        factors = factors[valid]
        weights = weights[valid]
        if factors.size > 0 and weights.sum() > 0:
            weights = weights / weights.sum()
            mean_factor = np.sum(weights * factors)
            return float(np.sqrt(np.sum(weights * (factors - mean_factor) ** 2)))

    raise ValueError("Could not infer sigma_fraction from T_probability_table.")


def infer_n_sigma_each_side_from_probability_table(T_probability_table: pd.DataFrame, sigma_fraction: float | None = None) -> float:
    """Infer the sampled +/-N sigma extent from the T-factor probability table."""
    sigma_fraction = infer_sigma_fraction_from_probability_table(T_probability_table) if sigma_fraction is None else float(sigma_fraction)
    table = T_probability_table.copy()
    table["T_factor"] = pd.to_numeric(table["T_factor"], errors="coerce")
    max_dev = float((table["T_factor"] - 1.0).abs().max())
    if sigma_fraction <= 0:
        raise ValueError("sigma_fraction must be positive.")
    return max_dev / sigma_fraction


def plot_T_probability_weights_with_curve(
    T_probability_table: pd.DataFrame,
    sigma_fraction: float | None,
    outfile: str | Path,
    title: str = "Discrete T probability weights with continuous normal curve",
):
    """
    Plot discrete probability weights for sampled T factors with a bell-curve overlay.

    The bars show the actual discrete weights used in the probability-weighted
    PyCap runs. The smooth curve shows the corresponding continuous normal model.
    For display only, the continuous curve is scaled to the probability-weight
    axis so the shapes can be compared visually.
    """
    required = {"T_factor", "probability_weight"}
    missing = required - set(T_probability_table.columns)
    if missing:
        raise KeyError(f"T_probability_table is missing required columns: {sorted(missing)}")

    table = T_probability_table.sort_values("T_factor").copy()
    table["T_factor"] = pd.to_numeric(table["T_factor"], errors="coerce")
    table["probability_weight"] = pd.to_numeric(table["probability_weight"], errors="coerce")
    table = table.dropna(subset=["T_factor", "probability_weight"])

    factors = table["T_factor"].to_numpy(dtype=float)
    weights = table["probability_weight"].to_numpy(dtype=float)

    sigma_factor = infer_sigma_fraction_from_probability_table(table) if sigma_fraction is None else float(sigma_fraction)
    mean_factor = 1.0

    if len(factors) > 1:
        dx = float(np.median(np.diff(factors)))
    else:
        dx = sigma_factor / 2.5 if sigma_factor > 0 else 0.025

    x_left = min(factors.min(), mean_factor - 3.0 * sigma_factor)
    x_right = max(factors.max(), mean_factor + 3.0 * sigma_factor)
    x = np.linspace(x_left, x_right, 700)
    pdf = _normal_pdf(x, mean_factor, sigma_factor)

    # Convert density to approximate probability mass over one bar width so the
    # continuous curve can share the bar-chart y-axis.
    pdf_mass = pdf * dx

    fig, ax = plt.subplots(figsize=(10.0, 6.0))
    bar_width = dx * 0.72 if len(factors) > 1 else 0.025
    ax.bar(
        factors,
        weights,
        width=bar_width,
        color="#A7C7E7",
        edgecolor="0.35",
        linewidth=0.9,
        alpha=0.88,
        label="Discrete T weights used in PyCap runs",
        zorder=2,
    )
    ax.plot(
        x,
        pdf_mass,
        color=SCENARIO_COLORS.get("expected", "#6A4C93"),
        linewidth=2.4,
        label="Normal bell curve, scaled to weights",
        zorder=3,
    )
    ax.axvline(1.0, color="0.25", linestyle="--", linewidth=1.2, label="Baseline T", zorder=1)

    ax.set_xlim(x_left - 0.01, x_right + 0.01)
    ax.set_xlabel("T factor relative to baseline T")
    ax.set_ylabel("Probability weight")
    ax.set_title(title)
    ax.legend(loc="best")

    save_figure(fig, outfile)



def plot_T_probability_shaded_sigma_regions(
    sigma_fraction: float,
    n_sigma_each_side: float,
    outfile: str | Path,
    title: str = "Normal probability model for T uncertainty",
):
    """
    Plot the normal distribution for T factor with shaded sigma regions.

    This is a teaching/interpretation figure. The shaded bands and interval
    brackets are drawn in data coordinates, so the ±1σ and ±2σ annotations span
    the correct T-factor ranges.
    """
    sigma = float(sigma_fraction)
    max_sigma = max(float(n_sigma_each_side), 3.0)
    x_min = 1.0 - max_sigma * sigma
    x_max = 1.0 + max_sigma * sigma
    x = np.linspace(x_min, x_max, 1200)
    y = _normal_pdf(x, 1.0, sigma)
    ymax = float(y.max())

    fig, ax = plt.subplots(figsize=(10, 6.0))

    intervals = [
        (-3, -2, "#DCECF7", "2.1%"),
        (-2, -1, "#BFDDF2", "13.6%"),
        (-1, 0, "#8CC7E8", "34.1%"),
        (0, 1, "#8CC7E8", "34.1%"),
        (1, 2, "#BFDDF2", "13.6%"),
        (2, 3, "#DCECF7", "2.1%"),
    ]
    for left_z, right_z, color, label in intervals:
        left = 1.0 + left_z * sigma
        right = 1.0 + right_z * sigma
        mask = (x >= left) & (x <= right)
        if mask.any():
            ax.fill_between(x[mask], y[mask], color=color, alpha=0.95)
            x_mid = (left + right) / 2.0
            y_mid = _normal_pdf(x_mid, 1.0, sigma)
            ax.text(x_mid, y_mid * 0.18, label, ha="center", va="center", fontsize=9)

    ax.plot(x, y, color=SCENARIO_COLORS.get("expected", "#6A4C93"), linewidth=2.5)

    z_ticks = [-3, -2, -1, 0, 1, 2, 3]
    tick_positions = [1.0 + z * sigma for z in z_ticks]
    tick_labels = [f"{z:+d}σ\n{pos:.2f}" if z != 0 else f"μ\n{1.0:.2f}" for z, pos in zip(z_ticks, tick_positions)]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)

    for z, pos in zip(z_ticks, tick_positions):
        line_alpha = 0.55 if abs(z) <= n_sigma_each_side else 0.15
        ax.axvline(pos, color="0.45", linestyle=":" if z != 0 else "--", linewidth=1.1, alpha=line_alpha)

    def draw_interval_bracket(ax, x0, x1, y_level, label, end_frac=0.045, text_pad_frac=0.012):
        """Draw a clean data-coordinate bracket spanning x0 to x1 at y_level."""
        end_h = ymax * end_frac
        ax.plot([x0, x1], [y_level, y_level], color="0.4", lw=1.1)
        ax.plot([x0, x0], [y_level, y_level - end_h], color="0.4", lw=1.1)
        ax.plot([x1, x1], [y_level, y_level - end_h], color="0.4", lw=1.1)
        ax.text((x0 + x1) / 2.0, y_level + ymax * text_pad_frac, label, ha="center", va="bottom", fontsize=10)

    # Precise empirical-rule brackets.
    draw_interval_bracket(ax, 1.0 - 1.0 * sigma, 1.0 + 1.0 * sigma, ymax * 1.04, "~68.2% within ±1σ")
    draw_interval_bracket(ax, 1.0 - 2.0 * sigma, 1.0 + 2.0 * sigma, ymax * 1.22, "~95.4% within ±2σ")

    ax.set_ylim(0, ymax * 1.38)
    ax.set_xlabel("T factor relative to baseline T")
    ax.set_ylabel("Probability density")
    ax.set_title(title)
    ax.text(
        0.02,
        0.96,
        f"Mean T factor = 1.0\n1σ = ±{sigma_fraction:.0%}\nSampled range = ±{n_sigma_each_side:g}σ",
        transform=ax.transAxes,
        ha="left",
        va="top",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="0.75", alpha=0.9),
        fontsize=9,
    )

    save_figure(fig, outfile)



def plot_probability_weighted_streamflow_dashboard(
    sigma_fraction: float,
    n_sigma_each_side: float,
    outfile: str | Path,
    title: str = "Normal probability model for T uncertainty",
):
    """
    Plot the normal distribution for T factor with shaded sigma regions.

    This is a teaching/interpretation figure. It shows how the chosen probability
    model maps standard deviations onto T-factor space. For the current project
    default, sigma_fraction=0.10 means one standard deviation is +/-10% in T, so
    +/-2 sigma corresponds to T factors 0.8 to 1.2.
    """
    sigma = float(sigma_fraction)
    max_sigma = max(float(n_sigma_each_side), 3.0)
    x_min = 1.0 - max_sigma * sigma
    x_max = 1.0 + max_sigma * sigma
    x = np.linspace(x_min, x_max, 1000)
    y = _normal_pdf(x, 1.0, sigma)

    fig, ax = plt.subplots(figsize=(10., 6.0))

    # Color sigma intervals symmetrically. The labels use the familiar empirical
    # rule percentages to make the figure easier to connect to the uploaded
    # examples: ~68% within +/-1 sigma, ~95% within +/-2 sigma, ~99.7% within +/-3.
    intervals = [
        (-3, -2, "#DCECF7", "2.1%"),
        (-2, -1, "#BFDDF2", "13.6%"),
        (-1, 0, "#8CC7E8", "34.1%"),
        (0, 1, "#8CC7E8", "34.1%"),
        (1, 2, "#BFDDF2", "13.6%"),
        (2, 3, "#DCECF7", "2.1%"),
    ]
    for left_z, right_z, color, label in intervals:
        left = 1.0 + left_z * sigma
        right = 1.0 + right_z * sigma
        mask = (x >= left) & (x <= right)
        if mask.any():
            ax.fill_between(x[mask], y[mask], color=color, alpha=0.95)
            x_mid = (left + right) / 2.0
            y_mid = _normal_pdf(x_mid, 1.0, sigma)
            ax.text(x_mid, y_mid * 0.18, label, ha="center", va="center", fontsize=9)

    ax.plot(x, y, color=SCENARIO_COLORS.get("expected", "#6A4C93"), linewidth=2.2)

    # Mark baseline, +/-1 sigma, and +/-2 sigma clearly. These are the most
    # important reference points for this project because the default sampled
    # range is +/-2 sigma.
    z_ticks = [-3, -2, -1, 0, 1, 2, 3]
    tick_positions = [1.0 + z * sigma for z in z_ticks]
    tick_labels = [f"{z:+d}σ\n{pos:.2f}" if z != 0 else f"μ\n{1.0:.2f}" for z, pos in zip(z_ticks, tick_positions)]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)

    for z, pos in zip(z_ticks, tick_positions):
        line_alpha = 0.55 if abs(z) <= n_sigma_each_side else 0.15
        ax.axvline(pos, color="0.35", linestyle=":" if z != 0 else "--", linewidth=1.0, alpha=line_alpha)

    # Brackets/annotations for the empirical-rule interpretation.
    ymax = y.max()
    ax.annotate("~68% within ±1σ", xy=(1.0, ymax * 1.03), xytext=(1.0, ymax * 1.16), ha="center",
                arrowprops=dict(arrowstyle="-[,widthB=4.5,lengthB=0.7", lw=1.0, color="0.35"), fontsize=9)
    ax.annotate("~95% within ±2σ", xy=(1.0, ymax * 1.22), xytext=(1.0, ymax * 1.34), ha="center",
                arrowprops=dict(arrowstyle="-[,widthB=8.8,lengthB=0.7", lw=1.0, color="0.35"), fontsize=9)

    ax.set_ylim(0, ymax * 1.42)
    ax.set_xlabel("T factor relative to baseline T")
    ax.set_ylabel("Probability density")
    ax.set_title(title)
    ax.text(
        0.02,
        0.96,
        f"Mean T factor = 1.0\n1σ = ±{sigma_fraction:.0%}\nSampled range = ±{n_sigma_each_side:g}σ",
        transform=ax.transAxes,
        ha="left",
        va="top",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="0.75", alpha=0.9),
        fontsize=9,
    )

    save_figure(fig, outfile)


def plot_probability_weighted_streamflow_dashboard(
    member_summary: pd.DataFrame,
    xcol: str,
    outfile: str | Path,
    title: str = "Probability-weighted streamflow uncertainty and cost metrics",
):
    """
    Create a combined report figure for Notebook 202 / 203.

    Layout:
        - Left panel spans all 3 rows:
            Expected streamflow with uncertainty band.
        - Right top:
            Probability-weighted absolute streamflow error.
        - Right middle:
            Probability-weighted streamflow shortfall.
        - Right bottom:
            Streamflow standard deviation.

    This puts the main hydrologic prediction and the three uncertainty/cost
    diagnostics into one report-ready figure.
    """
    required = {
        xcol,
        "baseline_T_streamflow_cfs",
        "expected_streamflow_cfs",
        "streamflow_p05_cfs",
        "streamflow_p95_cfs",
        "probability_weighted_absolute_streamflow_error_cfs",
        "probability_weighted_streamflow_shortfall_cfs",
        "streamflow_std_cfs",
    }
    missing = required - set(member_summary.columns)
    if missing:
        raise KeyError(f"member_summary is missing required columns: {sorted(missing)}")

    plot_df = sort_for_plot(member_summary, xcol=xcol)
    x = plot_df[xcol]

    fig = plt.figure(figsize=(14.0, 9.0))

    gs = fig.add_gridspec(
        3,
        2,
        width_ratios=[1.65, 1.0],
        height_ratios=[1.0, 1.0, 1.0],
        wspace=0.30,
        hspace=0.42,
    )

    ax_left = fig.add_subplot(gs[:, 0])
    ax_top = fig.add_subplot(gs[0, 1])
    ax_middle = fig.add_subplot(gs[1, 1], sharex=ax_top)
    ax_bottom = fig.add_subplot(gs[2, 1], sharex=ax_top)

    # -------------------------------------------------------------------------
    # Left panel: main hydrologic prediction with uncertainty band
    # -------------------------------------------------------------------------
    ax_left.plot(
        x,
        plot_df["baseline_T_streamflow_cfs"],
        linestyle="--",
        color=SCENARIO_COLORS.get("baseline_T"),
        label="Baseline-T prediction",
    )

    ax_left.plot(
        x,
        plot_df["expected_streamflow_cfs"],
        color=SCENARIO_COLORS.get("expected"),
        label="Probability-weighted expected streamflow",
    )

    ax_left.fill_between(
        x,
        plot_df["streamflow_p05_cfs"],
        plot_df["streamflow_p95_cfs"],
        color=SCENARIO_COLORS.get("uncertainty_band", "0.7"),
        alpha=0.25,
        label="Weighted 5th–95th percentile range",
    )

    ax_left.set_xlabel("Effective total pumping after fish-dollars cutoff (cfs)")
    ax_left.set_ylabel("Streamflow = 8.6 cfs - depletion (cfs)")
    ax_left.set_title("A. Expected streamflow with T uncertainty band")
    ax_left.legend(loc="best")

    # -------------------------------------------------------------------------
    # Right top: absolute streamflow error
    # -------------------------------------------------------------------------
    ax_top.plot(
        x,
        plot_df["probability_weighted_absolute_streamflow_error_cfs"],
        marker="o",
        markersize=3,
        color=SCENARIO_COLORS.get("expected"),
    )

    # ax_top.set_xlabel("Effective total pumping (cfs)")
    ax_top.set_ylabel("Abs. streamflow error (cfs)")
    ax_top.set_title("B. Probability-weighted absolute error")

    # -------------------------------------------------------------------------
    # Right middle: one-sided shortfall
    # -------------------------------------------------------------------------
    ax_middle.plot(
        x,
        plot_df["probability_weighted_streamflow_shortfall_cfs"],
        marker="o",
        markersize=3,
        color=SCENARIO_COLORS.get("T_plus_10pct"),
    )

    # ax_middle.set_xlabel("Effective total pumping (cfs)")
    ax_middle.set_ylabel("Streamflow shortfall (cfs)")
    ax_middle.set_title("C. Probability-weighted streamflow shortfall")

    # -------------------------------------------------------------------------
    # Right bottom: streamflow standard deviation
    # -------------------------------------------------------------------------
    ax_bottom.plot(
        x,
        plot_df["streamflow_std_cfs"],
        marker="o",
        markersize=3,
        color="0.35",
    )

    ax_bottom.set_xlabel("Effective total pumping (cfs)")
    ax_bottom.set_ylabel("Streamflow std. dev. (cfs)")
    ax_bottom.set_title("D. Streamflow standard deviation")

    fig.suptitle(title, y=0.95, fontsize=PLOT_STYLE.get("axes.titlesize", 12) + 2)

    save_figure(fig, outfile)