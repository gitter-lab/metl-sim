""" Runs the GB1 docking pipeline but uses my Python-based framework from energize.py """

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

import energize
from templates import fill_templates
import time


def run_mutate_step(rosetta_scripts_bin_fn, database_path, working_dir):

    # the input structure is assumed to be "structure.pdb"
    # setting this up is handled in the prep_working_dir() function
    structure_fn = "structure.pdb"

    # note that options_mutate.txt specifies an output directory of "mutated_structures"
    mutate_cmd = [rosetta_scripts_bin_fn,
                  '-database', database_path,
                  "-in:file:s", structure_fn,
                  "-nstruct", "1",
                  "-out:file:scorefile", "mutate.sc",
                  "@options_mutate.txt",
                  ]

    mutate_out_fn = join(working_dir, "mutate.out")
    # to completely void output, can direct it to subprocess.DEVNULL instead of f
    with open(mutate_out_fn, "w") as f:
        return_code = subprocess.call(mutate_cmd, cwd=working_dir, stdout=f, stderr=f)
    if return_code != 0:
        raise energize.RosettaError("Mutate step did not execute successfully. Return code: {}".format(return_code))

    # Sameer copied output from this step into output directory, but we can just keep it
    # where it is because our script has the option to save the whole working directory if requested
    # to avoid conflicts with "score.sc" file, we specifically specify mutate.sc in the command above
    # shutil.copyfile("mutated_structures/structure_0001.pdb", "output/variant_relaxed.pdb")
    # shutil.copyfile("mutated_structures/mutate.sc", "output/variant_relaxed_score.sc")


def run_docking_step(rosetta_scripts_bin_fn: str,
                     database_path: str,
                     num_structs: int,
                     working_dir: str,
                     variant_has_mutations: bool = True):

    in_structure_fn = "mutated_structures/structure_0001.pdb"

    if variant_has_mutations:
        dock_cmd = [rosetta_scripts_bin_fn,
                    "-database", database_path,
                    "-in:file:s", in_structure_fn,
                    "-docking:partners A_C",
                    "-use_input_sc",
                    "-ex1",
                    "-ex2",
                    "-out:path:all", "docked_structures",
                    "-out:file:scorefile", "docked_score.sc",
                    "-out:overwrite",
                    "-score:weights", "ref2015.wts",
                    "-parser:protocol", "docking_minimize_fast.xml",
                    '-nstruct', str(num_structs)]
    else:
        # not 100% sure if sameer's docking script requires different args for WT
        # either way, WT is not supported for docking at the moment...
        raise NotImplementedError("This function doesn't support the WT yet")

    dock_out_fn = join(working_dir, "dock.out")
    with open(dock_out_fn, "w") as f:
        return_code = subprocess.call(dock_cmd, cwd=working_dir, stdout=f, stderr=f)
    if return_code != 0:
        raise energize.RosettaError("Docking step did not execute successfully. Return code: {}".format(return_code))


def run_docking_pipeline(rosetta_main_dir: str,
                         working_dir: str,
                         num_structs: int,
                         variant_has_mutations: bool = True):

    # keep track of how long it takes to run Rosetta
    all_start = time.time()

    # get the paths to the rosetta binaries and database
    relax_bin_fn, rosetta_scripts_bin_fn, score_jd2_bin_fn, database_path = energize.get_rosetta_paths(rosetta_main_dir)

    # run the mutate step
    if variant_has_mutations:
        mt_start_time = time.time()
        run_mutate_step(rosetta_scripts_bin_fn, database_path, working_dir)
        mt_run_time = time.time() - mt_start_time
    else:
        raise NotImplementedError("This function doesn't support the WT yet")

    # run docking step
    dock_start_time = time.time()
    run_docking_step(rosetta_scripts_bin_fn, database_path, num_structs, working_dir, variant_has_mutations)
    dock_run_time = time.time() - dock_start_time

    # keep track of how long it takes to run all steps
    all_run_time = time.time() - all_start

    # can keep track of run times for different steps... but we just have 1 step here
    run_times = {
        "mutate": mt_run_time,
        "dock": dock_run_time,
        "all": all_run_time,
    }
    return run_times


