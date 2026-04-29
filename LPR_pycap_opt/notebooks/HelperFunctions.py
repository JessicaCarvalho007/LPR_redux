
from pathlib import Path
import copy
import pandas as pd
import numpy as np
import yaml

from pycap.analysis_project import Project

SUMMARY_STATS = ["mean", "std", "25%", "50%", "75%", "max"]

def load_pareto_archive_summary(run_name, run_dir):
    run_dir = Path(run_dir)
    pareto_file = run_dir / f"{run_name}.pareto.archive.summary.csv.zip"
    if not pareto_file.exists():
        raise FileNotFoundError(f"Could not find required zip file: {pareto_file}")
    return pd.read_csv(pareto_file), pareto_file


def load_final_feasible_pareto_front(run_name, run_dir):
    pareto_df, pareto_file = load_pareto_archive_summary(run_name, run_dir)

    required_cols = {"member", "generation", "nsga2_front", "is_feasible"}
    missing_cols = required_cols - set(pareto_df.columns)
    if missing_cols:
        raise KeyError(f"Pareto summary file is missing required columns: {sorted(missing_cols)}")

    pareto_df = pareto_df.loc[
        (pareto_df["nsga2_front"] == 1) &
        (pareto_df["is_feasible"] == 1)
    ].copy()

    pareto_df["member"] = pareto_df["member"].astype(str)

    final_generation = pareto_df["generation"].max()
    pareto_df_final = pareto_df.loc[
        pareto_df["generation"] == final_generation
    ].copy()

    if pareto_df_final.empty:
        raise ValueError("No feasible Pareto members were found in the final generation.")

    return pareto_df_final, pareto_file, final_generation


def load_decision_variable_population(run_dir):
    run_dir = Path(run_dir)

    dv_files = sorted(run_dir.glob("*dv_pop.csv.zip"))
    if not dv_files:
        raise FileNotFoundError(f"No zipped dv_pop files were found in {run_dir}")

    frames = [pd.read_csv(f, index_col=0) for f in dv_files]

    init_file = run_dir / "initial_dvpop.csv"
    if init_file.exists():
        frames.append(pd.read_csv(init_file, index_col=0))

    dv_df = pd.concat(frames, axis=0)
    dv_df.index = dv_df.index.astype(str)
    dv_df = dv_df[~dv_df.index.duplicated(keep="first")]

    return dv_df


def get_q_columns(df):
    return [c for c in df.columns if "_q" in str(c).lower()]


def load_base_dict(run_dir):
    yml_file = Path(run_dir) / "LPR_Redux.yml"
    if not yml_file.exists():
        raise FileNotFoundError(f"Could not find {yml_file}")
    with open(yml_file, "r") as f:
        return yaml.safe_load(f)


def _flatten_stream_table(df):
    """
    Convert a stream-depletion table with rows like 418, total_combined
    and columns like LPR into a Series indexed as lpr:418:bdpl, etc.
    """
    out = {}
    for row_name in df.index:
        for col_name in df.columns:
            obs_name = f"{str(col_name).lower()}:{str(row_name)}:bdpl"
            out[obs_name] = df.loc[row_name, col_name]
    return pd.Series(out, dtype=float)


def _normalize_stream_name(stream_name):
    return str(stream_name).split(":")[0]


def _build_bdpl_series_from_wells(ap, initial_dict):
    """
    Manual fallback for pycap versions that do not expose agg_base_stream_df.

    Builds the equivalent of the base-stream depletion table by taking the
    maximum depletion for each well-stream pair, converting to cfs, and then
    summing into total_existing, total_proposed, and total_combined rows.
    """
    if not hasattr(ap, "wells"):
        raise AttributeError("Project object has no 'wells' attribute for manual fallback.")

    rows = {}
    total_existing = {}
    total_proposed = {}
    total_combined = {}

    for well_key, well_obj in ap.wells.items():
        if not hasattr(well_obj, "depletion"):
            continue

        if well_key in initial_dict and isinstance(initial_dict[well_key], dict):
            well_label = str(initial_dict[well_key].get("name", well_key))
            status = str(initial_dict[well_key].get("status", "pending")).lower()
        else:
            well_label = str(getattr(well_obj, "name", well_key))
            status = str(getattr(well_obj, "status", "pending")).lower()

        row = {}

        for stream_name, ts in well_obj.depletion.items():
            base_stream = _normalize_stream_name(stream_name)
            arr = np.asarray(ts, dtype=float)
            max_depl_cfs = float(np.nanmax(arr) / (3600.0 * 24.0))

            row[base_stream] = row.get(base_stream, 0.0) + max_depl_cfs
            total_combined[base_stream] = total_combined.get(base_stream, 0.0) + max_depl_cfs

            if status == "existing":
                total_existing[base_stream] = total_existing.get(base_stream, 0.0) + max_depl_cfs
            else:
                total_proposed[base_stream] = total_proposed.get(base_stream, 0.0) + max_depl_cfs

        rows[well_label] = row

    stream_df = pd.DataFrame.from_dict(rows, orient="index").fillna(0.0)

    if total_existing:
        stream_df.loc["total_existing", list(total_existing.keys())] = pd.Series(total_existing)
    if total_proposed:
        stream_df.loc["total_proposed", list(total_proposed.keys())] = pd.Series(total_proposed)
    if total_combined:
        stream_df.loc["total_combined", list(total_combined.keys())] = pd.Series(total_combined)

    stream_df = stream_df.fillna(0.0)
    return _flatten_stream_table(stream_df)


