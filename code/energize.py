""" this is the run script that executes on the server """

import argparse
import subprocess
import shutil
import os
import sys
from os.path import isdir, join, basename, abspath
import uuid
import socket
import csv
import platform

import shortuuid
import numpy as np
import pandas as pd

from templates import fill_templates
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
              "Delete it before continuing or set overwrite_wd=True.".format(working_dir),
              flush=True)
        raise

    # copy over PDB file into rosetta working dir and rename it to structure.pdb
    shutil.copyfile(pdb_fn, join(working_dir, "structure.pdb"))

    # fill the template rosetta arguments (Rosetta scripts XML files and resfile) for this variant
    # note that if the variant is the wild-type (no mutations), then there is no need to fill these in (wont be used)
    if variant != "_wt":
        fill_templates(template_dir, variant, relax_distance, relax_repeats, working_dir)

    # copy over files from the template dir that don't need to be changed
    files_to_copy = ["flags_mutate", "flags_relax", "flags_relax_all", "flags_filter", "flags_centroid",
                     "filter_3rd.xml", "total_hydrophobic_weights_version1.wts",
                     "total_hydrophobic_weights_version2.wts"]

    for fn in files_to_copy:
        shutil.copy(join(template_dir, fn), working_dir)


def run_mutate_step(relax_bin_fn, database_path, mutate_default_max_cycles, working_dir):
    # todo: should this use the relax binary or rosetta_scripts binary? both seem to work the same
    mutate_cmd = [relax_bin_fn, '-database', database_path,
                  '-default_max_cycles', str(mutate_default_max_cycles), '@flags_mutate']
    mutate_out_fn = join(working_dir, "mutate.out")
    # to completely void output, can direct it to subprocess.DEVNULL instead of f
    with open(mutate_out_fn, "w") as f:
        return_code = subprocess.call(mutate_cmd, cwd=working_dir, stdout=f, stderr=f)
    if return_code != 0:
        raise RosettaError("Mutate step did not execute successfully. Return code: {}".format(return_code))


def run_relax_step(relax_bin_fn, database_path, relax_nstruct, relax_repeats, working_dir, variant_has_mutations=True):
    # todo: should this use the relax binary or rosetta_scripts binary? both seem to work the same
    if variant_has_mutations:
        # this is the main way to run relax for variants, where the rosettascript protocol specified in @flags_relax
        # and relax_template.xml is used to only relax around the mutated residues
        relax_cmd = [relax_bin_fn, '-database', database_path, '-nstruct', str(relax_nstruct), '@flags_relax']
    else:
        # this is for running relax on the wild-type structure, without mutating it, in which case we don't
        # select residues around the mutated positions (there are none), just relax the whole structure
        relax_cmd = [relax_bin_fn, '-database', database_path, '-nstruct', str(relax_nstruct),
                     '-relax:default_repeats', str(relax_repeats), '@flags_relax_all']

    relax_out_fn = join(working_dir, "relax.out")
    with open(relax_out_fn, "w") as f:
        return_code = subprocess.call(relax_cmd, cwd=working_dir, stdout=f, stderr=f)
    if return_code != 0:
        raise RosettaError("Relax step did not execute successfully. Return code: {}".format(return_code))


def run_filter_step(rosetta_scripts_bin_fn, database_path, working_dir):
    filter_cmd = [rosetta_scripts_bin_fn, '-database', database_path, '@flags_filter']
    filter_out_fn = join(working_dir, "filter.out")
    with open(filter_out_fn, "w") as f:
        return_code = subprocess.call(filter_cmd, cwd=working_dir, stdout=f, stderr=f)
    if return_code != 0:
        raise RosettaError("Filter step did not execute successfully. Return code: {}".format(return_code))