def gen_mutate_xml(variant, chain, working_dir):

    template_fn = "templates/docking_wd_template/mutate_template.xml"

    aa_map = {
        "A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE", "G": "GLY",
        "H": "HIS", "I": "ILE", "K": "LYS", "L": "LEU", "M": "MET", "N": "ASN",
        "P": "PRO", "Q": "GLN", "R": "ARG", "S": "SER", "T": "THR", "V": "VAL",
        "W": "TRP", "Y": "TYR"
    }

    variants = variant.split(',')
    idxs = []
    mutate_residue_blocks = []
    mutate_residue_movers = []
    protocols = []

    for i, v in enumerate(variants, 1):
        if len(v) < 3:
            raise ValueError(f"ERROR: length(variant) < 3 : {v}")
        parent_aa, residue_idx, new_aa = v[0], v[1:-1], v[-1]

        idxs.append(residue_idx + chain)
        mutate_residue_blocks.append(
            f'<MutateResidue name="mutant{i}" target="{residue_idx}{chain}" new_res="{aa_map[new_aa]}"/>')
        mutate_residue_movers.append(f'<Add mover_name="mutant{i}"/>')
        protocols.append(f'<Add mover_name="mutant{i}"/>')

    with open(template_fn, 'r') as template_file:
        template = template_file.read()

    filled_template = template.format(
        joined_idxs=",".join(idxs),
        mutate_residue_placeholders="\n".join(mutate_residue_blocks),
        mutate_residue_movers="\n".join(mutate_residue_movers),
        protocols_placeholders="\n".join(protocols)
    )

    with open(join(working_dir, "mutate.xml"), "w") as f:
        f.write(filled_template)


def prep_working_dir(template_dir, working_dir, pdb_fn, chain, variant, overwrite_wd=False):
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

    # create additional subdirectories for intermediate outputs
    os.makedirs(join(working_dir, "mutated_structures"))  # for output of rosetta scripts
    os.makedirs(join(working_dir, "relaxed_structures"))  # for Rosetta relax output
    os.makedirs(join(working_dir, "docked_structures"))  # for Rosetta relax output

    # this output directory is not the actual output directory for the job
    # this is what Sameer used for his outputs but I may code it out
    # todo: potentially remove
    os.makedirs(join(working_dir, "output"))

    # copy over PDB file into rosetta working dir and rename it to structure.pdb
    shutil.copyfile(pdb_fn, join(working_dir, "structure.pdb"))

    # copy over files from the template dir that don't need to be changed
    files_to_copy = ["docking_minimize.xml", "docking_minimize_fast.xml",
                     "options_dock.txt", "options_mutate.txt", "protein_dock_fast.sh"]

    for fn in files_to_copy:
        shutil.copy(join(template_dir, fn), working_dir)

    # create the mutate.xml file
    gen_mutate_xml(variant, chain, working_dir)


def run_single_variant(rosetta_main_dir: str,
                       pdb_fn: str,
                       chain: str,
                       variant: str,
                       rosetta_hparams: dict,
                       working_dir: str,
                       staging_dir: str,
                       output_dir: str,
                       save_wd: bool = False):

    start_time = time.time()

    template_dir = "templates/docking_wd_template"

    # set up the working directory (copies the pdb file, sets up the rosetta scripts, etc.)
    prep_working_dir(template_dir,
                     working_dir,
                     pdb_fn,
                     chain,
                     variant,
                     overwrite_wd=True)

    # run the mutate and relax steps
    variant_has_mutations = False if variant == "_wt" else True

    run_times = run_docking_pipeline(rosetta_main_dir,
                                     working_dir,
                                     rosetta_hparams["num_structs"],
                                     variant_has_mutations)

    # # copy over or parse any files we want to keep from the working directory to the output directory
    # # the stdout and stderr outputs from rosetta are in the working directory under mutate.out and relax.out
    # # however, we don't need them, so we are going to leave them there and just parse the energies
    #
    # # parse the output files into a single-record csv, appending info about variant
    # # place in a staging directory and combine with other variants that run during this job
    # score_df = parse_score_sc(join(working_dir, "relax.sc"))
    # filter_df = parse_score_sc(join(working_dir, "filter.sc"))
    # centroid_df = parse_score_sc(join(working_dir, "centroid.sc"))
    #
    # # the total_score from filter and centroid probably won't be used, but let's keep them in just in case
    # # just need to resolve the name conflict with the total_score from score_df
    # filter_df.rename(columns={"total_score": "filter_total_score"}, inplace=True)
    # centroid_df.rename(columns={"total_score": "centroid_total_score"}, inplace=True)
    #
    # full_df = pd.concat((score_df, filter_df, centroid_df), axis=1)
    #
    # # append info about this variant
    # full_df.insert(0, "pdb_fn", [basename(pdb_fn)])
    # full_df.insert(1, "variant", [variant])
    # full_df.insert(2, "start_time", [time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_time))])
    # full_df.insert(3, "run_time", [int(run_times["all"])])
    # full_df.insert(4, "mutate_run_time", [int(run_times["mutate"])])
    # full_df.insert(5, "relax_run_time", [int(run_times["relax"])])
    # full_df.insert(6, "filter_run_time", [int(run_times["filter"])])
    # full_df.insert(7, "centroid_run_time", [int(run_times["centroid"])])
    #
    # # note: it's not the best practice to have filenames with periods and commas
    # #   could pass in the loop ID for this single variant and use that to save the file
    # full_df.to_csv(join(staging_dir, "{}_{}_energies.csv".format(basename(pdb_fn), variant)), index=False)

    # if the flag is set, save all files in the working directory for this variant
    # these go directly to the output directory instead of the staging directory
    if save_wd:
        shutil.copytree(working_dir, join(output_dir, "wd_{}_{}".format(basename(pdb_fn), variant)))

    # clean up the working dir in preparation for next variant
    shutil.rmtree(working_dir)

    return run_times["all"]


