"""
Helper functions for the Little Plover River PyCap transmissivity uncertainty
project using the depletion_q objective.

Recommended location:
    /workspaces/LPR_redux/LPR_pycap_opt/notebooks/Uncertainty_Project_depletion_q/

This helper intentionally uses a new module name instead of reusing the old
fish-dollars helper. That avoids Jupyter import-cache confusion and keeps the
hydrologic depletion_q workflow separate from the earlier fish_dollars prototype.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import copy
import importlib.util
import os
import sys
import traceback

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError
import matplotlib.pyplot as plt
import pyemu

HELPER_VERSION = "2026-05-24_depletion_q_304_v7_full_uncertainty_annotation_higher"

GPM2CFS = 0.002228
HISTORIC_STREAMFLOW_CFS = 8.6
DEPLETION_OBS_NAME = "lpr:total_combined:bdpl"
PUMPING_COLUMN_FOR_HYDRO_PLOTS = "pumping_objective_reeval_cfs"

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

SCENARIO_COLORS = {
    "archive": "#8FC3DA",       # light blue: original archived front
    "reeval": "#2E86AB",        # darker blue: re-evaluated front
    "expected": "#6A4C93",
    "baseline_T": "#2E86AB",
    "T_minus_10pct": "#3A923A",
    "T_plus_10pct": "#D1495B",
    "uncertainty_band": "#A6A6A6",
}


@dataclass
class DepletionQContext:
    """Container for the source depletion_q PyCap/PEST++ run."""
    run_name: str
    project_dir: Path
    run_dir: Path
    script_path: Path
    module: object
    initial_dict_master: dict
    bdplobs: object
    obsnames: list[str]
    base_T: float
    pst_path: Path
    all_q_cols: list[str]
    decvar_q_cols: list[str]
    fixed_q_cols: list[str]


# =============================================================================
# Path and import helpers
# =============================================================================

def find_lpr_pycap_opt_dir(start: str | Path | None = None) -> Path:
    """
    Find the LPR_pycap_opt directory by walking upward from the current directory.
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
    """Create and return standard output/cache directories for a notebook."""
    notebook_dir = Path(notebook_dir)
    output_dir = notebook_dir / "project_output" / f"{notebook_number}_{notebook_slug}"
    cache_dir = notebook_dir / "cached_reevaluations"
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return {"output_dir": output_dir, "cache_dir": cache_dir}


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


def find_depletion_q_forward_script(project_dir: str | Path, run_dir: str | Path) -> Path:
    """
    Locate the source-of-truth depletion_q forward script.

    For the depletion_q objective, the original MOU setup uses:
        run_pycap_standalone_opt_mou.py

    Prefer the copy in the run folder because it is the exact script copied into
    the PEST++ run. Fall back to LPR_pycap_opt/scripts/ if needed.
    """
    project_dir = Path(project_dir)
    run_dir = Path(run_dir)
    candidates = [
        run_dir / "run_pycap_standalone_opt_mou.py",
        project_dir / "scripts" / "run_pycap_standalone_opt_mou.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not find run_pycap_standalone_opt_mou.py in the run folder or scripts folder."
    )


def read_obsnames_from_instruction_file(run_dir: str | Path) -> list[str]:
    """Read observation names from allobs.out.ins using the original script convention."""
    ins_file = Path(run_dir) / "allobs.out.ins"
    if not ins_file.exists():
        raise FileNotFoundError(f"Missing instruction file: {ins_file}")
    return [line.split("!")[1].lower() for line in ins_file.read_text().splitlines()[1:] if "!" in line]


def load_depletion_q_context(run_name: str, project_dir: str | Path | None = None) -> DepletionQContext:
    """
    Load the original depletion_q forward-model context for a PEST++ MOU run.

    The original instantiate() function uses relative paths, so this helper
    temporarily changes into the run directory, calls instantiate(), and then
    returns to the original working directory.
    """
    project_dir = find_lpr_pycap_opt_dir() if project_dir is None else Path(project_dir)
    run_dir = project_dir / "pycap_runs" / "pycap_pest" / f"run_{run_name}"
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory does not exist: {run_dir}")

    script_path = find_depletion_q_forward_script(project_dir, run_dir)
    module_name = f"depletion_q_forward_{abs(hash(str(script_path))) % 10**8}"
    module = import_python_file(module_name, script_path)

    original_cwd = Path.cwd()
    os.chdir(run_dir)
    try:
        initial_dict_master, bdplobs = module.instantiate()
    finally:
        os.chdir(original_cwd)

    obsnames = read_obsnames_from_instruction_file(run_dir)
    base_T = float(initial_dict_master["project_properties"]["T"])

    # For depletion_q, the PEST++ objective `obj_well` is the sum of only the
    # decision-variable pumping parameters, not the total pumping from all wells.
    all_q_cols, decvar_q_cols, fixed_q_cols = read_pst_q_column_groups(run_name, run_dir)
    pst_path = run_dir / f"{run_name}.pst"

    return DepletionQContext(
        run_name=run_name,
        project_dir=project_dir,
        run_dir=run_dir,
        script_path=script_path,
        module=module,
        initial_dict_master=initial_dict_master,
        bdplobs=bdplobs,
        obsnames=obsnames,
        base_T=base_T,
        pst_path=pst_path,
        all_q_cols=all_q_cols,
        decvar_q_cols=decvar_q_cols,
        fixed_q_cols=fixed_q_cols,
    )


# =============================================================================
# Data loading helpers
# =============================================================================

def read_pareto_archive_summary(run_name_or_path: str | Path, run_dir: str | Path | None = None) -> pd.DataFrame:
    """
    Read the PEST++ MOU Pareto archive summary CSV zip.

    This function accepts either of these calling styles:

        read_pareto_archive_summary(run_name, run_dir)
        read_pareto_archive_summary(path_to_archive_zip)

    The second form is included to make notebooks less fragile while we rebuild
    the depletion_q workflow.
    """
    if run_dir is None:
        pareto_file = Path(run_name_or_path)
    else:
        run_name = str(run_name_or_path)
        pareto_file = Path(run_dir) / f"{run_name}.pareto.archive.summary.csv.zip"

    if not pareto_file.exists():
        raise FileNotFoundError(f"Missing Pareto archive summary: {pareto_file}")

    df = pd.read_csv(pareto_file)
    if "member" not in df.columns:
        raise KeyError("Pareto archive summary is missing the 'member' column.")
    df["member"] = df["member"].astype(str)
    return df


def select_final_feasible_front1(
    pareto_df: pd.DataFrame,
    depletion_obs_name: str = DEPLETION_OBS_NAME,
    n_test_members: int | None = None,
) -> pd.DataFrame:
    """
    Select final-generation, feasible, NSGA-II front-1 members.
    """
    required = {"member", "generation", "nsga2_front", "is_feasible", "obj_well", depletion_obs_name}
    missing = required - set(pareto_df.columns)
    if missing:
        raise KeyError(f"Pareto archive summary is missing required columns: {sorted(missing)}")

    df = pareto_df.loc[
        (pareto_df["nsga2_front"] == 1) &
        (pareto_df["is_feasible"] == 1)
    ].copy()

    if df.empty:
        raise ValueError("No feasible front-1 members were found.")

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

    Final archive members can come from any saved population, so include all
    saved dv_pop files plus initial_dvpop.csv if present.
    """
    run_dir = Path(run_dir)
    dv_files = sorted(run_dir.glob("*dv_pop.csv.zip")) + sorted(run_dir.glob("*dv_pop.csv"))
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


def get_q_columns(df: pd.DataFrame) -> list[str]:
    """Return pumping-parameter columns from a population table."""
    return [c for c in df.columns if str(c).lower().endswith("__q") or "__q" in str(c).lower()]


def match_columns_case_insensitive(df: pd.DataFrame, requested_names: list[str]) -> list[str]:
    """Return DataFrame columns matching requested names, ignoring case."""
    lookup = {str(c).lower(): c for c in df.columns}
    matched = []
    for name in requested_names:
        key = str(name).lower()
        if key in lookup:
            matched.append(lookup[key])
    return matched


def read_pst_q_column_groups(run_name: str, run_dir: str | Path) -> tuple[list[str], list[str], list[str]]:
    """
    Read the PEST control file and return all pumping, decision-variable pumping,
    and fixed pumping parameter names.

    Important for depletion_q:
        The archived `obj_well` objective is the prior-information equation that
        sums only parameters in the `decvars` group. It does NOT equal the sum of
        every pumping parameter in the model.
    """
    run_dir = Path(run_dir)
    pst_path = run_dir / f"{run_name}.pst"
    if not pst_path.exists():
        raise FileNotFoundError(f"Missing PEST control file: {pst_path}")

    pst = pyemu.Pst(str(pst_path))
    pars = pst.parameter_data.copy()
    pars.index = pars.index.astype(str).str.lower()
    pars["parnme_lower"] = pars["parnme"].astype(str).str.lower()
    pars["pargp_lower"] = pars["pargp"].astype(str).str.lower()
    pars["partrans_lower"] = pars["partrans"].astype(str).str.lower()

    all_q = pars.loc[pars["parnme_lower"].str.endswith("__q"), "parnme_lower"].tolist()
    decvar_q = pars.loc[
        pars["parnme_lower"].str.endswith("__q") & (pars["pargp_lower"] == "decvars"),
        "parnme_lower",
    ].tolist()
    fixed_q = [c for c in all_q if c not in set(decvar_q)]

    if not all_q:
        raise ValueError(f"No pumping parameters ending in '__q' were found in {pst_path}")
    if not decvar_q:
        raise ValueError(f"No decision-variable pumping parameters were found in {pst_path}")

    return all_q, decvar_q, fixed_q


# =============================================================================
# Re-evaluation helpers
# =============================================================================

def make_initial_dict_with_T(
    initial_dict_master: dict,
    t_factor: float | None = None,
    t_value: float | None = None,
) -> dict:
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


def run_original_depletion_q_get_results(
    q_row: pd.Series,
    context: DepletionQContext,
    t_factor: float | None = 1.0,
    t_value: float | None = None,
) -> pd.Series:
    """
    Call the original depletion_q get_results() function for one pumping design.

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
        write_csv=False,
    )
    return result


