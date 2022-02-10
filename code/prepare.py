""" Prepare raw PDB files for use with Rosetta """

import argparse
import os
import stat
from os.path import join, isdir, basename, abspath
import shutil
import subprocess
import platform
import time

import pandas as pd

from utils import save_argparse_args


def prep_working_dir(template_dir, working_dir, pdb_fn, overwrite_wd=False):
    """ prep the working directory by copying over files from the template directory"""

    # delete the current working directory if one exists
    if overwrite_wd:
        try:
            shutil.rmtree(working_dir)
        except FileNotFoundError:
            pass

    # copy over the full template directory as there are no files that need to be modified if it exists
    try:
        shutil.copytree(template_dir, working_dir)
    except FileExistsError:
        print("The working directory '{}' already exists. Please delete this directory or specify "
              "a different working directory.".format(working_dir))
        raise

    # copy over PDB file into and rename it structure.pdb
    shutil.copyfile(pdb_fn, join(working_dir, "structure.pdb"))


# def make_executable(fn):
#     st = os.stat(fn)
#     os.chmod(fn, st.st_mode | stat.S_IEXEC)


def clean_pdb_wrapper(keep_ligand, rosetta_main_dir, working_dir, chain):
    """ run Rosetta's clean_pdb_keep_ligand.py script. assumes there is a structure.pdb file in the working_dir """

    if keep_ligand:
        cleaned_fn = run_clean_pdb_keep_ligand(rosetta_main_dir, working_dir)
    else:
        cleaned_fn = run_clean_pdb(rosetta_main_dir, working_dir, chain)

    return cleaned_fn


def run_clean_pdb(rosetta_main_dir, working_dir, chain):
    clean_pdb_script_fn = abspath(join(rosetta_main_dir, "tools/protein_tools/scripts/clean_pdb.py"))
    clean_pdb_cmd = ['conda', 'run', '-n', 'clean_pdb', clean_pdb_script_fn, 'structure.pdb', chain]

    # run the clean pdb script
    clean_out_fn = join(working_dir, "clean_pdb.out")
    with open(clean_out_fn, "w") as f:
        return_code = subprocess.call(clean_pdb_cmd, cwd=working_dir, stdout=f, stderr=f)
    if return_code != 0:
        raise RuntimeError("Clean PDB did not execute successfully, return code: {}".format(return_code))

    # this script saves the output file in the same directory as the input file
    cleaned_pdb_fn = "structure_{}.pdb".format(chain)

    # rename the cleaned pdb to structure_cleaned.pdb
    # os.rename(join(working_dir, cleaned_pdb_fn), join(working_dir, "structure_cleaned.pdb"))

    return cleaned_pdb_fn


def run_clean_pdb_keep_ligand(rosetta_main_dir, working_dir):
    clean_pdb_keep_ligand_fn = "source/src/apps/public/relax_w_allatom_cst/clean_pdb_keep_ligand.py"
    clean_pdb_script_fn = abspath(join(rosetta_main_dir, clean_pdb_keep_ligand_fn))
    clean_pdb_cmd = ['conda', 'run', '-n', 'clean_pdb', clean_pdb_script_fn, 'structure.pdb', '-ignorechain']

    # run the clean pdb script
    clean_out_fn = join(working_dir, "clean_pdb.out")
    with open(clean_out_fn, "w") as f:
        return_code = subprocess.call(clean_pdb_cmd, cwd=working_dir, stdout=f, stderr=f)
    if return_code != 0:
        raise RuntimeError("Clean PDB did not execute successfully, return code: {}".format(return_code))

    # this script saves the output file in the same directory as the input file
    # the output filename is just the input filename with _00.pdb appended
    cleaned_pdb_fn = "structure.pdb_00.pdb"

    # rename the cleaned pdb to structure_cleaned.pdb
    # os.rename(join(working_dir, cleaned_pdb_fn), join(working_dir, "structure_cleaned.pdb"))

    return cleaned_pdb_fn


