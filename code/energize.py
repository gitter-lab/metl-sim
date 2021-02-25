""" this is the run script that executes on the server """
# todo: rename this file to run_mutate.py or similar to differentiate from potential runs to prep PDB files

import argparse
import subprocess
import shutil
import os
from os.path import isdir, join, basename
import uuid
import socket
import csv

import shortuuid
import numpy as np
import pandas as pd

from gen_rosetta_args import gen_rosetta_args
import time


class RosettaError(Exception):
    # a simple custom error for when Rosetta gives a bad return code
    pass


def prep_working_dir(template_dir, working_dir, pdb_fn, variant, relax_distance, relax_repeats, overwrite_wd=False):
    """ prep the working directory by copying over files from the template directory, modifying as needed """
    # delete the current working directory if one exists
    if overwrite_wd:
        try:
            shutil.rmtree(working_dir)
        except FileNotFoundError:
            pass

    # create the directory
    try:
        os.mkdir(working_dir)
    except FileExistsError:
        print("Working directory '{}' already exists. "
              "Delete it before continuing or set overwrite_wd=True.".format(working_dir))
        raise

    # copy over PDB file into rosetta working dir and rename it to structure.pdb
    shutil.copyfile(pdb_fn, join(working_dir, "structure.pdb"))

    # generate the rosetta arguments (Rosetta scripts XML files and resfile) for this variant
    gen_rosetta_args(template_dir, variant, relax_distance, relax_repeats, working_dir)

    # copy over files from the template dir that don't need to be changed
    files_to_copy = ["flags_mutate", "flags_relax"]
    for fn in files_to_copy:
        shutil.copy(join(template_dir, fn), working_dir)


def run_mutate_relax_steps(rosetta_main_dir, working_dir, mutate_default_max_cycles, relax_nstruct):
    # path to the relax binary which is used for both the mutate and relax steps
    relax_bin_fn = join(rosetta_main_dir, "source/bin/relax.static.linuxgccrelease")

    # path to the rosetta database
    database_path = join(rosetta_main_dir, "database")

    # run the mutate step
    mutate_cmd = [relax_bin_fn, '-database', database_path,
                  '-default_max_cycles', str(mutate_default_max_cycles), '@flags_mutate']
    return_code = subprocess.call(mutate_cmd, cwd=working_dir)
    if return_code != 0:
        raise RosettaError("Mutate step did not execute successfully. Return code: {}".format(return_code))

    # rename the resulting score.sc to keep the score files from the mutate and relax steps separate
    os.rename(join(working_dir, "score.sc"), join(working_dir, "mutate.sc"))

    # run the relax step
    relax_cmd = [relax_bin_fn, '-database', database_path, '-nstruct', str(relax_nstruct), '@flags_relax']
    return_code = subprocess.call(relax_cmd, cwd=working_dir)
    if return_code != 0:
        raise RosettaError("Relax step did not execute successfully. Return code: {}".format(return_code))


def parse_score_sc(score_sc_fn, agg_method="avg"):
    """ parse the score.sc file from the energize run, aggregating energies and appending info about variant """
    score_df = pd.read_csv(score_sc_fn, delim_whitespace=True, skiprows=1, header=0)

    # drop the "SCORE:" and "description" columns, these won't be needed for final output
    score_df = score_df.drop(["SCORE:", "description"], axis=1)

    # special case: only 1 structure was generated, no need to aggerate
    if len(score_df) == 1:
        parsed_df = score_df.iloc[[0]]
    else:
        if agg_method == "min_energy_avg":
            # select the structure(s) with the minimum total_score and average the energies if multiple structures
            # we average just in case there are some structures with the same min total_score but different energies
            min_score_df = score_df[score_df.total_score == score_df.total_score.min()]
            parsed_df = min_score_df.mean(axis=0).to_frame().T
        elif agg_method == "min_energy_first":
            # select structures with min total_score and use the first one
            min_score_df = score_df[score_df.total_score == score_df.total_score.min()]
            parsed_df = min_score_df.iloc[[0]]
        elif agg_method == "avg":
            # take the average of all structures, not just the ones with lowest score
            parsed_df = score_df.mean(axis=0).to_frame().T
        else:
            raise ValueError("invalid aggregation method: {}".format(agg_method))

    return parsed_df