def reevaluate_depletion_q_designs(
    pareto_final: pd.DataFrame,
    dv_df: pd.DataFrame,
    q_cols: list[str],
    context: DepletionQContext,
    scenarios: dict[str, float | dict],
    historic_streamflow_cfs: float = HISTORIC_STREAMFLOW_CFS,
    depletion_obs_name: str = DEPLETION_OBS_NAME,
    progress_every: int = 50,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Re-evaluate a set of depletion_q Pareto designs under one or more T scenarios.
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

        for _, row in pareto_final.reset_index(drop=True).iterrows():
            counter += 1
            member = str(row["member"])
            if counter == 1 or counter % progress_every == 0 or counter == n_total:
                print(f"  Re-evaluating {counter} of {n_total}: scenario={scenario_label}, member={member}")

            try:
                if member not in dv_df.index:
                    raise KeyError(f"Member {member!r} was not found in the decision-variable population.")
                # The population file may contain all pumping parameters. For the
                # forward model, passing all available Q parameters is fine because fixed
                # parameters are at their original values.
                model_q_cols = match_columns_case_insensitive(dv_df, q_cols)
                if not model_q_cols:
                    raise KeyError("No model pumping columns were found in dv_df.")
                q_row = dv_df.loc[member, model_q_cols].copy()

                reeval = run_original_depletion_q_get_results(
                    q_row=q_row,
                    context=context,
                    t_factor=t_factor_actual,
                    t_value=t_value_actual,
                )

                # Important: the depletion_q archived objective `obj_well` is NOT
                # the sum of all model pumping. It is the sum of the decision-variable
                # pumping parameters only. This was the source of the original pumping
                # mismatch in Notebook 300.
                objective_q_cols = match_columns_case_insensitive(dv_df, context.decvar_q_cols)
                if not objective_q_cols:
                    raise KeyError("No decision-variable pumping columns were found in dv_df.")

                pumping_objective_gpm = dv_df.loc[member, objective_q_cols].astype(float).sum()
                pumping_objective_cfs = pumping_objective_gpm * GPM2CFS

                full_model_total_pumping_gpm = q_row.astype(float).sum()
                full_model_total_pumping_cfs = full_model_total_pumping_gpm * GPM2CFS

                archive_pumping_objective_gpm = row.get("obj_well", np.nan)
                archive_pumping_objective_cfs = archive_pumping_objective_gpm * GPM2CFS

                depletion_cfs = reeval.loc[depletion_obs_name] if depletion_obs_name in reeval.index else np.nan
                streamflow_cfs = historic_streamflow_cfs - depletion_cfs

                records.append({
                    "scenario": scenario_label,
                    "T_factor": t_factor_actual,
                    "T_value": t_value_actual,
                    "probability_weight": prob_weight,
                    "member": member,
                    "generation": row.get("generation", np.nan),

                    # Archived objective values.
                    "archive_pumping_objective_gpm": archive_pumping_objective_gpm,
                    "archive_pumping_objective_cfs": archive_pumping_objective_cfs,
                    "archive_total_pumping_gpm": archive_pumping_objective_gpm,
                    "archive_total_pumping_cfs": archive_pumping_objective_cfs,
                    "archive_depletion_cfs": row.get(depletion_obs_name, np.nan),
                    "archive_streamflow_cfs": historic_streamflow_cfs - row.get(depletion_obs_name, np.nan),

                    # Re-evaluated pumping objective: only decision-variable pumping.
                    "pumping_objective_reeval_gpm": pumping_objective_gpm,
                    "pumping_objective_reeval_cfs": pumping_objective_cfs,
                    "total_pumping_gpm": pumping_objective_gpm,
                    "total_pumping_cfs": pumping_objective_cfs,

                    # Diagnostic only: full model pumping including fixed/background wells.
                    "full_model_total_pumping_gpm": full_model_total_pumping_gpm,
                    "full_model_total_pumping_cfs": full_model_total_pumping_cfs,

                    "n_model_q_columns": len(model_q_cols),
                    "n_objective_q_columns": len(objective_q_cols),
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


# =============================================================================
# Validation-summary helpers
# =============================================================================

def build_300_validation_comparison(results_long: pd.DataFrame) -> pd.DataFrame:
    """Create a clean baseline validation comparison table from baseline results."""
    if results_long.empty:
        raise ValueError("results_long is empty.")
    df = results_long.loc[results_long["scenario"] == "baseline_T"].copy()
    if df.empty:
        raise ValueError("No baseline_T rows found in results_long.")

    # Compare the archived `obj_well` objective against the re-evaluated
    # decision-variable pumping sum. This is the correct depletion_q pumping
    # objective. Do not compare against full_model_total_pumping_cfs.
    df["pumping_objective_abs_diff_cfs"] = (
        df["pumping_objective_reeval_cfs"] - df["archive_pumping_objective_cfs"]
    ).abs()
    # Backward-compatible alias used by plotting and summary code.
    df["total_pumping_abs_diff_cfs"] = df["pumping_objective_abs_diff_cfs"]

    df["depletion_abs_diff_cfs"] = (df["depletion_cfs"] - df["archive_depletion_cfs"]).abs()
    df["streamflow_abs_diff_cfs"] = (df["streamflow_cfs"] - df["archive_streamflow_cfs"]).abs()

    return df


def summarize_300_validation(
    comparison: pd.DataFrame,
    error_df: pd.DataFrame | None = None,
    pumping_abs_tol_cfs: float = 1.0e-3,
    depletion_abs_tol_cfs: float = 1.0e-5,
) -> pd.DataFrame:
    """Summarize depletion_q baseline validation results.

    For the depletion_q objective, the archived pumping objective is obj_well,
    which is the sum of the decision-variable pumping parameters. The full
    model pumping total is retained as a diagnostic elsewhere, but it is not
    the correct validation target for the archived Pareto objective.

    Streamflow is mathematically redundant with depletion here because
    streamflow = 8.6 cfs - depletion. Therefore, this validation table checks
    the pumping objective and depletion only. Streamflow differences remain in
    the comparison CSV as a diagnostic column.
    """
    error_df = pd.DataFrame() if error_df is None else error_df

    max_pump = float(comparison["pumping_objective_abs_diff_cfs"].max()) if not comparison.empty else np.nan
    max_dep = float(comparison["depletion_abs_diff_cfs"].max()) if not comparison.empty else np.nan
    max_stream = float(comparison["streamflow_abs_diff_cfs"].max()) if "streamflow_abs_diff_cfs" in comparison.columns and not comparison.empty else np.nan

    pumping_passed = bool(max_pump <= pumping_abs_tol_cfs)
    depletion_passed = bool(max_dep <= depletion_abs_tol_cfs)
    hydrologic_passed = bool(pumping_passed and depletion_passed and len(error_df) == 0)

    rows = [
        ("n_members_attempted", len(comparison) + len(error_df)),
        ("n_members_successful", len(comparison)),
        ("n_members_error", len(error_df)),
        ("max_pumping_objective_abs_diff_cfs", max_pump),
        ("max_depletion_abs_diff_cfs", max_dep),
        ("max_streamflow_abs_diff_cfs_diagnostic", max_stream),
        ("pumping_objective_abs_tolerance_cfs", pumping_abs_tol_cfs),
        ("depletion_abs_tolerance_cfs", depletion_abs_tol_cfs),
        ("pumping_objective_validation_passed", pumping_passed),
        ("depletion_validation_passed", depletion_passed),
        ("hydrologic_validation_passed", hydrologic_passed),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


# =============================================================================
# Plotting helpers
# =============================================================================

def apply_plot_style(style: dict | None = None):
    """Apply matplotlib defaults for report-ready plots."""
    plt.rcParams.update(PLOT_STYLE)
    if style:
        plt.rcParams.update(style)



def read_csv_if_not_empty(path: str | Path, **kwargs) -> pd.DataFrame:
    """
    Read a CSV file only if it exists and contains data.

    This is mainly for error-cache CSVs. If a run has zero errors, pandas may
    create an empty CSV file with no columns. Reading that file normally raises
    pandas.errors.EmptyDataError. Returning an empty DataFrame is the correct
    behavior in that case.
    """
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, **kwargs)
    except EmptyDataError:
        return pd.DataFrame()


def write_error_cache(error_df: pd.DataFrame, path: str | Path) -> None:
    """Write an error cache that can always be read later.

    If there are no errors, write a header-only table instead of a completely
    blank file. This prevents EmptyDataError when RERUN_REEVALUATION=False.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if error_df is None or error_df.empty:
        pd.DataFrame(columns=["scenario", "member", "error", "traceback"]).to_csv(path, index=False)
    else:
        error_df.to_csv(path, index=False)

def save_figure(fig, outfile: str | Path, dpi: int | None = None):
    """Save a figure with tight layout and create parent directories as needed."""
    outfile = Path(outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(outfile, dpi=dpi if dpi is not None else PLOT_STYLE.get("savefig.dpi", 300), bbox_inches="tight")
    plt.show()
    print(f"Saved figure: {outfile}")


def sort_for_plot(df: pd.DataFrame, xcol: str = PUMPING_COLUMN_FOR_HYDRO_PLOTS) -> pd.DataFrame:
    """Return a copy sorted by the selected x-column."""
    return df.sort_values(xcol).copy()


def plot_validation_grid_1x2(
    df: pd.DataFrame,
    plot_specs: list[dict],
    outfile: str | Path,
    figure_title: str = "Baseline re-evaluation validation",
):
    """Plot one-to-one validation panels in a clean 1x2 figure."""
    if len(plot_specs) != 2:
        raise ValueError("plot_validation_grid_1x2 expects exactly two panels.")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2))

    for ax, spec in zip(axes, plot_specs):
        xcol = spec["xcol"]
        ycol = spec["ycol"]
        panel_df = df[[xcol, ycol]].dropna().copy()

        if panel_df.empty:
            ax.text(0.5, 0.5, "No data available", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(spec.get("title", "Validation panel"))
            continue

        ax.scatter(panel_df[xcol], panel_df[ycol], alpha=0.75, s=24, color=SCENARIO_COLORS.get("reeval"))
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

    fig.suptitle(figure_title, y=1.04, fontsize=PLOT_STYLE.get("axes.titlesize", 13) + 1)
    save_figure(fig, outfile)


def plot_validation_grid_2x2(
    df: pd.DataFrame,
    plot_specs: list[dict],
    outfile: str | Path,
    figure_title: str = "Baseline re-evaluation validation",
):
    """Plot up to four one-to-one validation panels in a 2x2 figure."""
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

        ax.scatter(panel_df[xcol], panel_df[ycol], alpha=0.75, s=24, color=SCENARIO_COLORS.get("reeval"))
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

    for ax in axes[len(plot_specs):]:
        ax.axis("off")

    fig.suptitle(figure_title, y=1.02, fontsize=PLOT_STYLE.get("axes.titlesize", 13) + 1)
    save_figure(fig, outfile)


def plot_archive_vs_reevaluated_front(
    df: pd.DataFrame,
    outfile: str | Path,
    x_archive: str = "archive_total_pumping_cfs",
    y_archive: str = "archive_streamflow_cfs",
    x_reeval: str = "total_pumping_cfs",
    y_reeval: str = "streamflow_cfs",
    xlabel: str = "Total pumping (cfs)",
    ylabel: str = "Streamflow = 8.6 cfs - depletion (cfs)",
    title: str = "Original archived front vs. re-evaluated front",
):
    """Plot the archived Pareto front and the re-evaluated Pareto front together."""
    required = [x_archive, y_archive, x_reeval, y_reeval]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Cannot plot archive vs re-evaluated front. Missing columns: {missing}")

    fig, ax = plt.subplots(figsize=(8.5, 5.5))

    archive_df = df[[x_archive, y_archive]].dropna().sort_values(x_archive).copy()
    reeval_df = df[[x_reeval, y_reeval]].dropna().sort_values(x_reeval).copy()

    ax.scatter(archive_df[x_archive], archive_df[y_archive], s=28, marker="D", edgecolors="black", alpha=0.70,
               color=SCENARIO_COLORS.get("archive"), label="Original archived front")
    ax.plot(archive_df[x_archive], archive_df[y_archive], alpha=0.85,
            color=SCENARIO_COLORS.get("archive"))

    ax.scatter(reeval_df[x_reeval], reeval_df[y_reeval], s=18, alpha=0.75,
               color=SCENARIO_COLORS.get("reeval"), label="Re-evaluated front")
    ax.plot(reeval_df[x_reeval], reeval_df[y_reeval], alpha=0.75,
            color=SCENARIO_COLORS.get("reeval"))

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    save_figure(fig, outfile)


# =============================================================================
# Notebook 301 helpers: known T-error scenario summaries and plots
# =============================================================================


def make_known_T_scenario_dict(base_T: float) -> dict[str, dict]:
    """Return the standard known-error T scenarios used in Notebook 301."""
    base_T = float(base_T)
    return {
        "T_minus_10pct": {"T_factor": 0.9, "T_value": base_T * 0.9},
        "baseline_T": {"T_factor": 1.0, "T_value": base_T},
        "T_plus_10pct": {"T_factor": 1.1, "T_value": base_T * 1.1},
    }


def add_known_T_error_columns(results_long: pd.DataFrame) -> pd.DataFrame:
    """Add member-level streamflow/depletion differences relative to baseline_T."""
    required = {"member", "scenario", "depletion_cfs", "streamflow_cfs", "pumping_objective_reeval_cfs"}
    missing = required - set(results_long.columns)
    if missing:
        raise KeyError(f"results_long is missing required columns: {sorted(missing)}")

    df = results_long.copy()
    baseline = df.loc[df["scenario"] == "baseline_T", ["member", "depletion_cfs", "streamflow_cfs"]].copy()
    if baseline.empty:
        raise ValueError("No baseline_T rows were found in results_long.")
    baseline = baseline.rename(columns={
        "depletion_cfs": "baseline_T_depletion_cfs",
        "streamflow_cfs": "baseline_T_streamflow_cfs",
    })

    df = df.merge(baseline, on="member", how="left")
    df["depletion_change_from_baseline_cfs"] = df["depletion_cfs"] - df["baseline_T_depletion_cfs"]
    df["streamflow_change_from_baseline_cfs"] = df["streamflow_cfs"] - df["baseline_T_streamflow_cfs"]
    df["absolute_depletion_error_cfs"] = df["depletion_change_from_baseline_cfs"].abs()
    df["absolute_streamflow_error_cfs"] = df["streamflow_change_from_baseline_cfs"].abs()

    # Streamflow shortfall is one-sided: it only counts cases where the scenario
    # streamflow is lower than the baseline-T streamflow prediction.
    df["streamflow_shortfall_below_baseline_cfs"] = np.maximum(
        df["baseline_T_streamflow_cfs"] - df["streamflow_cfs"],
        0.0,
    )
    return df


def make_known_T_wide(results_long: pd.DataFrame) -> pd.DataFrame:
    """Create a member-level wide table for the known T-error scenario results."""
    df = add_known_T_error_columns(results_long)
    id_cols = ["member"]
    value_cols = [
        "T_factor",
        "T_value",
        "pumping_objective_reeval_cfs",
        "full_model_total_pumping_cfs",
        "depletion_cfs",
        "streamflow_cfs",
        "depletion_change_from_baseline_cfs",
        "streamflow_change_from_baseline_cfs",
        "absolute_depletion_error_cfs",
        "absolute_streamflow_error_cfs",
        "streamflow_shortfall_below_baseline_cfs",
    ]
    available = [c for c in value_cols if c in df.columns]
    wide = df.pivot_table(index=id_cols, columns="scenario", values=available, aggfunc="first")
    wide.columns = [f"{metric}__{scenario}" for metric, scenario in wide.columns]
    wide = wide.reset_index()

    # Add a simple plotting x column from the baseline scenario; pumping is held
    # fixed across T scenarios, so this is the correct x-axis for all panels.
    base_col = "pumping_objective_reeval_cfs__baseline_T"
    if base_col in wide.columns:
        wide[PUMPING_COLUMN_FOR_HYDRO_PLOTS] = wide[base_col]
    return wide


def summarize_known_T_scenarios(results_long: pd.DataFrame) -> pd.DataFrame:
    """Summarize fixed-design known T-error results by scenario."""
    df = add_known_T_error_columns(results_long)
    rows = []
    scenario_order = ["T_minus_10pct", "baseline_T", "T_plus_10pct"]
    for scenario in scenario_order:
        g = df.loc[df["scenario"] == scenario].copy()
        if g.empty:
            continue
        rows.append({
            "scenario": scenario,
            "T_factor": float(g["T_factor"].iloc[0]),
            "T_value": float(g["T_value"].iloc[0]),
            "n_members": int(len(g)),
            "mean_pumping_objective_cfs": float(g["pumping_objective_reeval_cfs"].mean()),
            "min_pumping_objective_cfs": float(g["pumping_objective_reeval_cfs"].min()),
            "max_pumping_objective_cfs": float(g["pumping_objective_reeval_cfs"].max()),
            "mean_depletion_cfs": float(g["depletion_cfs"].mean()),
            "min_depletion_cfs": float(g["depletion_cfs"].min()),
            "max_depletion_cfs": float(g["depletion_cfs"].max()),
            "mean_streamflow_cfs": float(g["streamflow_cfs"].mean()),
            "min_streamflow_cfs": float(g["streamflow_cfs"].min()),
            "max_streamflow_cfs": float(g["streamflow_cfs"].max()),
            "mean_depletion_change_from_baseline_cfs": float(g["depletion_change_from_baseline_cfs"].mean()),
            "mean_streamflow_change_from_baseline_cfs": float(g["streamflow_change_from_baseline_cfs"].mean()),
            "mean_absolute_depletion_error_cfs": float(g["absolute_depletion_error_cfs"].mean()),
            "max_absolute_depletion_error_cfs": float(g["absolute_depletion_error_cfs"].max()),
            "mean_absolute_streamflow_error_cfs": float(g["absolute_streamflow_error_cfs"].mean()),
            "max_absolute_streamflow_error_cfs": float(g["absolute_streamflow_error_cfs"].max()),
            "mean_streamflow_shortfall_below_baseline_cfs": float(g["streamflow_shortfall_below_baseline_cfs"].mean()),
            "max_streamflow_shortfall_below_baseline_cfs": float(g["streamflow_shortfall_below_baseline_cfs"].max()),
        })
    return pd.DataFrame(rows)


def plot_depletion_q_known_T_fronts(results_long: pd.DataFrame, outfile: str | Path, y_metric: str = "streamflow"):
    """Plot pumping-objective vs streamflow or depletion for known T scenarios."""
    if y_metric not in {"streamflow", "depletion"}:
        raise ValueError("y_metric must be either 'streamflow' or 'depletion'.")
    ycol = "streamflow_cfs" if y_metric == "streamflow" else "depletion_cfs"
    ylabel = "Streamflow = 8.6 cfs - depletion (cfs)" if y_metric == "streamflow" else "Depletion (cfs)"
    title_metric = "streamflow" if y_metric == "streamflow" else "depletion"

    df = sort_for_plot(results_long, xcol=PUMPING_COLUMN_FOR_HYDRO_PLOTS)
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    for scenario, label, color in [
        ("T_minus_10pct", "T -10%", "#2E7D32"),
        ("baseline_T", "Baseline T", "#1F77B4"),
        ("T_plus_10pct", "T +10%", "#C62828"),
    ]:
        g = df.loc[df["scenario"] == scenario].copy()
        if g.empty:
            continue
        ax.plot(
            g[PUMPING_COLUMN_FOR_HYDRO_PLOTS],
            g[ycol],
            marker="o",
            markersize=3,
            linewidth=1.5,
            color=color,
            label=label,
            alpha=0.9,
        )
    ax.set_xlabel("Pumping objective: decision-variable pumping (cfs)")
    ax.set_ylabel(ylabel)
    ax.set_title(f"Fixed depletion_q Pareto designs under known T error: {title_metric}")
    ax.legend(loc="best")
    save_figure(fig, outfile)


def plot_depletion_q_known_T_error_2x2(wide: pd.DataFrame, outfile: str | Path):
    """Create a 2x2 report figure for Notebook 301 known T-error results."""
    plot_df = sort_for_plot(wide, xcol=PUMPING_COLUMN_FOR_HYDRO_PLOTS)
    x = plot_df[PUMPING_COLUMN_FOR_HYDRO_PLOTS]

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.0))
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    scenarios = [
        ("T_minus_10pct", "T -10%", "#2E7D32"),
        ("baseline_T", "Baseline T", "#1F77B4"),
        ("T_plus_10pct", "T +10%", "#C62828"),
    ]

    for scenario, label, color in scenarios:
        stream_col = f"streamflow_cfs__{scenario}"
        dep_col = f"depletion_cfs__{scenario}"
        if stream_col in plot_df.columns:
            ax_a.plot(x, plot_df[stream_col], marker="o", markersize=3, linewidth=1.4, color=color, label=label)
        if dep_col in plot_df.columns:
            ax_b.plot(x, plot_df[dep_col], marker="o", markersize=3, linewidth=1.4, color=color, label=label)

    for scenario, label, color in [
        ("T_minus_10pct", "T -10%", "#2E7D32"),
        ("T_plus_10pct", "T +10%", "#C62828"),
    ]:
        change_col = f"streamflow_change_from_baseline_cfs__{scenario}"
        abs_col = f"absolute_streamflow_error_cfs__{scenario}"
        if change_col in plot_df.columns:
            ax_c.plot(x, plot_df[change_col], marker="o", markersize=3, linewidth=1.4, color=color, label=label)
        if abs_col in plot_df.columns:
            ax_d.plot(x, plot_df[abs_col], marker="o", markersize=3, linewidth=1.4, color=color, label=label)

    ax_c.axhline(0, color="0.35", linestyle="--", linewidth=1.0)

    ax_a.set_title("A. Streamflow response")
    ax_a.set_xlabel("Pumping objective (cfs)")
    ax_a.set_ylabel("Streamflow (cfs)")
    ax_a.legend(loc="best")

    ax_b.set_title("B. Depletion response")
    ax_b.set_xlabel("Pumping objective (cfs)")
    ax_b.set_ylabel("Depletion (cfs)")
    ax_b.legend(loc="best")

    ax_c.set_title("C. Signed streamflow change from baseline T")
    ax_c.set_xlabel("Pumping objective (cfs)")
    ax_c.set_ylabel("Streamflow change (cfs)")
    ax_c.legend(loc="best")

    ax_d.set_title("D. Absolute streamflow error")
    ax_d.set_xlabel("Pumping objective (cfs)")
    ax_d.set_ylabel("Absolute streamflow error (cfs)")
    ax_d.legend(loc="best")

    fig.suptitle("Fixed depletion_q designs under known ±10% transmissivity error", y=1.02)
    save_figure(fig, outfile)


# =============================================================================
# Probability-weighted parameter uncertainty helpers for Notebook 302
# =============================================================================

def _normal_pdf(x, mean: float = 0.0, sigma: float = 1.0):
    """Return the normal probability density evaluated at x."""
    x = np.asarray(x, dtype=float)
    return (1.0 / (sigma * np.sqrt(2.0 * np.pi))) * np.exp(-0.5 * ((x - mean) / sigma) ** 2)


def make_normal_parameter_probability_table(
    parameter_name: str,
    base_value: float,
    sigma_fraction: float = 0.10,
    n_sigma_each_side: float = 2.0,
    n_values: int = 11,
) -> pd.DataFrame:
    """
    Build a discrete normal probability table for a multiplicative parameter factor.

    For transmissivity with sigma_fraction=0.10 and n_sigma_each_side=2.0,
    this creates factors from 0.8 to 1.2 centered on 1.0.
    """
    if n_values < 3:
        raise ValueError("n_values must be at least 3.")
    if sigma_fraction <= 0:
        raise ValueError("sigma_fraction must be positive.")
    if n_sigma_each_side <= 0:
        raise ValueError("n_sigma_each_side must be positive.")

    z_scores = np.linspace(-float(n_sigma_each_side), float(n_sigma_each_side), int(n_values))
    parameter_factors = 1.0 + z_scores * float(sigma_fraction)
    raw_weights = _normal_pdf(z_scores, mean=0.0, sigma=1.0)
    probability_weights = raw_weights / raw_weights.sum()

    rows = []
    for z, factor, weight in zip(z_scores, parameter_factors, probability_weights):
        if abs(z) < 1.0e-12:
            scenario = "baseline_T"
        elif z < 0:
            scenario = f"T_zminus_{abs(z):.2f}".replace(".", "p")
        else:
            scenario = f"T_zplus_{z:.2f}".replace(".", "p")
        rows.append({
            "parameter_name": parameter_name,
            "scenario": scenario,
            "z_score": float(z),
            "parameter_factor": float(factor),
            "parameter_value": float(base_value) * float(factor),
            "probability_weight": float(weight),
        })
    return pd.DataFrame(rows)


def probability_table_to_T_scenarios(probability_table: pd.DataFrame) -> dict[str, dict]:
    """Convert a probability table into the scenario dictionary expected by reevaluate_depletion_q_designs()."""
    required = {"scenario", "parameter_factor", "parameter_value", "probability_weight"}
    missing = required - set(probability_table.columns)
    if missing:
        raise KeyError(f"probability_table is missing required columns: {sorted(missing)}")
    scenarios = {}
    for _, row in probability_table.iterrows():
        scenarios[str(row["scenario"])] = {
            "T_factor": float(row["parameter_factor"]),
            "T_value": float(row["parameter_value"]),
            "probability_weight": float(row["probability_weight"]),
        }
    return scenarios


def weighted_quantile(values, weights, quantiles):
    """Compute weighted quantiles for 1D values and weights."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    quantiles = np.asarray(quantiles, dtype=float)
    valid = np.isfinite(values) & np.isfinite(weights) & (weights >= 0)
    values = values[valid]
    weights = weights[valid]
    if values.size == 0 or weights.sum() <= 0:
        return np.full_like(quantiles, np.nan, dtype=float)
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    weights = weights / weights.sum()
    cdf = np.cumsum(weights)
    return np.interp(quantiles, cdf, values)


def add_probability_table_metadata(results_long: pd.DataFrame, probability_table: pd.DataFrame) -> pd.DataFrame:
    """
    Attach probability-table metadata to long re-evaluation results.

    This function intentionally removes any pre-existing probability metadata
    columns before merging. Without this, pandas can create columns like
    parameter_factor_x and parameter_factor_y, which later breaks the
    probability-weighted summary functions.
    """
    possible_meta_cols = [
        "z_score",
        "parameter_factor",
        "parameter_value",
        "base_parameter_value",
        "probability_weight",
        "parameter_name",
        "parameter_label",
        "parameter_symbol",
    ]

    meta_cols = ["scenario"] + [c for c in possible_meta_cols if c in probability_table.columns]
    meta = probability_table[meta_cols].copy()

    drop_cols = [c for c in possible_meta_cols if c in results_long.columns]
    df = results_long.drop(columns=drop_cols, errors="ignore").copy()

    merged = df.merge(meta, on="scenario", how="left")

    if "parameter_factor" not in merged.columns:
        raise KeyError("parameter_factor was not created during metadata merge. Check probability_table columns.")
    if "probability_weight" not in merged.columns:
        raise KeyError("probability_weight was not created during metadata merge. Check probability_table columns.")

    return merged


def summarize_probability_weighted_depletion_q(results_long: pd.DataFrame) -> pd.DataFrame:
    """
    Create member-level probability-weighted uncertainty metrics.

    Baseline is the row with parameter_factor closest to 1.0 for each member.
    """
    required = {"member", "parameter_factor", "probability_weight", "pumping_objective_reeval_cfs", "depletion_cfs", "streamflow_cfs"}
    missing = required - set(results_long.columns)
    if missing:
        raise KeyError(f"results_long is missing required columns: {sorted(missing)}")

    rows = []
    for member, g in results_long.groupby("member", sort=False):
        g = g.copy()
        weights = pd.to_numeric(g["probability_weight"], errors="coerce").to_numpy(dtype=float)
        if np.nansum(weights) <= 0:
            weights = np.ones(len(g), dtype=float) / max(len(g), 1)
        else:
            weights = weights / np.nansum(weights)

        stream = pd.to_numeric(g["streamflow_cfs"], errors="coerce").to_numpy(dtype=float)
        dep = pd.to_numeric(g["depletion_cfs"], errors="coerce").to_numpy(dtype=float)
        factors = pd.to_numeric(g["parameter_factor"], errors="coerce").to_numpy(dtype=float)
        baseline_idx = int(np.nanargmin(np.abs(factors - 1.0)))

        baseline_stream = float(stream[baseline_idx])
        baseline_dep = float(dep[baseline_idx])
        expected_stream = float(np.nansum(weights * stream))
        expected_dep = float(np.nansum(weights * dep))
        stream_p05, stream_p50, stream_p95 = weighted_quantile(stream, weights, [0.05, 0.50, 0.95])
        dep_p05, dep_p50, dep_p95 = weighted_quantile(dep, weights, [0.05, 0.50, 0.95])

        rows.append({
            "member": member,
            PUMPING_COLUMN_FOR_HYDRO_PLOTS: float(g[PUMPING_COLUMN_FOR_HYDRO_PLOTS].iloc[0]),
            "baseline_streamflow_cfs": baseline_stream,
            "baseline_depletion_cfs": baseline_dep,
            "expected_streamflow_cfs": expected_stream,
            "expected_depletion_cfs": expected_dep,
            "expected_streamflow_bias_from_baseline_cfs": expected_stream - baseline_stream,
            "expected_depletion_bias_from_baseline_cfs": expected_dep - baseline_dep,
            "probability_weighted_absolute_streamflow_error_cfs": float(np.nansum(weights * np.abs(stream - baseline_stream))),
            "probability_weighted_absolute_depletion_error_cfs": float(np.nansum(weights * np.abs(dep - baseline_dep))),
            "probability_weighted_streamflow_shortfall_cfs": float(np.nansum(weights * np.maximum(baseline_stream - stream, 0.0))),
            "probability_weighted_depletion_excess_cfs": float(np.nansum(weights * np.maximum(dep - baseline_dep, 0.0))),
            "streamflow_std_cfs": float(np.sqrt(np.nansum(weights * (stream - expected_stream) ** 2))),
            "depletion_std_cfs": float(np.sqrt(np.nansum(weights * (dep - expected_dep) ** 2))),
            "streamflow_p05_cfs": float(stream_p05),
            "streamflow_p50_cfs": float(stream_p50),
            "streamflow_p95_cfs": float(stream_p95),
            "depletion_p05_cfs": float(dep_p05),
            "depletion_p50_cfs": float(dep_p50),
            "depletion_p95_cfs": float(dep_p95),
        })
    return pd.DataFrame(rows)


def summarize_probability_weighted_overall(member_summary: pd.DataFrame) -> pd.DataFrame:
    """Summarize member-level probability-weighted metrics into a compact overall table."""
    metrics = [
        ("n_members", len(member_summary)),
        ("mean_probability_weighted_absolute_streamflow_error_cfs", member_summary["probability_weighted_absolute_streamflow_error_cfs"].mean()),
        ("max_probability_weighted_absolute_streamflow_error_cfs", member_summary["probability_weighted_absolute_streamflow_error_cfs"].max()),
        ("mean_probability_weighted_streamflow_shortfall_cfs", member_summary["probability_weighted_streamflow_shortfall_cfs"].mean()),
        ("max_probability_weighted_streamflow_shortfall_cfs", member_summary["probability_weighted_streamflow_shortfall_cfs"].max()),
        ("mean_streamflow_std_cfs", member_summary["streamflow_std_cfs"].mean()),
        ("max_streamflow_std_cfs", member_summary["streamflow_std_cfs"].max()),
        ("mean_expected_streamflow_bias_from_baseline_cfs", member_summary["expected_streamflow_bias_from_baseline_cfs"].mean()),
        ("mean_probability_weighted_absolute_depletion_error_cfs", member_summary["probability_weighted_absolute_depletion_error_cfs"].mean()),
        ("mean_probability_weighted_depletion_excess_cfs", member_summary["probability_weighted_depletion_excess_cfs"].mean()),
        ("mean_depletion_std_cfs", member_summary["depletion_std_cfs"].mean()),
    ]
    return pd.DataFrame([{"metric": m, "value": v} for m, v in metrics])


def plot_parameter_probability_weights_with_curve(probability_table: pd.DataFrame, sigma_fraction: float, outfile: str | Path, title: str):
    """Plot discrete probability weights with a continuous normal bell-curve overlay."""
    df = probability_table.sort_values("parameter_factor").copy()
    factors = df["parameter_factor"].to_numpy(dtype=float)
    weights = df["probability_weight"].to_numpy(dtype=float)
    dx = float(np.median(np.diff(factors))) if len(factors) > 1 else sigma_fraction / 2.5
    x = np.linspace(min(factors.min(), 1 - 3 * sigma_fraction), max(factors.max(), 1 + 3 * sigma_fraction), 700)
    pdf_mass = _normal_pdf((x - 1.0) / sigma_fraction, 0, 1) * (dx / sigma_fraction)

    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.bar(factors, weights, width=dx * 0.72, color="#A7C7E7", edgecolor="0.35", linewidth=0.9, alpha=0.88, label="Discrete probability weights")
    ax.plot(x, pdf_mass, color=SCENARIO_COLORS.get("expected", "#6A4C93"), linewidth=2.4, label="Normal bell curve, scaled to weights")
    ax.axvline(1.0, color="0.25", linestyle="--", linewidth=1.2, label="Baseline value")
    ax.set_xlabel("Parameter factor relative to baseline")
    ax.set_ylabel("Probability weight")
    ax.set_title(title)
    ax.legend(loc="best")
    save_figure(fig, outfile)


def plot_parameter_probability_shaded_sigma_regions(sigma_fraction: float, n_sigma_each_side: float, outfile: str | Path, title: str):
    """Plot a normal distribution in parameter-factor space with shaded sigma regions."""
    sigma = float(sigma_fraction)
    max_sigma = max(float(n_sigma_each_side), 3.0)
    x = np.linspace(1 - max_sigma * sigma, 1 + max_sigma * sigma, 1200)
    y = _normal_pdf(x, 1.0, sigma)
    ymax = float(y.max())
    fig, ax = plt.subplots(figsize=(9.5, 5.7))
    intervals = [(-3, -2, "#DCECF7", "2.1%"), (-2, -1, "#BFDDF2", "13.6%"), (-1, 0, "#8CC7E8", "34.1%"), (0, 1, "#8CC7E8", "34.1%"), (1, 2, "#BFDDF2", "13.6%"), (2, 3, "#DCECF7", "2.1%")]
    for left_z, right_z, color, label in intervals:
        left = 1 + left_z * sigma
        right = 1 + right_z * sigma
        mask = (x >= left) & (x <= right)
        ax.fill_between(x[mask], y[mask], color=color, alpha=0.95)
        mid = (left + right) / 2
        ax.text(mid, _normal_pdf(mid, 1.0, sigma) * 0.18, label, ha="center", va="center", fontsize=9)
    ax.plot(x, y, color=SCENARIO_COLORS.get("expected", "#6A4C93"), linewidth=2.5)
    z_ticks = [-3, -2, -1, 0, 1, 2, 3]
    tick_positions = [1 + z * sigma for z in z_ticks]
    tick_labels = [f"{z:+d}σ\n{pos:.2f}" if z != 0 else f"μ\n{1.0:.2f}" for z, pos in zip(z_ticks, tick_positions)]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    for z, pos in zip(z_ticks, tick_positions):
        ax.axvline(pos, color="0.45", linestyle=":" if z != 0 else "--", linewidth=1.1, alpha=0.85 if abs(z) <= n_sigma_each_side else 0.35)

    def bracket(x0, x1, y_level, label):
        end_h = ymax * 0.045
        ax.plot([x0, x1], [y_level, y_level], color="0.4", lw=1.1)
        ax.plot([x0, x0], [y_level, y_level - end_h], color="0.4", lw=1.1)
        ax.plot([x1, x1], [y_level, y_level - end_h], color="0.4", lw=1.1)
        ax.text((x0 + x1) / 2, y_level + ymax * 0.012, label, ha="center", va="bottom", fontsize=10)

    bracket(1 - sigma, 1 + sigma, ymax * 1.04, "~68.2% within ±1σ")
    bracket(1 - 2 * sigma, 1 + 2 * sigma, ymax * 1.22, "~95.4% within ±2σ")
    ax.set_ylim(0, ymax * 1.38)
    ax.set_xlabel("Parameter factor relative to baseline")
    ax.set_ylabel("Probability density")
    ax.set_title(title)
    ax.text(0.02, 0.96, f"Mean factor = 1.0\n1σ = ±{sigma_fraction:.0%}\nSampled range = ±{n_sigma_each_side:g}σ", transform=ax.transAxes, ha="left", va="top", bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="0.75", alpha=0.9), fontsize=9)
    save_figure(fig, outfile)


def plot_probability_weighted_streamflow_dashboard_depletion_q(member_summary: pd.DataFrame, outfile: str | Path, title: str):
    """Create a 3-row dashboard of expected streamflow and uncertainty/cost metrics."""
    required = {PUMPING_COLUMN_FOR_HYDRO_PLOTS, "baseline_streamflow_cfs", "expected_streamflow_cfs", "streamflow_p05_cfs", "streamflow_p95_cfs", "probability_weighted_absolute_streamflow_error_cfs", "probability_weighted_streamflow_shortfall_cfs", "streamflow_std_cfs"}
    missing = required - set(member_summary.columns)
    if missing:
        raise KeyError(f"member_summary is missing required columns: {sorted(missing)}")
    plot_df = sort_for_plot(member_summary, xcol=PUMPING_COLUMN_FOR_HYDRO_PLOTS)
    x = plot_df[PUMPING_COLUMN_FOR_HYDRO_PLOTS]
    fig = plt.figure(figsize=(14.0, 9.2))
    gs = fig.add_gridspec(3, 2, width_ratios=[1.65, 1.0], height_ratios=[1, 1, 1], wspace=0.30, hspace=0.42)
    ax_left = fig.add_subplot(gs[:, 0])
    ax_top = fig.add_subplot(gs[0, 1])
    ax_mid = fig.add_subplot(gs[1, 1], sharex=ax_top)
    ax_bot = fig.add_subplot(gs[2, 1], sharex=ax_top)

    ax_left.plot(x, plot_df["baseline_streamflow_cfs"], linestyle="--", color=SCENARIO_COLORS.get("baseline_T"), label="Baseline-parameter prediction")
    ax_left.plot(x, plot_df["expected_streamflow_cfs"], color=SCENARIO_COLORS.get("expected"), label="Probability-weighted expected streamflow")
    ax_left.fill_between(x, plot_df["streamflow_p05_cfs"], plot_df["streamflow_p95_cfs"], color=SCENARIO_COLORS.get("uncertainty_band", "0.7"), alpha=0.25, label="Weighted 5th–95th percentile range")
    ax_left.set_xlabel("Pumping objective (cfs)")
    ax_left.set_ylabel("Streamflow = 8.6 cfs - depletion (cfs)")
    ax_left.set_title("A. Expected streamflow with uncertainty band")
    ax_left.legend(loc="best")

    ax_top.plot(x, plot_df["probability_weighted_absolute_streamflow_error_cfs"], marker="o", markersize=3, color=SCENARIO_COLORS.get("expected"))
    ax_top.set_ylabel("Abs. error (cfs)")
    ax_top.set_title("B. Probability-weighted absolute streamflow error")
    ax_top.tick_params(labelbottom=False)

    ax_mid.plot(x, plot_df["probability_weighted_streamflow_shortfall_cfs"], marker="o", markersize=3, color=SCENARIO_COLORS.get("T_plus_10pct"))
    ax_mid.set_ylabel("Shortfall (cfs)")
    ax_mid.set_title("C. Probability-weighted streamflow shortfall")
    ax_mid.tick_params(labelbottom=False)

    ax_bot.plot(x, plot_df["streamflow_std_cfs"], marker="o", markersize=3, color="0.35")
    ax_bot.set_xlabel("Pumping objective (cfs)")
    ax_bot.set_ylabel("Std. dev. (cfs)")
    ax_bot.set_title("D. Streamflow standard deviation")

    fig.suptitle(title, y=1.02, fontsize=PLOT_STYLE.get("axes.titlesize", 13) + 1)
    save_figure(fig, outfile)


def plot_probability_weighted_metric(member_summary: pd.DataFrame, ycol: str, outfile: str | Path, title: str, ylabel: str):
    """Simple metric-vs-pumping plot for probability-weighted results."""
    plot_df = sort_for_plot(member_summary, xcol=PUMPING_COLUMN_FOR_HYDRO_PLOTS)
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    ax.plot(plot_df[PUMPING_COLUMN_FOR_HYDRO_PLOTS], plot_df[ycol], marker="o", markersize=3, linewidth=1.7, color=SCENARIO_COLORS.get("expected"))
    ax.set_xlabel("Pumping objective (cfs)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    save_figure(fig, outfile)



# =============================================================================
# Generic project-property parameter perturbation helpers
# =============================================================================

PARAMETER_CONFIG = {
    "transmissivity": {
        "project_key": "T",
        "symbol": "T",
        "label": "Transmissivity",
        "scenario_tag": "transmissivity",
        "short_tag": "T",
    },
    "storage": {
        "project_key": "S",
        "symbol": "S",
        "label": "Storage",
        "scenario_tag": "storage",
        "short_tag": "S",
    },
}


def normalize_parameter_name(parameter_name: str) -> str:
    """Normalize common parameter aliases used in notebooks."""
    key = str(parameter_name).strip().lower().replace(" ", "_")
    aliases = {
        "t": "transmissivity",
        "transmissivity": "transmissivity",
        "s": "storage",
        "storage": "storage",
        "storativity": "storage",
    }
    if key not in aliases:
        raise KeyError(
            f"Unsupported parameter {parameter_name!r}. Supported options are: "
            f"{sorted(set(aliases.values()))}."
        )
    return aliases[key]


def get_parameter_config(parameter_name: str) -> dict:
    """Return the configuration dictionary for a supported project parameter."""
    normalized = normalize_parameter_name(parameter_name)
    return PARAMETER_CONFIG[normalized].copy()


def get_project_parameter_value(initial_dict: dict, parameter_name: str) -> float:
    """Read a scalar project_properties value, currently T or S."""
    cfg = get_parameter_config(parameter_name)
    project_key = cfg["project_key"]
    if "project_properties" not in initial_dict:
        raise KeyError("initial_dict does not contain 'project_properties'.")
    if project_key not in initial_dict["project_properties"]:
        raise KeyError(f"initial_dict['project_properties'] does not contain {project_key!r}.")
    return float(initial_dict["project_properties"][project_key])


def make_initial_dict_with_project_parameter(
    initial_dict_master: dict,
    parameter_name: str,
    parameter_factor: float | None = None,
    parameter_value: float | None = None,
) -> dict:
    """
    Return a deep-copied PyCap project dictionary with one project_properties
    parameter changed. Currently supports transmissivity (T) and storage (S).
    """
    cfg = get_parameter_config(parameter_name)
    project_key = cfg["project_key"]

    initial_dict = copy.deepcopy(initial_dict_master)
    base_value = get_project_parameter_value(initial_dict_master, parameter_name)

    if parameter_value is not None:
        new_value = float(parameter_value)
    else:
        factor = 1.0 if parameter_factor is None else float(parameter_factor)
        new_value = base_value * factor

    initial_dict["project_properties"][project_key] = new_value
    return initial_dict


def make_initial_dict_with_T(
    initial_dict_master: dict,
    t_factor: float | None = None,
    t_value: float | None = None,
) -> dict:
    """Backward-compatible wrapper for older notebooks that only perturb T."""
    return make_initial_dict_with_project_parameter(
        initial_dict_master,
        parameter_name="transmissivity",
        parameter_factor=t_factor,
        parameter_value=t_value,
    )


def make_known_parameter_scenario_dict(
    parameter_name: str,
    base_value: float,
    factors: list[float] | tuple[float, ...] = (0.9, 1.0, 1.1),
) -> dict[str, dict]:
    """
    Return the standard known-error scenarios for a scalar project parameter.

    Scenario labels are parameter-specific, for example:
        storage_minus_10pct
        baseline_storage
        storage_plus_10pct
    """
    cfg = get_parameter_config(parameter_name)
    tag = cfg["scenario_tag"]
    label = cfg["label"]
    base_value = float(base_value)

    if len(factors) != 3:
        raise ValueError("This helper expects exactly three factors: lower, baseline, upper.")

    lower, baseline, upper = [float(v) for v in factors]
    return {
        f"{tag}_minus_10pct": {
            "parameter_name": normalize_parameter_name(parameter_name),
            "parameter_label": label,
            "parameter_factor": lower,
            "parameter_value": base_value * lower,
        },
        f"baseline_{tag}": {
            "parameter_name": normalize_parameter_name(parameter_name),
            "parameter_label": label,
            "parameter_factor": baseline,
            "parameter_value": base_value * baseline,
        },
        f"{tag}_plus_10pct": {
            "parameter_name": normalize_parameter_name(parameter_name),
            "parameter_label": label,
            "parameter_factor": upper,
            "parameter_value": base_value * upper,
        },
    }


def make_known_T_scenario_dict(base_T: float) -> dict[str, dict]:
    """
    Backward-compatible known-T scenarios. This preserves the older T-specific
    scenario labels expected by some earlier notebooks.
    """
    base_T = float(base_T)
    return {
        "T_minus_10pct": {"T_factor": 0.9, "T_value": base_T * 0.9},
        "baseline_T": {"T_factor": 1.0, "T_value": base_T},
        "T_plus_10pct": {"T_factor": 1.1, "T_value": base_T * 1.1},
    }


def _scenario_parameter_info(scenario_info, context: DepletionQContext) -> dict:
    """Standardize old T-only and new generic parameter scenario dictionaries."""
    if isinstance(scenario_info, dict):
        if "parameter_name" in scenario_info:
            parameter_name = normalize_parameter_name(scenario_info["parameter_name"])
            parameter_value = scenario_info.get("parameter_value", None)
            parameter_factor = scenario_info.get("parameter_factor", None)
            base_value = get_project_parameter_value(context.initial_dict_master, parameter_name)
            if parameter_value is None:
                parameter_factor = 1.0 if parameter_factor is None else float(parameter_factor)
                parameter_value = base_value * parameter_factor
            else:
                parameter_value = float(parameter_value)
                parameter_factor = parameter_value / base_value
            probability_weight = scenario_info.get("probability_weight", np.nan)
        else:
            parameter_name = "transmissivity"
            base_value = get_project_parameter_value(context.initial_dict_master, parameter_name)
            parameter_value = scenario_info.get("T_value", None)
            parameter_factor = scenario_info.get("T_factor", None)
            if parameter_value is None:
                parameter_factor = 1.0 if parameter_factor is None else float(parameter_factor)
                parameter_value = base_value * parameter_factor
            else:
                parameter_value = float(parameter_value)
                parameter_factor = parameter_value / base_value
            probability_weight = scenario_info.get("probability_weight", np.nan)
    else:
        parameter_name = "transmissivity"
        base_value = get_project_parameter_value(context.initial_dict_master, parameter_name)
        parameter_factor = float(scenario_info)
        parameter_value = base_value * parameter_factor
        probability_weight = np.nan

    cfg = get_parameter_config(parameter_name)
    return {
        "parameter_name": parameter_name,
        "parameter_label": cfg["label"],
        "parameter_symbol": cfg["symbol"],
        "parameter_factor": float(parameter_factor),
        "parameter_value": float(parameter_value),
        "base_parameter_value": float(base_value),
        "probability_weight": probability_weight,
    }


def run_original_depletion_q_get_results(
    q_row: pd.Series,
    context: DepletionQContext,
    t_factor: float | None = 1.0,
    t_value: float | None = None,
    parameter_name: str = "transmissivity",
    parameter_factor: float | None = None,
    parameter_value: float | None = None,
) -> pd.Series:
    """
    Call the original depletion_q get_results() function for one pumping design.

    This updated version supports either the old T-only arguments or a generic
    project parameter name/factor/value.
    """
    q_row = q_row.copy()
    q_row.index = [str(i).lower() for i in q_row.index]

    if parameter_name in [None, "transmissivity"] and parameter_factor is None and parameter_value is None:
        parameter_factor = t_factor
        parameter_value = t_value

    initial_dict = make_initial_dict_with_project_parameter(
        context.initial_dict_master,
        parameter_name=parameter_name,
        parameter_factor=parameter_factor,
        parameter_value=parameter_value,
    )

    result = context.module.get_results(
        q_row,
        context.obsnames,
        initial_dict,
        context.bdplobs,
        write_csv=False,
    )
    return result


def reevaluate_depletion_q_designs(
    pareto_final: pd.DataFrame,
    dv_df: pd.DataFrame,
    q_cols: list[str],
    context: DepletionQContext,
    scenarios: dict[str, float | dict],
    historic_streamflow_cfs: float = HISTORIC_STREAMFLOW_CFS,
    depletion_obs_name: str = DEPLETION_OBS_NAME,
    progress_every: int = 50,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Re-evaluate a set of depletion_q Pareto designs under one or more parameter
    scenarios. Supports transmissivity and storage.
    """
    records = []
    errors = []
    scenario_items = list(scenarios.items())
    n_total = len(pareto_final) * len(scenario_items)
    counter = 0

    model_q_cols = match_columns_case_insensitive(dv_df, q_cols)
    if not model_q_cols:
        raise KeyError("No model pumping columns were found in dv_df.")

    objective_q_cols = match_columns_case_insensitive(dv_df, context.decvar_q_cols)
    if not objective_q_cols:
        raise KeyError("No decision-variable pumping columns were found in dv_df.")

    for scenario_label, scenario_info in scenario_items:
        pinfo = _scenario_parameter_info(scenario_info, context)
        parameter_name = pinfo["parameter_name"]
        parameter_label = pinfo["parameter_label"]
        parameter_symbol = pinfo["parameter_symbol"]
        parameter_factor = pinfo["parameter_factor"]
        parameter_value = pinfo["parameter_value"]
        base_parameter_value = pinfo["base_parameter_value"]
        prob_weight = pinfo["probability_weight"]

        print(f"Scenario: {scenario_label} | {parameter_symbol} factor: {parameter_factor:.6g} | {parameter_symbol} value: {parameter_value:.6g}")

        for _, row in pareto_final.reset_index(drop=True).iterrows():
            counter += 1
            member = str(row["member"])
            if counter == 1 or counter % progress_every == 0 or counter == n_total:
                print(f"  Re-evaluating {counter} of {n_total}: scenario={scenario_label}, member={member}")

            try:
                if member not in dv_df.index:
                    raise KeyError(f"Member {member!r} was not found in the decision-variable population.")

                q_row = dv_df.loc[member, model_q_cols].copy()

                reeval = run_original_depletion_q_get_results(
                    q_row=q_row,
                    context=context,
                    parameter_name=parameter_name,
                    parameter_factor=parameter_factor,
                    parameter_value=parameter_value,
                )

                pumping_objective_gpm = dv_df.loc[member, objective_q_cols].astype(float).sum()
                pumping_objective_cfs = pumping_objective_gpm * GPM2CFS

                full_model_total_pumping_gpm = q_row.astype(float).sum()
                full_model_total_pumping_cfs = full_model_total_pumping_gpm * GPM2CFS

                archive_pumping_objective_gpm = row.get("obj_well", np.nan)
                archive_pumping_objective_cfs = archive_pumping_objective_gpm * GPM2CFS if pd.notna(archive_pumping_objective_gpm) else np.nan

                depletion_cfs = float(reeval.loc[depletion_obs_name])
                streamflow_cfs = historic_streamflow_cfs - depletion_cfs

                records.append({
                    "member": member,
                    "generation": row.get("generation", np.nan),
                    "scenario": scenario_label,
                    "parameter_name": parameter_name,
                    "parameter_label": parameter_label,
                    "parameter_symbol": parameter_symbol,
                    "parameter_factor": parameter_factor,
                    "parameter_value": parameter_value,
                    "base_parameter_value": base_parameter_value,
                    "probability_weight": prob_weight,
                    "T_factor": parameter_factor if parameter_name == "transmissivity" else np.nan,
                    "T_value": parameter_value if parameter_name == "transmissivity" else np.nan,
                    "S_factor": parameter_factor if parameter_name == "storage" else np.nan,
                    "S_value": parameter_value if parameter_name == "storage" else np.nan,
                    "archive_pumping_objective_cfs": archive_pumping_objective_cfs,
                    "pumping_objective_reeval_cfs": pumping_objective_cfs,
                    "full_model_total_pumping_cfs": full_model_total_pumping_cfs,
                    "archive_depletion_cfs": row.get(depletion_obs_name, np.nan),
                    "depletion_cfs": depletion_cfs,
                    "streamflow_cfs": streamflow_cfs,
                })

            except Exception as err:
                errors.append({
                    "member": member,
                    "scenario": scenario_label,
                    "parameter_name": parameter_name,
                    "parameter_factor": parameter_factor,
                    "parameter_value": parameter_value,
                    "error": repr(err),
                    "traceback": traceback.format_exc(),
                })

    return pd.DataFrame(records), pd.DataFrame(errors)


def add_known_parameter_error_columns(results_long: pd.DataFrame, baseline_scenario: str | None = None) -> pd.DataFrame:
    """Add member-level streamflow/depletion differences relative to the baseline parameter scenario."""
    required = {"member", "scenario", "depletion_cfs", "streamflow_cfs", "pumping_objective_reeval_cfs"}
    missing = required - set(results_long.columns)
    if missing:
        raise KeyError(f"results_long is missing required columns: {sorted(missing)}")

    df = results_long.copy()
    if baseline_scenario is None:
        candidates = [s for s in df["scenario"].dropna().unique() if str(s).startswith("baseline")]
        if not candidates:
            candidates = ["baseline_T"] if "baseline_T" in set(df["scenario"]) else []
        if not candidates:
            raise ValueError("Could not infer baseline scenario. Pass baseline_scenario explicitly.")
        baseline_scenario = candidates[0]

    baseline = df.loc[df["scenario"] == baseline_scenario, ["member", "depletion_cfs", "streamflow_cfs"]].copy()
    if baseline.empty:
        raise ValueError(f"No baseline rows were found for scenario {baseline_scenario!r}.")

    baseline = baseline.rename(columns={
        "depletion_cfs": "baseline_parameter_depletion_cfs",
        "streamflow_cfs": "baseline_parameter_streamflow_cfs",
    })

    df = df.merge(baseline, on="member", how="left")
    df["depletion_change_from_baseline_cfs"] = df["depletion_cfs"] - df["baseline_parameter_depletion_cfs"]
    df["streamflow_change_from_baseline_cfs"] = df["streamflow_cfs"] - df["baseline_parameter_streamflow_cfs"]
    df["absolute_depletion_error_cfs"] = df["depletion_change_from_baseline_cfs"].abs()
    df["absolute_streamflow_error_cfs"] = df["streamflow_change_from_baseline_cfs"].abs()
    df["streamflow_shortfall_below_baseline_cfs"] = np.maximum(df["baseline_parameter_streamflow_cfs"] - df["streamflow_cfs"], 0.0)
    return df


def make_known_parameter_wide(results_long: pd.DataFrame, baseline_scenario: str | None = None) -> pd.DataFrame:
    """Create a member-level wide table for known parameter-error results."""
    df = add_known_parameter_error_columns(results_long, baseline_scenario=baseline_scenario)
    id_cols = ["member"]
    value_cols = [
        "parameter_factor", "parameter_value", "base_parameter_value",
        "T_factor", "T_value", "S_factor", "S_value",
        "pumping_objective_reeval_cfs", "full_model_total_pumping_cfs",
        "depletion_cfs", "streamflow_cfs",
        "depletion_change_from_baseline_cfs", "streamflow_change_from_baseline_cfs",
        "absolute_depletion_error_cfs", "absolute_streamflow_error_cfs",
        "streamflow_shortfall_below_baseline_cfs",
    ]
    available = [c for c in value_cols if c in df.columns]
    wide = df.pivot_table(index=id_cols, columns="scenario", values=available, aggfunc="first")
    wide.columns = [f"{metric}__{scenario}" for metric, scenario in wide.columns]
    wide = wide.reset_index()

    if baseline_scenario is None:
        candidates = [s for s in df["scenario"].dropna().unique() if str(s).startswith("baseline")]
        baseline_scenario = candidates[0] if candidates else "baseline_T"

    base_col = f"pumping_objective_reeval_cfs__{baseline_scenario}"
    if base_col in wide.columns:
        wide[PUMPING_COLUMN_FOR_HYDRO_PLOTS] = wide[base_col]
    return wide


def summarize_known_parameter_scenarios(
    results_long: pd.DataFrame,
    scenario_order: list[str] | None = None,
    baseline_scenario: str | None = None,
) -> pd.DataFrame:
    """Summarize fixed-design known parameter-error results by scenario."""
    df = add_known_parameter_error_columns(results_long, baseline_scenario=baseline_scenario)
    if scenario_order is None:
        scenario_order = list(df["scenario"].drop_duplicates())

    rows = []
    for scenario in scenario_order:
        g = df.loc[df["scenario"] == scenario].copy()
        if g.empty:
            continue
        rows.append({
            "scenario": scenario,
            "parameter_name": str(g["parameter_name"].iloc[0]) if "parameter_name" in g.columns else "",
            "parameter_label": str(g["parameter_label"].iloc[0]) if "parameter_label" in g.columns else "",
            "parameter_symbol": str(g["parameter_symbol"].iloc[0]) if "parameter_symbol" in g.columns else "",
            "parameter_factor": float(g["parameter_factor"].iloc[0]) if "parameter_factor" in g.columns else np.nan,
            "parameter_value": float(g["parameter_value"].iloc[0]) if "parameter_value" in g.columns else np.nan,
            "base_parameter_value": float(g["base_parameter_value"].iloc[0]) if "base_parameter_value" in g.columns else np.nan,
            "T_factor": float(g["T_factor"].iloc[0]) if "T_factor" in g.columns and pd.notna(g["T_factor"].iloc[0]) else np.nan,
            "T_value": float(g["T_value"].iloc[0]) if "T_value" in g.columns and pd.notna(g["T_value"].iloc[0]) else np.nan,
            "S_factor": float(g["S_factor"].iloc[0]) if "S_factor" in g.columns and pd.notna(g["S_factor"].iloc[0]) else np.nan,
            "S_value": float(g["S_value"].iloc[0]) if "S_value" in g.columns and pd.notna(g["S_value"].iloc[0]) else np.nan,
            "n_members": int(len(g)),
            "mean_pumping_objective_cfs": float(g["pumping_objective_reeval_cfs"].mean()),
            "min_pumping_objective_cfs": float(g["pumping_objective_reeval_cfs"].min()),
            "max_pumping_objective_cfs": float(g["pumping_objective_reeval_cfs"].max()),
            "mean_depletion_cfs": float(g["depletion_cfs"].mean()),
            "min_depletion_cfs": float(g["depletion_cfs"].min()),
            "max_depletion_cfs": float(g["depletion_cfs"].max()),
            "mean_streamflow_cfs": float(g["streamflow_cfs"].mean()),
            "min_streamflow_cfs": float(g["streamflow_cfs"].min()),
            "max_streamflow_cfs": float(g["streamflow_cfs"].max()),
            "mean_depletion_change_from_baseline_cfs": float(g["depletion_change_from_baseline_cfs"].mean()),
            "mean_streamflow_change_from_baseline_cfs": float(g["streamflow_change_from_baseline_cfs"].mean()),
            "mean_absolute_depletion_error_cfs": float(g["absolute_depletion_error_cfs"].mean()),
            "max_absolute_depletion_error_cfs": float(g["absolute_depletion_error_cfs"].max()),
            "mean_absolute_streamflow_error_cfs": float(g["absolute_streamflow_error_cfs"].mean()),
            "max_absolute_streamflow_error_cfs": float(g["absolute_streamflow_error_cfs"].max()),
            "mean_streamflow_shortfall_below_baseline_cfs": float(g["streamflow_shortfall_below_baseline_cfs"].mean()),
            "max_streamflow_shortfall_below_baseline_cfs": float(g["streamflow_shortfall_below_baseline_cfs"].max()),
        })
    return pd.DataFrame(rows)


def _scenario_label_for_plot(scenario: str, parameter_label: str = "Parameter") -> str:
    if scenario.startswith("baseline"):
        return f"Baseline {parameter_label}"
    if scenario.endswith("minus_10pct"):
        return f"{parameter_label} -10%"
    if scenario.endswith("plus_10pct"):
        return f"{parameter_label} +10%"
    return scenario


def _scenario_color_for_plot(scenario: str) -> str:
    if scenario.startswith("baseline"):
        return "#1F77B4"
    if scenario.endswith("minus_10pct"):
        return "#2E7D32"
    if scenario.endswith("plus_10pct"):
        return "#C62828"
    return "#4D4D4D"


def plot_depletion_q_known_parameter_fronts(
    results_long: pd.DataFrame,
    outfile: str | Path,
    y_metric: str = "streamflow",
    parameter_label: str | None = None,
):
    """Plot pumping-objective vs streamflow or depletion for known parameter scenarios."""
    if y_metric not in {"streamflow", "depletion"}:
        raise ValueError("y_metric must be either 'streamflow' or 'depletion'.")
    ycol = "streamflow_cfs" if y_metric == "streamflow" else "depletion_cfs"
    ylabel = "Streamflow = 8.6 cfs - depletion (cfs)" if y_metric == "streamflow" else "Depletion (cfs)"
    title_metric = "streamflow" if y_metric == "streamflow" else "depletion"
    df = sort_for_plot(results_long, xcol=PUMPING_COLUMN_FOR_HYDRO_PLOTS)

    if parameter_label is None:
        parameter_label = str(df["parameter_label"].dropna().iloc[0]) if "parameter_label" in df.columns and not df["parameter_label"].dropna().empty else "Parameter"

    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    for scenario in list(df["scenario"].drop_duplicates()):
        g = df.loc[df["scenario"] == scenario].copy()
        if g.empty:
            continue
        ax.plot(
            g[PUMPING_COLUMN_FOR_HYDRO_PLOTS],
            g[ycol],
            marker="o",
            markersize=3,
            linewidth=1.5,
            color=_scenario_color_for_plot(str(scenario)),
            label=_scenario_label_for_plot(str(scenario), parameter_label),
            alpha=0.9,
        )
    ax.set_xlabel("Pumping objective: decision-variable pumping (cfs)")
    ax.set_ylabel(ylabel)
    ax.set_title(f"Fixed depletion_q Pareto designs under known {parameter_label} error: {title_metric}")
    ax.legend(loc="best")
    save_figure(fig, outfile)


def plot_depletion_q_known_parameter_error_2x2(
    wide: pd.DataFrame,
    outfile: str | Path,
    scenario_order: list[str],
    parameter_label: str = "Parameter",
):
    """Create a 2x2 report figure for known parameter-error results."""
    plot_df = sort_for_plot(wide, xcol=PUMPING_COLUMN_FOR_HYDRO_PLOTS)
    x = plot_df[PUMPING_COLUMN_FOR_HYDRO_PLOTS]

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.0))
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    for scenario in scenario_order:
        label = _scenario_label_for_plot(str(scenario), parameter_label)
        color = _scenario_color_for_plot(str(scenario))
        stream_col = f"streamflow_cfs__{scenario}"
        dep_col = f"depletion_cfs__{scenario}"
        if stream_col in plot_df.columns:
            ax_a.plot(x, plot_df[stream_col], marker="o", markersize=3, linewidth=1.4, color=color, label=label)
        if dep_col in plot_df.columns:
            ax_b.plot(x, plot_df[dep_col], marker="o", markersize=3, linewidth=1.4, color=color, label=label)

    for scenario in scenario_order:
        if str(scenario).startswith("baseline"):
            continue
        label = _scenario_label_for_plot(str(scenario), parameter_label)
        color = _scenario_color_for_plot(str(scenario))
        change_col = f"streamflow_change_from_baseline_cfs__{scenario}"
        abs_col = f"absolute_streamflow_error_cfs__{scenario}"
        if change_col in plot_df.columns:
            ax_c.plot(x, plot_df[change_col], marker="o", markersize=3, linewidth=1.4, color=color, label=label)
        if abs_col in plot_df.columns:
            ax_d.plot(x, plot_df[abs_col], marker="o", markersize=3, linewidth=1.4, color=color, label=label)

    ax_c.axhline(0, color="0.35", linestyle="--", linewidth=1.0)

    ax_a.set_title("A. Streamflow response")
    ax_a.set_xlabel("Pumping objective (cfs)")
    ax_a.set_ylabel("Streamflow (cfs)")
    ax_a.legend(loc="best")

    ax_b.set_title("B. Depletion response")
    ax_b.set_xlabel("Pumping objective (cfs)")
    ax_b.set_ylabel("Depletion (cfs)")
    ax_b.legend(loc="best")

    ax_c.set_title(f"C. Signed streamflow change from baseline {parameter_label}")
    ax_c.set_xlabel("Pumping objective (cfs)")
    ax_c.set_ylabel("Streamflow change (cfs)")
    ax_c.legend(loc="best")

    ax_d.set_title("D. Absolute streamflow error")
    ax_d.set_xlabel("Pumping objective (cfs)")
    ax_d.set_ylabel("Absolute streamflow error (cfs)")
    ax_d.legend(loc="best")

    fig.suptitle(f"Fixed depletion_q designs under known +/-10% {parameter_label} error", y=1.02)
    save_figure(fig, outfile)


# Backward-compatible wrappers for older T-only notebook calls.
def add_known_T_error_columns(results_long: pd.DataFrame) -> pd.DataFrame:
    return add_known_parameter_error_columns(results_long, baseline_scenario="baseline_T")


def make_known_T_wide(results_long: pd.DataFrame) -> pd.DataFrame:
    return make_known_parameter_wide(results_long, baseline_scenario="baseline_T")


def summarize_known_T_scenarios(results_long: pd.DataFrame) -> pd.DataFrame:
    return summarize_known_parameter_scenarios(
        results_long,
        scenario_order=["T_minus_10pct", "baseline_T", "T_plus_10pct"],
        baseline_scenario="baseline_T",
    )



# =============================================================================
# Combined T/S perturbation helpers for Notebook 301b
# =============================================================================

def make_initial_dict_with_project_parameter_factors(
    initial_dict_master: dict,
    parameter_factors: dict[str, float] | None = None,
    parameter_values: dict[str, float] | None = None,
) -> dict:
    """
    Return a deep-copied PyCap project dictionary with one or more
    project_properties parameters changed.

    Examples
    --------
    make_initial_dict_with_project_parameter_factors(
        initial_dict_master,
        parameter_factors={"transmissivity": 1.1, "storage": 0.9},
    )
    """
    parameter_factors = {} if parameter_factors is None else dict(parameter_factors)
    parameter_values = {} if parameter_values is None else dict(parameter_values)

    initial_dict = copy.deepcopy(initial_dict_master)

    for parameter_name, factor in parameter_factors.items():
        cfg = get_parameter_config(parameter_name)
        project_key = cfg["project_key"]
        base_value = get_project_parameter_value(initial_dict_master, parameter_name)
        initial_dict["project_properties"][project_key] = float(base_value) * float(factor)

    for parameter_name, value in parameter_values.items():
        cfg = get_parameter_config(parameter_name)
        project_key = cfg["project_key"]
        initial_dict["project_properties"][project_key] = float(value)

    return initial_dict


def run_original_depletion_q_get_results_project_factors(
    q_row: pd.Series,
    context: DepletionQContext,
    parameter_factors: dict[str, float] | None = None,
    parameter_values: dict[str, float] | None = None,
) -> pd.Series:
    """
    Call the original depletion_q get_results() function for one pumping design
    with one or more project_properties parameters changed.
    """
    q_row = q_row.copy()
    q_row.index = [str(i).lower() for i in q_row.index]

    initial_dict = make_initial_dict_with_project_parameter_factors(
        context.initial_dict_master,
        parameter_factors=parameter_factors,
        parameter_values=parameter_values,
    )

    result = context.module.get_results(
        q_row,
        context.obsnames,
        initial_dict,
        context.bdplobs,
        write_csv=False,
    )
    return result


def make_combined_T_storage_scenario_dict(
    t_factors: tuple[float, float, float] = (0.9, 1.0, 1.1),
    s_factors: tuple[float, float, float] = (0.9, 1.0, 1.1),
) -> dict[str, dict]:
    """
    Return a compact known-error corner scenario set for combined T/S testing.

    The scenario set includes baseline, same-direction low/high, and opposing
    T/S perturbations. It does not include T-only or S-only scenarios because
    those are read from Notebook 301a outputs for additive-effect comparison.
    """
    t_low, t_base, t_high = [float(v) for v in t_factors]
    s_low, s_base, s_high = [float(v) for v in s_factors]

    return {
        "baseline_T1_S1": {"T_factor": t_base, "S_factor": s_base, "scenario_label": "Baseline T, baseline S"},
        "Tlow_Slow": {"T_factor": t_low, "S_factor": s_low, "scenario_label": "T -10%, S -10%"},
        "Thigh_Shigh": {"T_factor": t_high, "S_factor": s_high, "scenario_label": "T +10%, S +10%"},
        "Tlow_Shigh": {"T_factor": t_low, "S_factor": s_high, "scenario_label": "T -10%, S +10%"},
        "Thigh_Slow": {"T_factor": t_high, "S_factor": s_low, "scenario_label": "T +10%, S -10%"},
    }


def reevaluate_depletion_q_designs_combined_T_storage(
    pareto_final: pd.DataFrame,
    dv_df: pd.DataFrame,
    q_cols: list[str],
    context: DepletionQContext,
    scenarios: dict[str, dict],
    historic_streamflow_cfs: float = HISTORIC_STREAMFLOW_CFS,
    depletion_obs_name: str = DEPLETION_OBS_NAME,
    progress_every: int = 50,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Re-evaluate depletion_q Pareto designs under combined T/S scenarios.
    """
    records = []
    errors = []
    scenario_items = list(scenarios.items())
    n_total = len(pareto_final) * len(scenario_items)
    counter = 0

    model_q_cols = match_columns_case_insensitive(dv_df, q_cols)
    if not model_q_cols:
        raise KeyError("No model pumping columns were found in dv_df.")

    objective_q_cols = match_columns_case_insensitive(dv_df, context.decvar_q_cols)
    if not objective_q_cols:
        raise KeyError("No decision-variable pumping columns were found in dv_df.")

    base_T = get_project_parameter_value(context.initial_dict_master, "transmissivity")
    base_S = get_project_parameter_value(context.initial_dict_master, "storage")

    for scenario_label, scenario_info in scenario_items:
        T_factor = float(scenario_info["T_factor"])
        S_factor = float(scenario_info["S_factor"])
        T_value = base_T * T_factor
        S_value = base_S * S_factor
        scenario_display = scenario_info.get("scenario_label", scenario_label)

        print(f"Scenario: {scenario_label} | T factor: {T_factor:.6g} | S factor: {S_factor:.6g}")

        for _, row in pareto_final.reset_index(drop=True).iterrows():
            counter += 1
            member = str(row["member"])
            if counter == 1 or counter % progress_every == 0 or counter == n_total:
                print(f"  Re-evaluating {counter} of {n_total}: scenario={scenario_label}, member={member}")

            try:
                if member not in dv_df.index:
                    raise KeyError(f"Member {member!r} was not found in the decision-variable population.")

                q_row = dv_df.loc[member, model_q_cols].copy()

                reeval = run_original_depletion_q_get_results_project_factors(
                    q_row=q_row,
                    context=context,
                    parameter_factors={"transmissivity": T_factor, "storage": S_factor},
                )

                pumping_objective_gpm = dv_df.loc[member, objective_q_cols].astype(float).sum()
                pumping_objective_cfs = pumping_objective_gpm * GPM2CFS

                full_model_total_pumping_gpm = q_row.astype(float).sum()
                full_model_total_pumping_cfs = full_model_total_pumping_gpm * GPM2CFS

                archive_pumping_objective_gpm = row.get("obj_well", np.nan)
                archive_pumping_objective_cfs = archive_pumping_objective_gpm * GPM2CFS if pd.notna(archive_pumping_objective_gpm) else np.nan

                depletion_cfs = float(reeval.loc[depletion_obs_name])
                streamflow_cfs = historic_streamflow_cfs - depletion_cfs

                records.append({
                    "member": member,
                    "generation": row.get("generation", np.nan),
                    "scenario": scenario_label,
                    "scenario_label": scenario_display,
                    "T_factor": T_factor,
                    "S_factor": S_factor,
                    "T_value": T_value,
                    "S_value": S_value,
                    "base_T_value": base_T,
                    "base_S_value": base_S,
                    "archive_pumping_objective_cfs": archive_pumping_objective_cfs,
                    "pumping_objective_reeval_cfs": pumping_objective_cfs,
                    "full_model_total_pumping_cfs": full_model_total_pumping_cfs,
                    "archive_depletion_cfs": row.get(depletion_obs_name, np.nan),
                    "depletion_cfs": depletion_cfs,
                    "streamflow_cfs": streamflow_cfs,
                })

            except Exception as err:
                errors.append({
                    "member": member,
                    "scenario": scenario_label,
                    "T_factor": T_factor,
                    "S_factor": S_factor,
                    "error": repr(err),
                    "traceback": traceback.format_exc(),
                })

    return pd.DataFrame(records), pd.DataFrame(errors)



# =============================================================================
# Generic probability-weighted project-parameter helpers for Notebook 302a
# =============================================================================

def make_normal_project_parameter_probability_table(
    parameter_name: str,
    base_value: float,
    sigma_fraction: float = 0.10,
    n_sigma_each_side: float = 2.0,
    n_values: int = 11,
) -> pd.DataFrame:
    """
    Build a discrete normal probability table for a scalar project parameter.

    Supports transmissivity and storage through project_properties.T and
    project_properties.S. Scenario names are parameter-specific.
    """
    parameter_name = normalize_parameter_name(parameter_name)
    cfg = get_parameter_config(parameter_name)
    tag = cfg["scenario_tag"]

    if n_values < 3:
        raise ValueError("n_values must be at least 3.")
    if sigma_fraction <= 0:
        raise ValueError("sigma_fraction must be positive.")
    if n_sigma_each_side <= 0:
        raise ValueError("n_sigma_each_side must be positive.")

    z_scores = np.linspace(-float(n_sigma_each_side), float(n_sigma_each_side), int(n_values))
    parameter_factors = 1.0 + z_scores * float(sigma_fraction)
    raw_weights = _normal_pdf(z_scores, mean=0.0, sigma=1.0)
    probability_weights = raw_weights / raw_weights.sum()

    rows = []
    for z, factor, weight in zip(z_scores, parameter_factors, probability_weights):
        if abs(z) < 1.0e-12:
            scenario = f"baseline_{tag}"
        elif z < 0:
            scenario = f"{tag}_zminus_{abs(z):.2f}".replace(".", "p")
        else:
            scenario = f"{tag}_zplus_{z:.2f}".replace(".", "p")
        rows.append({
            "parameter_name": parameter_name,
            "parameter_label": cfg["label"],
            "parameter_symbol": cfg["symbol"],
            "scenario": scenario,
            "z_score": float(z),
            "parameter_factor": float(factor),
            "parameter_value": float(base_value) * float(factor),
            "base_parameter_value": float(base_value),
            "probability_weight": float(weight),
        })
    return pd.DataFrame(rows)


def probability_table_to_project_parameter_scenarios(probability_table: pd.DataFrame) -> dict[str, dict]:
    """
    Convert a generic probability table into the scenario dictionary expected by
    reevaluate_depletion_q_designs().
    """
    required = {"scenario", "parameter_name", "parameter_factor", "parameter_value", "probability_weight"}
    missing = required - set(probability_table.columns)
    if missing:
        raise KeyError(f"probability_table is missing required columns: {sorted(missing)}")

    scenarios = {}
    for _, row in probability_table.iterrows():
        parameter_name = normalize_parameter_name(row["parameter_name"])
        scenarios[str(row["scenario"])] = {
            "parameter_name": parameter_name,
            "parameter_factor": float(row["parameter_factor"]),
            "parameter_value": float(row["parameter_value"]),
            "probability_weight": float(row["probability_weight"]),
        }
    return scenarios


# =============================================================================
# Robust known-parameter helpers: baseline scenario fallback
# =============================================================================

def _resolve_baseline_scenario(results_long: pd.DataFrame, requested: str | None = None) -> str:
    available = [str(s) for s in results_long["scenario"].dropna().unique()]
    available_set = set(available)
    if requested is not None and requested in available_set:
        return requested
    candidates = []
    if requested == "baseline_transmissivity":
        candidates += ["baseline_T", "baseline_transmissivity"]
    elif requested == "baseline_T":
        candidates += ["baseline_transmissivity", "baseline_T"]
    elif requested == "baseline_storage":
        candidates += ["baseline_storage"]
    candidates += [s for s in available if s.startswith("baseline")]
    for candidate in candidates:
        if candidate in available_set:
            return candidate
    raise ValueError(f"No baseline scenario could be resolved. Requested={requested!r}. Available scenarios={available}")


def _resolve_scenario_order(results_long: pd.DataFrame, requested_order: list[str] | None = None) -> list[str]:
    available = [str(s) for s in results_long["scenario"].dropna().unique()]
    available_set = set(available)
    if requested_order is not None:
        resolved = [s for s in requested_order if s in available_set]
        if resolved:
            return resolved
    common_orders = [
        ["transmissivity_minus_10pct", "baseline_transmissivity", "transmissivity_plus_10pct"],
        ["T_minus_10pct", "baseline_T", "T_plus_10pct"],
        ["storage_minus_10pct", "baseline_storage", "storage_plus_10pct"],
    ]
    for order in common_orders:
        if all(s in available_set for s in order):
            return order
    return available


def add_known_parameter_error_columns(results_long: pd.DataFrame, baseline_scenario: str | None = None) -> pd.DataFrame:
    required = {"member", "scenario", "depletion_cfs", "streamflow_cfs", "pumping_objective_reeval_cfs"}
    missing = required - set(results_long.columns)
    if missing:
        raise KeyError(f"results_long is missing required columns: {sorted(missing)}")
    df = results_long.copy()
    baseline_scenario = _resolve_baseline_scenario(df, baseline_scenario)
    baseline = df.loc[df["scenario"] == baseline_scenario, ["member", "depletion_cfs", "streamflow_cfs"]].copy()
    baseline = baseline.rename(columns={"depletion_cfs": "baseline_parameter_depletion_cfs", "streamflow_cfs": "baseline_parameter_streamflow_cfs"})
    df = df.merge(baseline, on="member", how="left")
    df["depletion_change_from_baseline_cfs"] = df["depletion_cfs"] - df["baseline_parameter_depletion_cfs"]
    df["streamflow_change_from_baseline_cfs"] = df["streamflow_cfs"] - df["baseline_parameter_streamflow_cfs"]
    df["absolute_depletion_error_cfs"] = df["depletion_change_from_baseline_cfs"].abs()
    df["absolute_streamflow_error_cfs"] = df["streamflow_change_from_baseline_cfs"].abs()
    df["streamflow_shortfall_below_baseline_cfs"] = np.maximum(df["baseline_parameter_streamflow_cfs"] - df["streamflow_cfs"], 0.0)
    return df


def make_known_parameter_wide(results_long: pd.DataFrame, baseline_scenario: str | None = None) -> pd.DataFrame:
    baseline_scenario = _resolve_baseline_scenario(results_long, baseline_scenario)
    df = add_known_parameter_error_columns(results_long, baseline_scenario=baseline_scenario)
    value_cols = ["parameter_factor", "parameter_value", "base_parameter_value", "T_factor", "T_value", "S_factor", "S_value", "pumping_objective_reeval_cfs", "full_model_total_pumping_cfs", "depletion_cfs", "streamflow_cfs", "depletion_change_from_baseline_cfs", "streamflow_change_from_baseline_cfs", "absolute_depletion_error_cfs", "absolute_streamflow_error_cfs", "streamflow_shortfall_below_baseline_cfs"]
    available = [c for c in value_cols if c in df.columns]
    wide = df.pivot_table(index=["member"], columns="scenario", values=available, aggfunc="first")
    wide.columns = [f"{metric}__{scenario}" for metric, scenario in wide.columns]
    wide = wide.reset_index()
    base_col = f"pumping_objective_reeval_cfs__{baseline_scenario}"
    if base_col in wide.columns:
        wide[PUMPING_COLUMN_FOR_HYDRO_PLOTS] = wide[base_col]
    return wide


def summarize_known_parameter_scenarios(results_long: pd.DataFrame, scenario_order: list[str] | None = None, baseline_scenario: str | None = None) -> pd.DataFrame:
    baseline_scenario = _resolve_baseline_scenario(results_long, baseline_scenario)
    scenario_order = _resolve_scenario_order(results_long, scenario_order)
    df = add_known_parameter_error_columns(results_long, baseline_scenario=baseline_scenario)
    rows = []
    for scenario in scenario_order:
        g = df.loc[df["scenario"] == scenario].copy()
        if g.empty:
            continue
        rows.append({
            "scenario": scenario,
            "parameter_name": str(g["parameter_name"].iloc[0]) if "parameter_name" in g.columns else "",
            "parameter_label": str(g["parameter_label"].iloc[0]) if "parameter_label" in g.columns else "",
            "parameter_symbol": str(g["parameter_symbol"].iloc[0]) if "parameter_symbol" in g.columns else "",
            "parameter_factor": float(g["parameter_factor"].iloc[0]) if "parameter_factor" in g.columns and pd.notna(g["parameter_factor"].iloc[0]) else np.nan,
            "parameter_value": float(g["parameter_value"].iloc[0]) if "parameter_value" in g.columns and pd.notna(g["parameter_value"].iloc[0]) else np.nan,
            "base_parameter_value": float(g["base_parameter_value"].iloc[0]) if "base_parameter_value" in g.columns and pd.notna(g["base_parameter_value"].iloc[0]) else np.nan,
            "T_factor": float(g["T_factor"].iloc[0]) if "T_factor" in g.columns and pd.notna(g["T_factor"].iloc[0]) else np.nan,
            "T_value": float(g["T_value"].iloc[0]) if "T_value" in g.columns and pd.notna(g["T_value"].iloc[0]) else np.nan,
            "S_factor": float(g["S_factor"].iloc[0]) if "S_factor" in g.columns and pd.notna(g["S_factor"].iloc[0]) else np.nan,
            "S_value": float(g["S_value"].iloc[0]) if "S_value" in g.columns and pd.notna(g["S_value"].iloc[0]) else np.nan,
            "n_members": int(len(g)),
            "mean_pumping_objective_cfs": float(g["pumping_objective_reeval_cfs"].mean()),
            "min_pumping_objective_cfs": float(g["pumping_objective_reeval_cfs"].min()),
            "max_pumping_objective_cfs": float(g["pumping_objective_reeval_cfs"].max()),
            "mean_depletion_cfs": float(g["depletion_cfs"].mean()),
            "min_depletion_cfs": float(g["depletion_cfs"].min()),
            "max_depletion_cfs": float(g["depletion_cfs"].max()),
            "mean_streamflow_cfs": float(g["streamflow_cfs"].mean()),
            "min_streamflow_cfs": float(g["streamflow_cfs"].min()),
            "max_streamflow_cfs": float(g["streamflow_cfs"].max()),
            "mean_depletion_change_from_baseline_cfs": float(g["depletion_change_from_baseline_cfs"].mean()),
            "mean_streamflow_change_from_baseline_cfs": float(g["streamflow_change_from_baseline_cfs"].mean()),
            "mean_absolute_depletion_error_cfs": float(g["absolute_depletion_error_cfs"].mean()),
            "max_absolute_depletion_error_cfs": float(g["absolute_depletion_error_cfs"].max()),
            "mean_absolute_streamflow_error_cfs": float(g["absolute_streamflow_error_cfs"].mean()),
            "max_absolute_streamflow_error_cfs": float(g["absolute_streamflow_error_cfs"].max()),
            "mean_streamflow_shortfall_below_baseline_cfs": float(g["streamflow_shortfall_below_baseline_cfs"].mean()),
            "max_streamflow_shortfall_below_baseline_cfs": float(g["streamflow_shortfall_below_baseline_cfs"].max()),
        })
    return pd.DataFrame(rows)



# =============================================================================
# Joint T/S probability-weighted uncertainty helpers for Notebook 302b
# =============================================================================

def make_joint_T_storage_probability_table(
    base_T: float,
    base_S: float,
    t_sigma_fraction: float = 0.10,
    s_sigma_fraction: float = 0.10,
    n_sigma_each_side: float = 2.0,
    n_values_each: int = 5,
) -> pd.DataFrame:
    """
    Build an independent joint probability grid for transmissivity and storage.

    The joint probability is:

        P(T, S) = P(T) * P(S)

    and the joint weights are normalized to sum to 1.
    """
    if n_values_each < 3:
        raise ValueError("n_values_each must be at least 3.")
    if t_sigma_fraction <= 0 or s_sigma_fraction <= 0:
        raise ValueError("sigma fractions must be positive.")
    if n_sigma_each_side <= 0:
        raise ValueError("n_sigma_each_side must be positive.")

    z_values = np.linspace(-float(n_sigma_each_side), float(n_sigma_each_side), int(n_values_each))

    t_raw = _normal_pdf(z_values, mean=0.0, sigma=1.0)
    s_raw = _normal_pdf(z_values, mean=0.0, sigma=1.0)
    t_weights = t_raw / t_raw.sum()
    s_weights = s_raw / s_raw.sum()

    rows = []
    for t_z, t_weight in zip(z_values, t_weights):
        t_factor = 1.0 + float(t_z) * float(t_sigma_fraction)
        for s_z, s_weight in zip(z_values, s_weights):
            s_factor = 1.0 + float(s_z) * float(s_sigma_fraction)
            scenario = (
                f"Tz{t_z:+.2f}_Sz{s_z:+.2f}"
                .replace("+", "plus")
                .replace("-", "minus")
                .replace(".", "p")
            )

            rows.append({
                "scenario": scenario,
                "T_z_score": float(t_z),
                "S_z_score": float(s_z),
                "T_factor": float(t_factor),
                "S_factor": float(s_factor),
                "T_value": float(base_T) * float(t_factor),
                "S_value": float(base_S) * float(s_factor),
                "diffusivity_factor": float(t_factor) / float(s_factor),
                "T_probability_weight": float(t_weight),
                "S_probability_weight": float(s_weight),
                "joint_probability_weight_raw": float(t_weight) * float(s_weight),
            })

    table = pd.DataFrame(rows)
    table["joint_probability_weight"] = table["joint_probability_weight_raw"] / table["joint_probability_weight_raw"].sum()
    table["scenario_label"] = table.apply(
        lambda r: f"T {r['T_factor']:.2f}, S {r['S_factor']:.2f}",
        axis=1,
    )
    return table


def joint_probability_table_to_combined_scenarios(probability_table: pd.DataFrame) -> dict[str, dict]:
    """Convert a joint T/S probability table into scenarios for the combined T/S re-evaluator."""
    required = {"scenario", "T_factor", "S_factor", "scenario_label"}
    missing = required - set(probability_table.columns)
    if missing:
        raise KeyError(f"probability_table is missing required columns: {sorted(missing)}")

    scenarios = {}
    for _, row in probability_table.iterrows():
        scenarios[str(row["scenario"])] = {
            "T_factor": float(row["T_factor"]),
            "S_factor": float(row["S_factor"]),
            "scenario_label": str(row["scenario_label"]),
        }
    return scenarios


def add_joint_probability_metadata(results_long: pd.DataFrame, probability_table: pd.DataFrame) -> pd.DataFrame:
    """Attach joint T/S probability metadata to long re-evaluation results."""
    meta_cols = [
        "scenario",
        "T_z_score",
        "S_z_score",
        "T_factor",
        "S_factor",
        "T_value",
        "S_value",
        "diffusivity_factor",
        "T_probability_weight",
        "S_probability_weight",
        "joint_probability_weight",
        "scenario_label",
    ]
    meta_cols = [c for c in meta_cols if c in probability_table.columns]
    meta = probability_table[meta_cols].copy()

    drop_cols = [c for c in meta_cols if c != "scenario" and c in results_long.columns]
    df = results_long.drop(columns=drop_cols, errors="ignore").copy()
    merged = df.merge(meta, on="scenario", how="left", suffixes=("", "_probability"))

    if "joint_probability_weight" not in merged.columns:
        raise KeyError("joint_probability_weight was not created during metadata merge.")
    if "diffusivity_factor" not in merged.columns:
        raise KeyError("diffusivity_factor was not created during metadata merge.")

    return merged


def summarize_joint_probability_weighted_depletion_q(results_long: pd.DataFrame) -> pd.DataFrame:
    """
    Create member-level probability-weighted metrics for joint T/S uncertainty.
    """
    required = {
        "member",
        "joint_probability_weight",
        "pumping_objective_reeval_cfs",
        "depletion_cfs",
        "streamflow_cfs",
        "T_factor",
        "S_factor",
        "diffusivity_factor",
    }
    missing = required - set(results_long.columns)
    if missing:
        raise KeyError(f"results_long is missing required columns: {sorted(missing)}")

    rows = []
    for member, g in results_long.groupby("member", sort=False):
        g = g.copy()
        weights = pd.to_numeric(g["joint_probability_weight"], errors="coerce").to_numpy(dtype=float)
        if np.nansum(weights) <= 0:
            weights = np.ones(len(g), dtype=float) / max(len(g), 1)
        else:
            weights = weights / np.nansum(weights)

        stream = pd.to_numeric(g["streamflow_cfs"], errors="coerce").to_numpy(dtype=float)
        dep = pd.to_numeric(g["depletion_cfs"], errors="coerce").to_numpy(dtype=float)
        diff = pd.to_numeric(g["diffusivity_factor"], errors="coerce").to_numpy(dtype=float)
        t_factors = pd.to_numeric(g["T_factor"], errors="coerce").to_numpy(dtype=float)
        s_factors = pd.to_numeric(g["S_factor"], errors="coerce").to_numpy(dtype=float)

        # Baseline is the scenario closest to T_factor=1 and S_factor=1.
        baseline_score = np.abs(t_factors - 1.0) + np.abs(s_factors - 1.0)
        baseline_idx = int(np.nanargmin(baseline_score))

        baseline_stream = float(stream[baseline_idx])
        baseline_dep = float(dep[baseline_idx])
        expected_stream = float(np.nansum(weights * stream))
        expected_dep = float(np.nansum(weights * dep))

        stream_p05, stream_p50, stream_p95 = weighted_quantile(stream, weights, [0.05, 0.50, 0.95])
        dep_p05, dep_p50, dep_p95 = weighted_quantile(dep, weights, [0.05, 0.50, 0.95])

        shortfall = np.maximum(baseline_stream - stream, 0.0)
        abs_stream_error = np.abs(stream - baseline_stream)
        abs_dep_error = np.abs(dep - baseline_dep)

        worst_idx = int(np.nanargmin(stream))
        best_idx = int(np.nanargmax(stream))

        rows.append({
            "member": member,
            PUMPING_COLUMN_FOR_HYDRO_PLOTS: float(g[PUMPING_COLUMN_FOR_HYDRO_PLOTS].iloc[0]),
            "baseline_streamflow_cfs": baseline_stream,
            "baseline_depletion_cfs": baseline_dep,
            "expected_streamflow_cfs": expected_stream,
            "expected_depletion_cfs": expected_dep,
            "expected_streamflow_bias_from_baseline_cfs": expected_stream - baseline_stream,
            "expected_depletion_bias_from_baseline_cfs": expected_dep - baseline_dep,
            "probability_weighted_absolute_streamflow_error_cfs": float(np.nansum(weights * abs_stream_error)),
            "probability_weighted_absolute_depletion_error_cfs": float(np.nansum(weights * abs_dep_error)),
            "probability_weighted_streamflow_shortfall_cfs": float(np.nansum(weights * shortfall)),
            "probability_of_streamflow_shortfall": float(np.nansum(weights[stream < baseline_stream])),
            "streamflow_std_cfs": float(np.sqrt(np.nansum(weights * (stream - expected_stream) ** 2))),
            "depletion_std_cfs": float(np.sqrt(np.nansum(weights * (dep - expected_dep) ** 2))),
            "streamflow_p05_cfs": float(stream_p05),
            "streamflow_p50_cfs": float(stream_p50),
            "streamflow_p95_cfs": float(stream_p95),
            "depletion_p05_cfs": float(dep_p05),
            "depletion_p50_cfs": float(dep_p50),
            "depletion_p95_cfs": float(dep_p95),
            "best_case_streamflow_cfs": float(stream[best_idx]),
            "worst_case_streamflow_cfs": float(stream[worst_idx]),
            "best_case_T_factor": float(t_factors[best_idx]),
            "best_case_S_factor": float(s_factors[best_idx]),
            "best_case_diffusivity_factor": float(diff[best_idx]),
            "worst_case_T_factor": float(t_factors[worst_idx]),
            "worst_case_S_factor": float(s_factors[worst_idx]),
            "worst_case_diffusivity_factor": float(diff[worst_idx]),
            "expected_diffusivity_factor": float(np.nansum(weights * diff)),
            "min_diffusivity_factor": float(np.nanmin(diff)),
            "max_diffusivity_factor": float(np.nanmax(diff)),
            "n_joint_scenarios": int(len(g)),
        })

    return pd.DataFrame(rows)


def summarize_joint_probability_weighted_overall(member_summary: pd.DataFrame) -> pd.DataFrame:
    """Create an overall summary table for joint probability-weighted metrics."""
    metrics = {
        "n_members": len(member_summary),
        "mean_expected_streamflow_bias_cfs": member_summary["expected_streamflow_bias_from_baseline_cfs"].mean(),
        "mean_expected_depletion_bias_cfs": member_summary["expected_depletion_bias_from_baseline_cfs"].mean(),
        "mean_probability_weighted_absolute_streamflow_error_cfs": member_summary["probability_weighted_absolute_streamflow_error_cfs"].mean(),
        "max_probability_weighted_absolute_streamflow_error_cfs": member_summary["probability_weighted_absolute_streamflow_error_cfs"].max(),
        "mean_probability_weighted_absolute_depletion_error_cfs": member_summary["probability_weighted_absolute_depletion_error_cfs"].mean(),
        "max_probability_weighted_absolute_depletion_error_cfs": member_summary["probability_weighted_absolute_depletion_error_cfs"].max(),
        "mean_probability_weighted_streamflow_shortfall_cfs": member_summary["probability_weighted_streamflow_shortfall_cfs"].mean(),
        "max_probability_weighted_streamflow_shortfall_cfs": member_summary["probability_weighted_streamflow_shortfall_cfs"].max(),
        "mean_probability_of_streamflow_shortfall": member_summary["probability_of_streamflow_shortfall"].mean(),
        "mean_streamflow_std_cfs": member_summary["streamflow_std_cfs"].mean(),
        "max_streamflow_std_cfs": member_summary["streamflow_std_cfs"].max(),
        "mean_depletion_std_cfs": member_summary["depletion_std_cfs"].mean(),
        "max_depletion_std_cfs": member_summary["depletion_std_cfs"].max(),
        "mean_worst_case_streamflow_cfs": member_summary["worst_case_streamflow_cfs"].mean(),
        "mean_best_case_streamflow_cfs": member_summary["best_case_streamflow_cfs"].mean(),
    }
    return pd.DataFrame({"metric": list(metrics.keys()), "value": list(metrics.values())})


def summarize_joint_grid_by_scenario(results_long: pd.DataFrame) -> pd.DataFrame:
    """Summarize mean response by joint T/S scenario across all members."""
    required = {"scenario", "T_factor", "S_factor", "diffusivity_factor", "streamflow_cfs", "depletion_cfs"}
    missing = required - set(results_long.columns)
    if missing:
        raise KeyError(f"results_long is missing required columns: {sorted(missing)}")

    baseline = results_long.loc[
        np.isclose(results_long["T_factor"], 1.0) & np.isclose(results_long["S_factor"], 1.0),
        ["member", "streamflow_cfs", "depletion_cfs"],
    ].rename(columns={"streamflow_cfs": "baseline_streamflow_cfs", "depletion_cfs": "baseline_depletion_cfs"})

    df = results_long.merge(baseline, on="member", how="left")
    df["streamflow_change_from_baseline_cfs"] = df["streamflow_cfs"] - df["baseline_streamflow_cfs"]
    df["depletion_change_from_baseline_cfs"] = df["depletion_cfs"] - df["baseline_depletion_cfs"]

    return (
        df.groupby(["scenario", "scenario_label", "T_factor", "S_factor", "diffusivity_factor", "joint_probability_weight"], as_index=False)
        .agg(
            n_members=("member", "count"),
            mean_streamflow_cfs=("streamflow_cfs", "mean"),
            mean_depletion_cfs=("depletion_cfs", "mean"),
            mean_streamflow_change_from_baseline_cfs=("streamflow_change_from_baseline_cfs", "mean"),
            mean_depletion_change_from_baseline_cfs=("depletion_change_from_baseline_cfs", "mean"),
            mean_abs_streamflow_change_from_baseline_cfs=("streamflow_change_from_baseline_cfs", lambda x: float(np.mean(np.abs(x)))),
            max_abs_streamflow_change_from_baseline_cfs=("streamflow_change_from_baseline_cfs", lambda x: float(np.max(np.abs(x)))),
        )
        .sort_values(["T_factor", "S_factor"])
    )


def plot_joint_probability_heatmap(probability_table: pd.DataFrame, outfile: str | Path):
    """Plot the joint T/S probability grid."""
    pivot = probability_table.pivot_table(index="S_factor", columns="T_factor", values="joint_probability_weight", aggfunc="first")
    fig, ax = plt.subplots(figsize=(7.2, 5.8))
    im = ax.imshow(pivot.values, origin="lower", aspect="auto")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_xticklabels([f"{v:.2f}" for v in pivot.columns])
    ax.set_yticklabels([f"{v:.2f}" for v in pivot.index])
    ax.set_xlabel("T factor")
    ax.set_ylabel("S factor")
    ax.set_title("Joint T/S probability weights")
    fig.colorbar(im, ax=ax, label="Joint probability weight")
    save_figure(fig, outfile)


def plot_joint_grid_metric_heatmap(grid_summary: pd.DataFrame, value_col: str, outfile: str | Path, title: str, cbar_label: str):
    """Plot a T/S grid metric as a heatmap."""
    pivot = grid_summary.pivot_table(index="S_factor", columns="T_factor", values=value_col, aggfunc="first")
    fig, ax = plt.subplots(figsize=(7.2, 5.8))
    im = ax.imshow(pivot.values, origin="lower", aspect="auto")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_xticklabels([f"{v:.2f}" for v in pivot.columns])
    ax.set_yticklabels([f"{v:.2f}" for v in pivot.index])
    ax.set_xlabel("T factor")
    ax.set_ylabel("S factor")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label=cbar_label)
    save_figure(fig, outfile)


def plot_joint_diffusivity_vs_streamflow_change(grid_summary: pd.DataFrame, outfile: str | Path):
    """Plot mean streamflow change against T/S diffusivity factor."""
    df = grid_summary.copy().sort_values("diffusivity_factor")
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    ax.scatter(df["diffusivity_factor"], df["mean_streamflow_change_from_baseline_cfs"], s=55)
    for _, row in df.iterrows():
        ax.annotate(
            f"T{row['T_factor']:.1f}/S{row['S_factor']:.1f}",
            (row["diffusivity_factor"], row["mean_streamflow_change_from_baseline_cfs"]),
            textcoords="offset points",
            xytext=(4, 4),
            fontsize=8,
        )
    ax.axhline(0, color="0.35", linestyle="--", linewidth=1.0)
    ax.axvline(1, color="0.35", linestyle="--", linewidth=1.0)
    ax.set_xlabel("Diffusivity factor = T factor / S factor")
    ax.set_ylabel("Mean streamflow change from baseline (cfs)")
    ax.set_title("Joint T/S scenarios: streamflow change follows T/S diffusivity factor")
    save_figure(fig, outfile)



# =============================================================================
# 302b tolerance fix for probability of streamflow shortfall
# =============================================================================

SHORTFALL_TOLERANCE_CFS = 1.0e-10


def summarize_joint_probability_weighted_depletion_q(
    results_long: pd.DataFrame,
    shortfall_tolerance_cfs: float = SHORTFALL_TOLERANCE_CFS,
) -> pd.DataFrame:
    """
    Create member-level probability-weighted metrics for joint T/S uncertainty.

    The probability of streamflow shortfall uses a small tolerance so machine-
    precision differences around the baseline scenario are not counted as real
    shortfalls.
    """
    required = {
        "member",
        "joint_probability_weight",
        "pumping_objective_reeval_cfs",
        "depletion_cfs",
        "streamflow_cfs",
        "T_factor",
        "S_factor",
        "diffusivity_factor",
    }
    missing = required - set(results_long.columns)
    if missing:
        raise KeyError(f"results_long is missing required columns: {sorted(missing)}")

    rows = []
    tol = float(shortfall_tolerance_cfs)

    for member, g in results_long.groupby("member", sort=False):
        g = g.copy()
        weights = pd.to_numeric(g["joint_probability_weight"], errors="coerce").to_numpy(dtype=float)
        if np.nansum(weights) <= 0:
            weights = np.ones(len(g), dtype=float) / max(len(g), 1)
        else:
            weights = weights / np.nansum(weights)

        stream = pd.to_numeric(g["streamflow_cfs"], errors="coerce").to_numpy(dtype=float)
        dep = pd.to_numeric(g["depletion_cfs"], errors="coerce").to_numpy(dtype=float)
        diff = pd.to_numeric(g["diffusivity_factor"], errors="coerce").to_numpy(dtype=float)
        t_factors = pd.to_numeric(g["T_factor"], errors="coerce").to_numpy(dtype=float)
        s_factors = pd.to_numeric(g["S_factor"], errors="coerce").to_numpy(dtype=float)

        baseline_score = np.abs(t_factors - 1.0) + np.abs(s_factors - 1.0)
        baseline_idx = int(np.nanargmin(baseline_score))

        baseline_stream = float(stream[baseline_idx])
        baseline_dep = float(dep[baseline_idx])
        expected_stream = float(np.nansum(weights * stream))
        expected_dep = float(np.nansum(weights * dep))

        stream_p05, stream_p50, stream_p95 = weighted_quantile(stream, weights, [0.05, 0.50, 0.95])
        dep_p05, dep_p50, dep_p95 = weighted_quantile(dep, weights, [0.05, 0.50, 0.95])

        shortfall = np.maximum(baseline_stream - stream, 0.0)
        abs_stream_error = np.abs(stream - baseline_stream)
        abs_dep_error = np.abs(dep - baseline_dep)
        shortfall_mask = stream < (baseline_stream - tol)

        worst_idx = int(np.nanargmin(stream))
        best_idx = int(np.nanargmax(stream))

        rows.append({
            "member": member,
            PUMPING_COLUMN_FOR_HYDRO_PLOTS: float(g[PUMPING_COLUMN_FOR_HYDRO_PLOTS].iloc[0]),
            "baseline_streamflow_cfs": baseline_stream,
            "baseline_depletion_cfs": baseline_dep,
            "expected_streamflow_cfs": expected_stream,
            "expected_depletion_cfs": expected_dep,
            "expected_streamflow_bias_from_baseline_cfs": expected_stream - baseline_stream,
            "expected_depletion_bias_from_baseline_cfs": expected_dep - baseline_dep,
            "probability_weighted_absolute_streamflow_error_cfs": float(np.nansum(weights * abs_stream_error)),
            "probability_weighted_absolute_depletion_error_cfs": float(np.nansum(weights * abs_dep_error)),
            "probability_weighted_streamflow_shortfall_cfs": float(np.nansum(weights * shortfall)),
            "probability_of_streamflow_shortfall": float(np.nansum(weights[shortfall_mask])),
            "shortfall_tolerance_cfs": tol,
            "streamflow_std_cfs": float(np.sqrt(np.nansum(weights * (stream - expected_stream) ** 2))),
            "depletion_std_cfs": float(np.sqrt(np.nansum(weights * (dep - expected_dep) ** 2))),
            "streamflow_p05_cfs": float(stream_p05),
            "streamflow_p50_cfs": float(stream_p50),
            "streamflow_p95_cfs": float(stream_p95),
            "depletion_p05_cfs": float(dep_p05),
            "depletion_p50_cfs": float(dep_p50),
            "depletion_p95_cfs": float(dep_p95),
            "best_case_streamflow_cfs": float(stream[best_idx]),
            "worst_case_streamflow_cfs": float(stream[worst_idx]),
            "best_case_T_factor": float(t_factors[best_idx]),
            "best_case_S_factor": float(s_factors[best_idx]),
            "best_case_diffusivity_factor": float(diff[best_idx]),
            "worst_case_T_factor": float(t_factors[worst_idx]),
            "worst_case_S_factor": float(s_factors[worst_idx]),
            "worst_case_diffusivity_factor": float(diff[worst_idx]),
            "expected_diffusivity_factor": float(np.nansum(weights * diff)),
            "min_diffusivity_factor": float(np.nanmin(diff)),
            "max_diffusivity_factor": float(np.nanmax(diff)),
            "n_joint_scenarios": int(len(g)),
        })

    return pd.DataFrame(rows)