def run_centroid_step(score_jd2_bin_fn, database_path, working_dir):
    centroid_cmd = [score_jd2_bin_fn, '-database', database_path, '@flags_centroid']
    centroid_out_fn = join(working_dir, "centroid.out")
    with open(centroid_out_fn, "w") as f:
        return_code = subprocess.call(centroid_cmd, cwd=working_dir, stdout=f, stderr=f)
    if return_code != 0:
        raise RosettaError("Centroid step did not execute successfully. Return code: {}".format(return_code))


def run_rosetta_pipeline(rosetta_main_dir, working_dir, mutate_default_max_cycles, relax_nstruct, relax_repeats,
                         variant_has_mutations=True):

    # keep track of how long it takes to run Rosetta
    all_start = time.time()

    # path to rosetta binaries which are used for the various steps
    # subprocess wants a full path... or "./", so let's just add abspath
    if platform.system() == "Linux":
        relax_bin_fn = "relax.static.linuxgccrelease"
        rosetta_scripts_bin_fn = "rosetta_scripts.static.linuxgccrelease"
        score_jd2_bin_fn = "score_jd2.static.linuxgccrelease"
    elif platform.system() == "Darwin":
        relax_bin_fn = "relax.static.macosclangrelease"
        rosetta_scripts_bin_fn = "rosetta_scripts.static.macosclangrelease"
        score_jd2_bin_fn = "score_jd2.static.macosclangrelease"
    else:
        raise ValueError("unsupported platform: {}".format(platform.system()))

    relax_bin_fn = abspath(join(rosetta_main_dir, "source", "bin", relax_bin_fn))
    rosetta_scripts_bin_fn = abspath(join(rosetta_main_dir, "source", "bin", rosetta_scripts_bin_fn))
    score_jd2_bin_fn = abspath(join(rosetta_main_dir, "source", "bin", score_jd2_bin_fn))

    # path to the rosetta database
    database_path = abspath(join(rosetta_main_dir, "database"))

    # this branch logic is just handling the special case of the "_wt" variant (no mutations)
    if variant_has_mutations:
        mt_start_time = time.time()
        run_mutate_step(relax_bin_fn, database_path, mutate_default_max_cycles, working_dir)
        mt_run_time = time.time() - mt_start_time
        # print("Mutate step took {:.2f}".format(mt_run_time))
    else:
        # variant has no mutations (wild-type), so just rename structure.pdb to structure_0001.pdb
        # which is the expected structure filename for the remaining pipelie steps
        os.rename(join(working_dir, "structure.pdb"), join(working_dir, "structure_0001.pdb"))

    # relax also needs to know whether the variant has mutations because it needs to either run relax
    # around just the mutated residues or around the whole structure
    rx_start_time = time.time()
    run_relax_step(relax_bin_fn, database_path, relax_nstruct, relax_repeats, working_dir, variant_has_mutations)
    rx_run_time = time.time() - rx_start_time
    # print("Relax step took {:.2f}".format(rx_run_time))

    filt_start_time = time.time()
    run_filter_step(rosetta_scripts_bin_fn, database_path, working_dir)
    filt_run_time = time.time() - filt_start_time
    # print("Filter step took {:.2f}".format(filt_run_time))

    cent_start_time = time.time()
    run_centroid_step(score_jd2_bin_fn, database_path, working_dir)
    cent_run_time = time.time() - cent_start_time
    # print("Centroid step took {:.2f}".format(cent_run_time))

    # keep track of how long it takes to run all steps
    all_run_time = time.time() - all_start

    run_times = {"mutate": mt_run_time,
                 "relax": rx_run_time,
                 "filter": filt_run_time,
                 "centroid": cent_run_time,
                 "all": all_run_time}

    return run_times


def parse_score_sc(score_sc_fn, agg_method="avg"):
    """ parse the score.sc file from the energize run, aggregating energies and appending info about variant
        this function has also been co-opted to parse the centroid and filter score files, which should only
        have 1 possible record, so no need to do any agg (and it shouldn't) """
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