def run_single_variant(rosetta_main_dir, pdb_fn, variant, rosetta_hparams, output_dir, save_wd=False):
    template_dir = "energize_wd_template"
    working_dir = "energize_wd"

    # staging directory for variant outputs, which will be combined after all variants have been run
    staging_dir = join(output_dir, "staging")
    os.makedirs(staging_dir, exist_ok=True)

    # set up the working directory (copies the pdb file, sets up the rosetta scripts, etc)
    prep_working_dir(template_dir, working_dir, pdb_fn, variant,
                     rosetta_hparams["relax_distance"], rosetta_hparams["relax_repeats"], overwrite_wd=True)

    # run the mutate and relax steps
    print("Running Rosetta on variant {} {}".format(basename(pdb_fn), variant))
    start = time.time()
    run_mutate_relax_steps(rosetta_main_dir, working_dir,
                           rosetta_hparams["mutate_default_max_cycles"], rosetta_hparams["relax_nstruct"])
    run_time = time.time() - start
    print("Processing variant {} {} took {}".format(basename(pdb_fn), variant, run_time))

    # parse the output file into a single-record csv, appending info about variant
    # place in a staging directory and combine with other variants that run during this job
    sdf = parse_score_sc(join(working_dir, "score.sc"))
    # append info about this variant
    sdf.insert(0, "pdb_fn", [basename(pdb_fn)])
    sdf.insert(1, "variant", [variant])
    sdf.insert(2, "start_time", [start])
    sdf.insert(3, "run_time", [run_time])
    # note: it's not the best practice to have filenames with periods and commas
    #   could pass in the loop ID for this single variant and use that to save the file
    sdf.to_csv(join(staging_dir, "{}_{}_energies.csv".format(basename(pdb_fn), variant)), index=False)

    # if the flag is set, save all files in the working directory for this variant
    # these go directly to the output directory instead of the staging directory
    if save_wd:
        shutil.copytree(working_dir, join(output_dir, "wd_{}_{}".format(basename(pdb_fn), variant)))

    # clean up the working dir in preparation for next variant
    shutil.rmtree(working_dir)

    return run_time


def get_log_dir_name(args, job_uuid):
    """ get a log dir name for this run, whether running locally or on HTCondor """

    # note: it would be informative to include the PDB file in the log dir name.
    # however, i might set up the script to accept different PDB files for different variants (defined in the
    # input variants text file). in which case, there'd be multiple PDB files. so best keep PDB file out of it
    # for now, until I figure out whether I want the runs to support only one or multiple PDB files
    format_args = [args.cluster, args.process, time.strftime("%Y-%m-%d_%H-%M-%S"), job_uuid]
    log_dir_str = "energize_{}_{}_{}_{}"
    log_dir = log_dir_str.format(*format_args)
    return log_dir


def combine_outputs(staging_dir):
    """ combine the outputs from individual variants into a single csv """
    # Note that these will probably NOT be in the same order as they were run (can add timestamp to record)
    output_fns = [join(staging_dir, x) for x in os.listdir(staging_dir)]

    # read individual dataframes into a list
    dfs = []
    for fn in output_fns:
        df = pd.read_csv(fn, header=0)
        dfs.append(df)

    # combine into a single dataframe
    combined_df = pd.concat(dfs, axis=0, ignore_index=True)
    return combined_df


def save_csv_from_dict(save_fn, d):
    with open(save_fn, "w") as f:
        w = csv.writer(f)
        for k, v in d.items():
            w.writerow([k, v])


def save_argparse_args(args_dict, out_fn):
    """ save argparse arguments out to a file """
    with open(out_fn, "w") as f:
        for k, v in args_dict.items():
            # if a flag is set to false, dont include it in the argument file
            if (not isinstance(v, bool)) or (isinstance(v, bool) and v):
                f.write("--{}\n".format(k))
                # if a flag is true, no need to specify the "true" value
                if not isinstance(v, bool):
                    f.write("{}\n".format(v))