def _extract_bdpl_series_from_project(ap, initial_dict):
    """
    Robustly extract bdpl-style results from Project output across different
    pycap versions.
    """
    # First try in-memory aggregate tables
    if hasattr(ap, "agg_base_stream_df") and isinstance(ap.agg_base_stream_df, pd.DataFrame):
        return _flatten_stream_table(ap.agg_base_stream_df.copy())

    if hasattr(ap, "agg_df") and isinstance(ap.agg_df, pd.DataFrame):
        agg_df = ap.agg_df.copy()
        depl_cols = [c for c in agg_df.columns if ":depl" in str(c).lower()]
        if depl_cols:
            out = {}
            for row_name in agg_df.index:
                for col_name in depl_cols:
                    river_name = str(col_name).split(":")[0].lower()
                    obs_name = f"{river_name}:{str(row_name)}:bdpl"
                    out[obs_name] = agg_df.loc[row_name, col_name]
            return pd.Series(out, dtype=float)

    # Next try writing/reading csv outputs
    if hasattr(ap, "report_responses"):
        try:
            ap.report_responses()
        except Exception:
            pass

    if hasattr(ap, "write_responses_csv"):
        try:
            ap.write_responses_csv()
        except Exception:
            pass

    for attr_name in ["csv_stream_output_filename", "csv_output_filename"]:
        if hasattr(ap, attr_name):
            candidate = Path(getattr(ap, attr_name))
            if candidate.exists():
                candidate_df = pd.read_csv(candidate, index_col=0)
                if "base_stream_depletion" in candidate.name.lower():
                    return _flatten_stream_table(candidate_df)
                depl_cols = [c for c in candidate_df.columns if ":depl" in str(c).lower()]
                if depl_cols:
                    out = {}
                    for row_name in candidate_df.index:
                        for col_name in depl_cols:
                            river_name = str(col_name).split(":")[0].lower()
                            obs_name = f"{river_name}:{str(row_name)}:bdpl"
                            out[obs_name] = candidate_df.loc[row_name, col_name]
                    return pd.Series(out, dtype=float)

    # Final fallback: compute the stream depletion table directly from ap.wells
    return _build_bdpl_series_from_wells(ap, initial_dict)


def get_results_with_T(pars, initial_dict, bdplobs=None, T_multiplier=1.0, write_csv=False):
    pars = pars.copy()
    pars.index = [str(i).lower() for i in pars.index]

    qpars = pars.loc[pars.index.str.contains("_q")]

    upd_dict = copy.deepcopy(initial_dict)

    upd_dict["project_properties"]["T"] = initial_dict["project_properties"]["T"] * T_multiplier

    if "Max_T" in upd_dict["project_properties"]:
        upd_dict["project_properties"]["Max_T"] = initial_dict["project_properties"]["Max_T"] * T_multiplier
    if "Min_T" in upd_dict["project_properties"]:
        upd_dict["project_properties"]["Min_T"] = initial_dict["project_properties"]["Min_T"] * T_multiplier

    for idx, val in qpars.items():
        well_key = idx.split("__")[0]
        upd_dict[well_key]["Q"] = val

    ap = Project(
        None,
        write_results_to_files=write_csv,
        project_dict=upd_dict
    )

    if hasattr(ap, "aggregate_results"):
        try:
            ap.aggregate_results()
        except Exception:
            pass

    if hasattr(ap, "report_responses"):
        try:
            ap.report_responses()
        except Exception:
            pass

    result_series = _extract_bdpl_series_from_project(ap, upd_dict)
    result_series.index = result_series.index.astype(str)

    if bdplobs is not None:
        result_series = result_series.loc[bdplobs]

    return result_series