def run_single_variant(rosetta_main_dir, pdb_fn, variant, rosetta_hparams, staging_dir, output_dir, save_wd=False):
    # grab the start time for this variant
    start_time = time.time()

    template_dir = "templates/energize_wd_template"
    # todo: use a variant-specific working directory in the output directory (safer)
    working_dir = "energize_wd"

    # if the working directory exists from a previously failed variant, remove it before starting new variant
    if isdir(working_dir):
        shutil.rmtree(working_dir)

    # set up the working directory (copies the pdb file, sets up the rosetta scripts, etc)
    prep_working_dir(template_dir, working_dir, pdb_fn, variant,
                     rosetta_hparams["relax_distance"], rosetta_hparams["relax_repeats"], overwrite_wd=True)

    # run the mutate and relax steps
    variant_has_mutations = False if variant == "_wt" else True
    run_times = run_rosetta_pipeline(rosetta_main_dir, working_dir,
                                     rosetta_hparams["mutate_default_max_cycles"],
                                     rosetta_hparams["relax_nstruct"],
                                     rosetta_hparams["relax_repeats"],
                                     variant_has_mutations)

    # copy over or parse any files we want to keep from the working directory to the output directory
    # the stdout and stderr outputs from rosetta are in the working directory under mutate.out and relax.out
    # however, we don't need them, so we are going to leave them there and just parse the energies

    # parse the output files into a single-record csv, appending info about variant
    # place in a staging directory and combine with other variants that run during this job
    score_df = parse_score_sc(join(working_dir, "relax.sc"))
    filter_df = parse_score_sc(join(working_dir, "filter.sc"))
    centroid_df = parse_score_sc(join(working_dir, "centroid.sc"))

    # the total_score from filter and centroid probably won't be used, but let's keep them in just in case
    # just need to resolve the name conflict with the total_score from score_df
    filter_df.rename(columns={"total_score": "filter_total_score"}, inplace=True)
    centroid_df.rename(columns={"total_score": "centroid_total_score"}, inplace=True)

    full_df = pd.concat((score_df, filter_df, centroid_df), axis=1)

    # append info about this variant
    full_df.insert(0, "pdb_fn", [basename(pdb_fn)])
    full_df.insert(1, "variant", [variant])
    full_df.insert(2, "start_time", [time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_time))])
    full_df.insert(3, "run_time", [int(run_times["all"])])
    full_df.insert(4, "mutate_run_time", [int(run_times["mutate"])])
    full_df.insert(5, "relax_run_time", [int(run_times["relax"])])
    full_df.insert(6, "filter_run_time", [int(run_times["filter"])])
    full_df.insert(7, "centroid_run_time", [int(run_times["centroid"])])

    # note: it's not the best practice to have filenames with periods and commas
    #   could pass in the loop ID for this single variant and use that to save the file
    full_df.to_csv(join(staging_dir, "{}_{}_energies.csv".format(basename(pdb_fn), variant)), index=False)

    # if the flag is set, save all files in the working directory for this variant
    # these go directly to the output directory instead of the staging directory
    if save_wd:
        shutil.copytree(working_dir, join(output_dir, "wd_{}_{}".format(basename(pdb_fn), variant)))

    # clean up the working dir in preparation for next variant
    shutil.rmtree(working_dir)

    return run_times["all"]


