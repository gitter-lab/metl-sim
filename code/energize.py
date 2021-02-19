""" this is the run script that executes on the server """
# todo: rename this file to run_mutate.py or similar to differentiate from potential runs to prep PDB files

import argparse
import subprocess
import shutil
import os
from os.path import isdir, join

import numpy as np

from gen_rosetta_args import gen_rosetta_args
from parse_energies_txt import parse_multiple
from parse_score_sc import parse_score
import time


def prep_working_dir(template_dir, working_dir, pdb_fn, variant, wt_offset):
    """ prep the working directory by copying over files from the template directory, modifying as needed """

    # don't overwrite an existing working directory because not sure if there is currently a script using it
    # or if it is leftover from a failed run (it would be ok to delete in that case, but still)
    # get around this by specifying a different working directory for every variant, that way can avoid directory
    # collisions in the event of a crash and move on to the next variant
    if isdir(working_dir):
        raise IsADirectoryError("The working directory {} already exists. Please delete this directory or specify "
                                "a different working directory for this variant.")

    # create the directory
    os.mkdir(working_dir)

    # copy over PDB file into rosetta working dir and rename it to structure.pdb
    shutil.copyfile(pdb_fn, join(working_dir, "structure.pdb"))

    # generate the rosetta arguments (Rosetta scripts XML files and resfile) for this variant
    gen_rosetta_args(template_dir, variant, wt_offset, working_dir)

    # copy over files from the template dir that don't need to be changed
    files_to_copy = ["flags_mutate", "flags_relax"]
    for fn in files_to_copy:
        shutil.copy(join(template_dir, fn), working_dir)


def run_single_variant(vid, variant, pdb_fn, wt_offset, save_raw):
    start = time.time()

    print("Running variant {}: {}".format(vid, variant))

    # the directory in which rosetta will operate
    template_dir = "working_dir_template"
    working_dir = "working_dir"
    prep_working_dir(template_dir, working_dir, pdb_fn, variant, wt_offset)

    # run rosetta via energize.sh - make sure to block until complete
    process = subprocess.Popen("code/energize.sh", shell=True)
    process.wait()

    # TODO: place outputs in an output staging directory, from where I can combine multiple files / tar
    # parse the rosetta energy.txt into npy files and place in output directory
    parse_multiple("./working_dir_template/energy.txt", "./output/{}_".format(vid))
    # parse the score.sc and place into output dir
    parse_score("./working_dir_template/score.sc", "./output/{}_".format(vid))

    # if the flag is set, also copy over the raw score.sc and energy.txt files
    if save_raw:
        shutil.copyfile("./working_dir_template/energy.txt", "./output/{}_energy.txt".format(vid))
        shutil.copyfile("./working_dir_template/score.sc", "./output/{}_score.sc".format(vid))

    # clean up the rosetta working dir in preparation for next variant
    os.rmdir(working_dir)

    run_time = time.time() - start
    print("Processing variant {} took {}".format(vid, run_time))
    return run_time


def main(args):

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
        run_time = run_single_variant(vid, variant, args.pdb_fn, wt_offset, args.save_raw)
        run_times.append(run_time)

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