def reevaluate_member_set(member_q_df, base_dict, scenario_name, T_multiplier, print_every=10):
    results = {}

    for i, (member, row) in enumerate(member_q_df.iterrows(), start=1):
        if (i == 1) or (i % print_every == 0) or (i == len(member_q_df)):
            print(f"{scenario_name}: member {i} of {len(member_q_df)}")
        results[str(member)] = get_results_with_T(
            row,
            base_dict,
            T_multiplier=T_multiplier,
            write_csv=False
        )

    scenario_df = pd.DataFrame(results).T
    scenario_df.index = scenario_df.index.astype(str)
    scenario_df.index.name = "member"
    scenario_df["scenario"] = scenario_name
    scenario_df["T_multiplier"] = T_multiplier

    return scenario_df


def get_bdpl_columns(df):
    return [c for c in df.columns if str(c).endswith(":bdpl")]


def add_tradeoff_metrics(df, member_q_df, pumping_sign=1.0, q_to_cfs=1.0, tradeoff_mode="sum", tradeoff_obs=None, baseline_flow_cfs=None):
    out = df.copy()

    q_cols = get_q_columns(member_q_df)
    if not q_cols:
        raise ValueError("No pumping decision-variable columns containing '_q' were found.")

    total_pumping = pumping_sign * member_q_df[q_cols].sum(axis=1) * q_to_cfs
    total_pumping.index = total_pumping.index.astype(str)
    out["total_pumping_cfs"] = total_pumping.reindex(out.index)

    bdpl_cols = get_bdpl_columns(out)
    if not bdpl_cols:
        raise ValueError("No ':bdpl' columns were found in the reevaluated results.")

    if tradeoff_mode == "sum":
        out["depletion_metric_cfs"] = out[bdpl_cols].sum(axis=1)
        out["depletion_metric_source"] = "sum_of_all_bdpl_columns"
    elif tradeoff_mode == "selected_obs":
        if tradeoff_obs is None:
            raise ValueError("TRADEOFF_OBS must be set when TRADEOFF_MODE = 'selected_obs'.")
        if tradeoff_obs not in out.columns:
            raise KeyError(
                f"TRADEOFF_OBS '{tradeoff_obs}' was not found in the results. "
                f"Available bdpl columns include: {bdpl_cols[:10]}"
            )
        out["depletion_metric_cfs"] = out[tradeoff_obs]
        out["depletion_metric_source"] = tradeoff_obs
    else:
        raise ValueError("TRADEOFF_MODE must be either 'sum' or 'selected_obs'.")

    if baseline_flow_cfs is not None:
        out["streamflow_metric_cfs"] = baseline_flow_cfs - out["depletion_metric_cfs"]

    return out


def make_describe_table(df, value_cols, percentiles=(0.25, 0.50, 0.75)):
    desc = df[value_cols].describe(percentiles=list(percentiles)).loc[SUMMARY_STATS].copy()
    desc.index.name = "statistic"
    return desc


def make_summary_by_scenario(tradeoff_df, value_cols):
    pieces = []
    for scenario, grp in tradeoff_df.groupby("scenario", sort=False):
        desc = make_describe_table(grp, value_cols)
        desc["scenario"] = scenario
        desc = desc.reset_index()
        pieces.append(desc)

    summary_df = pd.concat(pieces, axis=0, ignore_index=True)
    return summary_df


def make_member_level_deltas(tradeoff_df, value_cols):
    baseline_df = (
        tradeoff_df.loc[tradeoff_df["scenario"] == "baseline", ["member"] + value_cols]
        .copy()
        .set_index("member")
        .sort_index()
    )

    delta_frames = []
    for scenario in [s for s in tradeoff_df["scenario"].unique() if s != "baseline"]:
        scenario_df = (
            tradeoff_df.loc[tradeoff_df["scenario"] == scenario, ["member"] + value_cols]
            .copy()
            .set_index("member")
            .sort_index()
        )

        aligned = scenario_df[value_cols] - baseline_df[value_cols]
        aligned["member"] = aligned.index
        aligned["scenario"] = scenario
        delta_frames.append(aligned.reset_index(drop=True))

    if delta_frames:
        delta_df = pd.concat(delta_frames, axis=0, ignore_index=True)
    else:
        delta_df = pd.DataFrame(columns=["member", "scenario"] + value_cols)

    return delta_df


def make_delta_summary(delta_df, value_cols):
    pieces = []
    for scenario, grp in delta_df.groupby("scenario", sort=False):
        desc = make_describe_table(grp, value_cols)
        desc["scenario"] = scenario
        desc = desc.reset_index()
        pieces.append(desc)

    if pieces:
        return pd.concat(pieces, axis=0, ignore_index=True)
    return pd.DataFrame(columns=["statistic", "scenario"] + value_cols)