def run_relax(rosetta_main_dir, working_dir, cleaned_pdb_fn, nstruct=1):
    """ run relax to prep the cleaned pdb for further use with Rosetta (as recommended by Rosetta docs) """

    if platform.system() == "Linux":
        relax_bin_fn = "relax.static.linuxgccrelease"
    elif platform.system() == "Darwin":
        relax_bin_fn = "relax.static.macosclangrelease"
    else:
        raise ValueError("unsupported platform: {}".format(platform.system()))

    relax_bin_fn = abspath(join(rosetta_main_dir, "source", "bin", relax_bin_fn))

    # path to the rosetta database
    database_path = abspath(join(rosetta_main_dir, "database"))

    relax_cmd = [relax_bin_fn, '-database', database_path, '-s', cleaned_pdb_fn,
                 '-nstruct', str(nstruct), '@flags_prepare_relax']
    relax_out_fn = join(working_dir, "relax.out")
    with open(relax_out_fn, "w") as f:
        subprocess.call(relax_cmd, cwd=working_dir, stdout=f, stderr=f)


def parse_scores(working_dir):
    """ get the filename of the lowest energy structure generated in the relax step """
    scores_fn = join(working_dir, "score.sc")

    # load the scores.sc file into a pandas dataframe
    df = pd.read_csv(scores_fn, delim_whitespace=True, skiprows=1)

    # get all structures with lowest energy (there may be multiple structures with same lowest energy)
    lowest_energy_df = df[df.total_score == df.total_score.min()]
    print("Found {} structures with lowest energy ({}).".format(len(lowest_energy_df),
                                                                lowest_energy_df.iloc[0]["total_score"]), flush=True)

    # return the *first* structure with the lowest energy
    return join(working_dir, lowest_energy_df.iloc[0]["description"] + ".pdb")


def get_output_dir(original_pdb_fn, out_dir_base):
    # time zone is UTC (coordinated universal time)
    output_dir = "{}_{}".format(basename(original_pdb_fn)[:-4],
                                time.strftime("%Y-%m-%d_%H-%M-%S", time.gmtime(time.time())))

    return join(out_dir_base, output_dir)


def main(args):

    output_dir = get_output_dir(args.pdb_fn, args.out_dir_base)
    os.makedirs(output_dir)
    print("output directory is: {}".format(output_dir), flush=True)

    template_dir = "templates/prepare_wd_template"
    working_dir = join(output_dir, "working_dir")

    # set up the working directory
    # this also copies over the PDB and renames it structure.pdb for consistency
    prep_working_dir(template_dir, working_dir, args.pdb_fn, overwrite_wd=True)

    # save the args to the working directory (which will be saved to the output dir)
    args_dict = dict(vars(args))
    save_argparse_args(args_dict, join(output_dir, "args.txt"))

    # run the clean_pdb script
    cleaned_pdb_fn = clean_pdb_wrapper(args.keep_ligand, args.rosetta_main_dir, working_dir, args.chain)

    # relax with all-heavy-atom constraints
    if args.relax_nstruct > 0:
        run_relax(args.rosetta_main_dir, working_dir, cleaned_pdb_fn, nstruct=args.relax_nstruct)

        # get the filename of the lowest scoring structure
        lowest_energy_pdb_fn = parse_scores(working_dir)

        # copy over the lowest energy PDB and rename it to match input filename
        shutil.copyfile(lowest_energy_pdb_fn, join(output_dir, "{}_p.pdb".format(basename(args.pdb_fn)[:-4])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--rosetta_main_dir",
                        help="The main directory of the rosetta distribution containing the binaries and "
                             "other files that are needed for this script (does not have to be full distribution)",
                        type=str,
                        default="rosetta_minimal")

    parser.add_argument("--pdb_fn",
                        help="the PDB file to prepare",
                        type=str)

    parser.add_argument("--keep_ligand",
                        help="whether to run clean_pdb.py or clean_pdb_keep_ligand.py",
                        action="store_true",
                        default=False)

    parser.add_argument("--chain",
                        help="if using clean_pdb with keep_ligand==False, specify which chain to grab from "
                             "the raw PDB. ignorechain will grab all the chain",
                        type=str, default="ignorechain")

    parser.add_argument("--relax_nstruct",
                        help="number of structures (restarts) in the relax step",
                        type=int,
                        default=10)

    parser.add_argument("--out_dir_base",
                        help="base output directory",
                        type=str,
                        default="output/prepare_outputs")

    main(parser.parse_args())