def main(args):

    # generate a unique identifier for this run
    job_uuid = shortuuid.encode(uuid.uuid4())[:12]

    # create the log directory for this job
    log_dir = join(args.log_dir_base, get_log_dir_name(args, job_uuid))
    os.makedirs(log_dir)

    # save the argparse arguments back out to a file
    save_argparse_args(vars(args), join(log_dir, "args.txt"))

    # create an info file for this job (cluster, process, server, github commit id, etc)
    job_info = {"uuid": job_uuid, "cluster": args.cluster, "process": args.process, "hostname": socket.gethostname(),
                "github_commit_id": args.commit_id, "script_start_time": time.time()}
    save_csv_from_dict(join(log_dir, "job.csv"), job_info)

    # create a dictionary of just rosetta hyperparameters that can be passed around throughout functions and saved
    rosetta_hparams = {"mutate_default_max_cycles": args.mutate_default_max_cycles,
                       "relax_distance": args.relax_distance,
                       "relax_repeats": args.relax_repeats,
                       "relax_nstruct": args.relax_nstruct}
    save_csv_from_dict(join(log_dir, "hparams.csv"), rosetta_hparams)

    # load the variants that will be processed with this run
    # this file contains a line for each variant
    # and each line contains the pdb file and the comma-delimited substitutions (e.g. "2qmt_p.pdb A23P,R67L")
    with open(args.variants_fn, "r") as f:
        pdbs_variants = f.readlines()

    # loop through each variant, model it with rosetta, save results
    # individual variant outputs will be placed in the staging directory
    for pdb_variant in pdbs_variants:
        pdb_basename, variant = pdb_variant.split()
        pdb_fn = join(args.pdb_dir, pdb_basename)

        # todo: run_single_variant can throw a RosettaError if Rosetta fails to run for a particular variant
        # but what are the chances that one variant fails and the others don't? I feel like any problems would
        # be universal for the particular protein or condor job, so maybe just let it crash?
        run_single_variant(args.rosetta_main_dir, pdb_fn, variant, rosetta_hparams, log_dir, args.save_wd)

    # todo: check if any of the variants failed to run... and if so, try to run them again here? or add to failed list?

    # combine outputs in the staging directory into a single csv file
    cdf = combine_outputs(join(log_dir, "staging"))
    # add additional column for job uuid
    cdf.insert(2, "job_uuid", job_uuid)
    # save in the main log directory
    cdf.to_csv(join(log_dir, "energies.csv"), index=False)

    # compress outputs, delete the output staging directory, etc
    shutil.rmtree(join(log_dir, "staging"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    # main input files
    parser.add_argument("--rosetta_main_dir",
                        help="The main directory of the rosetta distribution containing the binaries and "
                             "other files that are needed for this script (does not have to be full distribution)",
                        type=str,
                        default="/home/sg/Desktop/rosetta/rosetta_bin_linux_2020.50.61505_bundle/main")

    parser.add_argument("--variants_fn",
                        help="the file containing the variants",
                        type=str)

    parser.add_argument("--pdb_dir",
                        help="directory containing pdb files referenced in variants_fn",
                        type=str,
                        default="prepared_pdb_files")

    # energize hyperparameters
    parser.add_argument("--mutate_default_max_cycles",
                        help="number of optimization cycles in the mutate step",
                        type=int,
                        default=100)
    parser.add_argument("--relax_repeats",
                        help="number of FastRelax repeats in the relax step",
                        type=int,
                        default=15)
    parser.add_argument("--relax_nstruct",
                        help="number of structures (restarts) in the relax step",
                        type=int,
                        default=1)
    parser.add_argument("--relax_distance",
                        help="distance threshold in angstroms for the residue selector in the relax step",
                        type=float,
                        default=10.0)

    # logging and output options
    parser.add_argument("--save_wd",
                        help="set this to save the full working directory for each variant",
                        action="store_true")

    parser.add_argument("--log_dir_base",
                        help="base output directory where log dirs for each run will be placed",
                        default="output/energize_outputs")

    # HTCondor job information and program run information
    parser.add_argument("--cluster",
                        help="cluster (when running on HTCondor)",
                        type=str,
                        default="local")

    parser.add_argument("--process",
                        help="process (when running on HTCondor)",
                        type=str,
                        default="local")

    parser.add_argument("--commit_id",
                        help="the github commit id corresponding to this version of the code",
                        type=str,
                        default="no_commit_id")

    main(parser.parse_args())