def main(args):

    # rough script start time for logging
    # this will be logged in UTC time (GM time) in the log directory name and output files
    script_start = time.time()

    # generate a unique identifier for this run
    job_uuid = shortuuid.encode(uuid.uuid4())[:12]

    # create the log directory for this job
    log_dir = join(args.log_dir_base, energize.get_log_dir_name(args, job_uuid, script_start))
    os.makedirs(log_dir)

    # save the argparse arguments back out to a file
    energize.save_argparse_args(vars(args), join(log_dir, "args.txt"))

    # save job info
    energize.save_job_info(script_start, job_uuid, args.cluster, args.process, args.commit_id, log_dir)

    # create a dictionary of just rosetta hyperparameters that can be passed around throughout functions and saved
    rosetta_hparams = {"num_structs": args.num_structs}
    energize.save_csv_from_dict(join(log_dir, "hparams.csv"), rosetta_hparams)

    # load the variants that will be processed with this run
    # this file contains a line for each variant
    # and each line contains the pdb file and the comma-delimited substitutions (e.g. "2qmt_p.pdb A23P,R67L")
    with open(args.variants_fn, "r") as f:
        pdbs_variants = f.read().splitlines()

    # set up the staging dir....
    staging_dir = join(log_dir, "staging")
    os.makedirs(staging_dir, exist_ok=True)

    # define the working directory constant
    working_dir = "docking_wd"

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
                run_time = run_single_variant(args.rosetta_main_dir,
                                              pdb_fn,
                                              args.chain,
                                              variant,
                                              rosetta_hparams,
                                              working_dir,
                                              staging_dir,
                                              log_dir, args.save_wd)
                print("Processing variant {} {} took {:.2f}".format(basename(pdb_fn), variant, run_time), flush=True)

            except (energize.RosettaError, FileNotFoundError) as e:
                print(e, flush=True)
                print("Encountered error running variant {} {}. "
                      "Attempts remaining: {}".format(pdb_basename, variant, num_attempts_per_variant - attempt - 1),
                      flush=True)

                # if we are supposed to save the working directory, save it now
                # the run_single_variant() function doesn't take care of this when there's an exception
                # todo: if we end up using variant-specific working dir, update here
                if args.save_wd:
                    shutil.copytree(working_dir,
                                    join(log_dir, "wd_{}_{}_{}".format(basename(pdb_fn), variant, attempt)))

                # clean up the working dir in preparation for next variant
                shutil.rmtree(working_dir)
            else:
                # successful variant run, so break out of the attempt loop
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

    # # if any variants were successful, concat the outputs into a final energies.csv
    # if len(failed) < len(pdbs_variants):
    #     # combine outputs in the staging directory into a single csv file
    #     cdf = combine_outputs(join(log_dir, "staging"))
    #     # add additional column for job uuid
    #     cdf.insert(2, "job_uuid", job_uuid)
    #     # save in the main log directory
    #     cdf.to_csv(join(log_dir, "energies.csv"), index=False)
    #
    # # compress outputs, delete the output staging directory, etc
    # shutil.rmtree(join(log_dir, "staging"))
    #
    # if (len(failed) / len(pdbs_variants)) > args.allowable_failure_fraction:
    #     # too many variants failed in this job. exit with failure code.
    #     # todo: this exit code will put the job on hold, but the log directory will still be present with
    #     #  energies.csv, causing there to be duplicates for the variants that succeeded in this run and the
    #     #  variants that get run in the new run. one option is to just not save energies.csv when too many variants
    #     #  fail. the job will get rescheduled anyway and the variants will run on a new machine.
    #     #  but if we're going to run again, might as well keep the duplicate variants anyway? they get filtered out
    #     #  later...
    #     sys.exit(1)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        fromfile_prefix_chars="@")

    # main input files
    parser.add_argument("--rosetta_main_dir",
                        help="path to the main directory of the rosetta distribution",
                        type=str,
                        default="rosetta_minimal")

    parser.add_argument("--variants_fn",
                        help="path to text file containing protein variants",
                        type=str)

    # todo: change to specifying the chain in the variants_fn file to support different chains in a single run
    parser.add_argument("--chain",
                        help="the chain to use from the pdb file",
                        type=str,
                        default="A")

    parser.add_argument("--pdb_dir",
                        help="directory containing the pdb files referenced in variants_fn",
                        type=str,
                        default="pdb_files/prepared_pdb_files")

    parser.add_argument("--allowable_failure_fraction",
                        help="fraction of variants that can fail but still consider this job successful",
                        type=float,
                        default=0.25)

    # rosetta hyperparameters
    parser.add_argument("--num_structs",
                        help="number of structures",
                        type=int,
                        default=1)

    # logging and output options
    parser.add_argument("--save_wd",
                        help="set this flag to save the full working directory for each variant",
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
