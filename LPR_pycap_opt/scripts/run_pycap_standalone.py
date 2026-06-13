import sys, os, yaml
import pyemu
from pycap.analysis_project import Project
from pathlib import Path
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor


def instantiate():
    # instantiate the project with paths and filenames
    datapath = Path('./')
    pestpath = Path('./')
    with open(datapath / 'LPR_Redux.yml','r') as ifp:
        initial_dict = yaml.safe_load(ifp)

    obsnames = [i.split("!")[1].lower() for i in open(pestpath/'allobs.out.ins', 'r').readlines()[1:]]
    bdplobs = [i.lower() for i in obsnames if i.endswith('bdpl')]
    tsobs = [i.lower() for i in obsnames if not i.endswith('bdpl')]
    tslox = list(set([i.split('__')[0] for i in tsobs]))

    """Instantiate the project with paths and filenames."""
    # only read out year 5 for time series ::: hard coded
    times = range(365*4,365*5+1)
    return times, initial_dict, bdplobs, tslox

def get_results(pars, times, obsnames, initial_dict, bdplobs, tslox, write_csv= False):
    
    # make sure parameter indices are cast to lower()
    pars.index = [i.lower() for i in pars.index]

    # parse and update parameter values
    gpars = pars.loc[pars.index.str.contains('global')]
    qpars = pars.loc[pars.index.str.contains('_q')]
    apars = pars.loc[pars.index.str.contains('apport')]

    # make an updated dict copy 
    upd_dict = initial_dict.copy()

    # now update by groups. start with global which is bespoke
    upd_dict['project_properties']['T'] = gpars["global_t"]
    upd_dict['project_properties']['S'] = gpars["global_s"]
    
    # next over Q
    for idx,val in qpars.items():
        upd_dict[idx.split('__')[0]]['Q'] = val
    
    # finally apportionment
    for idx,val in apars.items():
        wellnum, appname = idx.split('__')
        upd_dict[wellnum][appname]['apportionment'] = val

    ap = Project(None, write_csv, upd_dict)
    ap.aggregate_results()
    ap.write_responses_csv()



    bdf = ap.agg_base_stream_df
    bdf.index=[f"lpr:{i}:bdpl" for i in bdf.index]
    bdf = bdf.loc[bdplobs]
    bdf['variable']=bdf.index
    bdf.rename(columns={'LPR':'value'}, inplace=True)
    tsdf = ap.all_depl_ts
    tsdf.columns = [i.lower() for i in tsdf.columns]
    tsdf = tsdf.loc[times][tslox].melt(ignore_index=False)
    tsdf.index=[f"{j}__{i}" for i,j in zip(tsdf.index,tsdf.variable)]
    allout  = pd.concat([bdf[['variable','value']],
                        tsdf]).loc[obsnames]
    return allout    


def process_realization(args):
    creal, row, times, obs_names, initial_dict, bdplobs, tslox, par_names = args
    allout = get_results(row[par_names], times, obs_names, initial_dict, bdplobs, tslox)
    return creal, allout.loc[obs_names].value.to_numpy()

def standalone_worker(times, initial_dict, bdplobs, tslox):
    # Read RNS run data
    rns = pyemu.helpers.RunStor('./prior_mc.rns')
    runs_df = rns.get_data()
    _, par_names, obs_names = rns.file_info('./prior_mc.rns')

    # Prepare arguments for parallel processing
    args_list = [
        (creal, runs_df.loc[creal], times, obs_names, initial_dict, bdplobs, tslox, par_names)
        for creal in runs_df.index
    ]

    # Parallel execution
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(process_realization, args_list))

    # Populate results
    obsvals = np.zeros((len(runs_df), len(obs_names)))
    for i, (creal, obs_array) in enumerate(results):
        obsvals[i, :] = obs_array

    runs_df.loc[:, obs_names] = obsvals
    rns.update(runs_df)

if __name__== "__main__":
    times, initial_dict, bdplobs, tslox = instantiate()
    standalone_worker(times, initial_dict, bdplobs, tslox)