def get_log_dir_name(args, job_uuid, start_time):
    """ get a log dir name for this run, whether running locally or on HTCondor """

    # note: it would be informative to include the PDB file in the log dir name.
    # however, i might set up the script to accept different PDB files for different variants (defined in the
    # input variants text file). in which case, there'd be multiple PDB files. so best keep PDB file out of it
    # for now, until I figure out whether I want the runs to support only one or multiple PDB files
    format_args = [args.cluster, args.process, time.strftime("%Y-%m-%d_%H-%M-%S", time.gmtime(start_time)), job_uuid]
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

    # rough script start time for logging
    # this will be logged in UTC time (GM time) in the log directory name and output files
    script_start = time.time()

    # generate a unique identifier for this run
    job_uuid = shortuuid.encode(uuid.uuid4())[:12]

    # create the log directory for this job
    log_dir = join(args.log_dir_base, get_log_dir_name(args, job_uuid, script_start))
    os.makedirs(log_dir)

    # save the argparse arguments back out to a file
    save_argparse_args(vars(args), join(log_dir, "args.txt"))

    # create an info file for this job (cluster, process, server, github commit id, etc)
    start_time_utc = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(script_start))
    job_info = {"uuid": job_uuid, "cluster": args.cluster, "process": args.process, "hostname": socket.gethostname(),
                "github_commit_id": args.commit_id, "script_start_time": start_time_utc}
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
        pdbs_variants = f.read().splitlines()

    # set up the staging dir....
    staging_dir = join(log_dir, "staging")
    os.makedirs(staging_dir, exist_ok=True)

    # loop through each variant, model it with rosetta, save results
    # individual variant outputs will be placed in the staging directory
    failed = []  # keep track of any variants that file after 3 attempts
    for i, pdb_variant in enumerate(pdbs_variants):
        pdb_basename, variant = pdb_variant.split()
        pdb_fn = join(args.pdb_dir, pdb_basename)

        # sometimes a single variant fails but others were/are successful
        # give variants 3 attempts at success, then move on to other variants
        # in worst case scenario, there is a system-level problem that will cause all variants to fail
        num_attempts_per_variant = 3
        for attempt in range(num_attempts_per_variant):
            try:
                print("Running Rosetta on variant {} {} ({}/{})".format(basename(pdb_fn), variant,
                                                                        i + 1, len(pdbs_variants)), flush=True)
                run_time = run_single_variant(args.rosetta_main_dir, pdb_fn, variant, rosetta_hparams, staging_dir,
                                              log_dir, args.save_wd)
                print("Processing variant {} {} took {:.2f}".format(basename(pdb_fn), variant, run_time), flush=True)

            except (RosettaError, FileNotFoundError) as e:
                print(e, flush=True)
                print("Encountered error running variant {} {}. "
                      "Attempts remaining: {}".format(pdb_basename, variant, num_attempts_per_variant - attempt - 1),
                      flush=True)
            else:
                break
        else:
            # else clause of the for loop triggers if we burned through all attempts without success
            # add this variant to a failed_variants.txt file and continue with the other variants
            failed.append(pdb_variant)

    # save a txt file with failed variants (if there are failed variants)
    if len(failed) > 0:
        with open(join(log_dir, "failed.txt"), "w") as f:
            for fv in failed:
                f.write("{}\n".format(fv))

    # if any variants were successful, concat the outputs into a final energies.csv
    if len(failed) < len(pdbs_variants):
        # combine outputs in the staging directory into a single csv file
        cdf = combine_outputs(join(log_dir, "staging"))
        # add additional column for job uuid
        cdf.insert(2, "job_uuid", job_uuid)
        # save in the main log directory
        cdf.to_csv(join(log_dir, "energies.csv"), index=False)

    # compress outputs, delete the output staging directory, etc
    shutil.rmtree(join(log_dir, "staging"))

    if (len(failed) / len(pdbs_variants)) > args.allowable_failure_fraction:
        # too many variants failed in this job. exit with failure code.
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        fromfile_prefix_chars="@")

    # main input files
    parser.add_argument("--rosetta_main_dir",
                        help="The main directory of the rosetta distribution containing the binaries and "
                             "other files that are needed for this script (does not have to be full distribution)",
                        type=str,
                        default="rosetta_minimal")

    parser.add_argument("--variants_fn",
                        help="the file containing the variants",
                        type=str)

    parser.add_argument("--pdb_dir",
                        help="directory containing pdb files referenced in variants_fn",
                        type=str,
                        default="pdb_files/prepared_pdb_files")

    parser.add_argument("--allowable_failure_fraction",
                        help="fraction of variants that can fail so that this job is still considered successful",
                        type=float,
                        default=0.25)


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
