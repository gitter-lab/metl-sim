""" this is the run script that executes on the server """
# todo: rename this file to run_mutate.py or similar to differentiate from potential runs to prep PDB files

import argparse
import subprocess
import shutil
import os
from os.path import isdir, join, basename

import numpy as np
import pandas as pd

from gen_rosetta_args import gen_rosetta_args
from parse_energies_txt import parse_multiple
from parse_score_sc import parse_score
import time


class RosettaError(Exception):
    # a simple custom error for when Rosetta gives a bad return code
    pass


def prep_working_dir(template_dir, working_dir, pdb_fn, variant, wt_offset, overwrite_wd=False):
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
    gen_rosetta_args(template_dir, variant, wt_offset, working_dir)

    # copy over files from the template dir that don't need to be changed
    files_to_copy = ["flags_mutate", "flags_relax"]
    for fn in files_to_copy:
        shutil.copy(join(template_dir, fn), working_dir)


def run_mutate_relax_steps(rosetta_main_dir, working_dir):

    # path to the relax binary which is used for both the mutate and relax steps
    relax_bin_fn = join(rosetta_main_dir, "source/bin/relax.static.linuxgccrelease")

    # path to the rosetta database
    database_path = join(rosetta_main_dir, "database")

    # run the mutate step
    mutate_cmd = [relax_bin_fn, '-database', database_path, '@flags_mutate']
    return_code = subprocess.call(mutate_cmd, cwd=working_dir)

    if return_code != 0:
        raise RosettaError("Mutate step did not execute successfully. Return code: {}".format(return_code))

    # rename the resulting score.sc to keep the score files from the mutate and relax steps separate
    os.rename(join(working_dir, "score.sc"), join(working_dir, "mutate.sc"))

    # run the relax step
    relax_cmd = [relax_bin_fn, '-database', database_path, '@flags_relax']
    return_code = subprocess.call(relax_cmd, cwd=working_dir)

    if return_code != 0:
        raise RosettaError("Relax step did not execute successfully. Return code: {}".format(return_code))


def parse_score_sc(vid, variant, pdb_fn, score_sc_fn, agg_method="avg"):
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

    # append info about this variant
    parsed_df.insert(0, "vid", [vid])
    parsed_df.insert(1, "variant", [variant])
    parsed_df.insert(2, "pdb_fn", [pdb_fn])
    # todo: it would be great to include the version of the code that generated this result (github tag)?

    return parsed_df


def run_single_variant(rosetta_main_dir, vid, variant, pdb_fn, wt_offset, save_wd=False):

    template_dir = "energize_wd_template"
    working_dir = "energize_wd"
    # todo: the output dir should be unique to each condor run (and probably each local run).
    #   this will make things easier for transferring condor outputs and handling local runs
    output_dir = "output/energize_outputs/"
    # staging directory for variant outputs, which will be combined after all variants have been run
    # todo: this can probably be passed in as an argument or just keep it here
    staging_dir = join(output_dir, "staging")
    os.makedirs(staging_dir, exist_ok=True)

    start = time.time()
    print("Running variant {}: {}".format(vid, variant))

    # set up the working directory (copies the pdb file, sets up the rosetta scripts, etc)
    prep_working_dir(template_dir, working_dir, pdb_fn, variant, wt_offset, overwrite_wd=True)

    # run the mutate and relax steps
    run_mutate_relax_steps(rosetta_main_dir, working_dir)

    # parse the output file into a single-record csv, appending info about variant
    # place in a staging directory and combine with other variants that run during this job
    sdf = parse_score_sc(vid, variant, basename(pdb_fn), join(working_dir, "score.sc"))
    sdf.to_csv(join(staging_dir, "{}_energies.csv".format(vid)))

    # if the flag is set, save all files in the working directory for this variant
    # these go directly to the output directory instead of the staging directory
    if save_wd:
        shutil.copytree(working_dir, join(output_dir, "wd"))

    # clean up the working dir in preparation for next variant
    shutil.rmtree(working_dir)

    run_time = time.time() - start
    print("Processing variant {} took {}".format(vid, run_time))
    return run_time


def main(args):

    # todo: figure out how to work this w/ condor
    rosetta_main_dir = "/home/sg/Desktop/rosetta/rosetta_bin_linux_2020.50.61505_bundle/main"

    # load the variants that will be processed on this server
    with open(args.variants_fn, "r") as f:
        ids_variants = f.readlines()

    # wild-type offset is needed since the pdb files are labeled from 1-num_residues, while the
    # datasets I have might be labeled from their start in a larger protein. hard-coded, for now
    if "pab1" in args.pdb_fn:
        wt_offset = 126
    else:
        wt_offset = 0

    # keep track of how long it takes to process variant
    run_times = []

    # loop through each variant, model it with rosetta, save results
    for id_variant in ids_variants:
        vid, variant = id_variant.split()
        run_time = run_single_variant(rosetta_main_dir, vid, variant, args.pdb_fn, wt_offset, args.save_raw)
        run_times.append(run_time)

    quit()

    # TODO: check if any of the variants failed to run... and if so, try to run them again here? or add to failed list?

    # create a final runtimes file for this run
    with open("./output/{}.runtimes".format(args.job_id), "w") as f:
        f.write("Avg runtime per variant: {:.3f}\n".format(np.average(run_times)))
        f.write("Std. dev.: {:.3f}\n".format(np.std(run_times)))
        for run_time in run_times:
            f.write("{:.3f}\n".format(run_time))

    # zip all the outputs and delete
    # TODO: combine outputs into a single csv file (can optionally save all the small output files as well)
    subprocess.call("tar -czf {}_output.tar.gz *".format(args.job_id), cwd="./output", shell=True)
    subprocess.call("find . ! -name '{}_output.tar.gz' -type f -exec rm -f {} +".format(args.job_id, "{}"), cwd="./output", shell=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("variants_fn",
                        help="the file containing the variants",
                        type=str)

    parser.add_argument("--job_id",
                        help="job id is used to save a diagnostic file",
                        type=str,
                        default="no_job_id")

    parser.add_argument("--pdb_fn",
                        help="path to pdb file",
                        type=str,
                        default="raw_pdb_files/ube4b_clean_0002.pdb")

    parser.add_argument("--save_raw",
                        help="set this to save the raw score.sc and energy.txt files in addition to the parsed ones",
                        action="store_true")

    main(parser.parse_args())
