""" Prepare raw PDB files for use with Rosetta """

import argparse
import os
import stat
from os.path import join, isdir, basename
import shutil
import subprocess

import pandas as pd


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
    except FileExistsError as e:
        print("The working directory '{}' already exists. Please delete this directory or specify "
              "a different working directory.".format(working_dir))
        raise

    # copy over PDB file into and rename it structure.pdb
    shutil.copyfile(pdb_fn, join(working_dir, "structure.pdb"))


def make_executable(fn):
    st = os.stat(fn)
    os.chmod(fn, st.st_mode | stat.S_IEXEC)


def run_clean_pdb(rosetta_main_dir, working_dir):
    """ run Rosetta's clean_pdb_keep_ligand.py script. assumes there is a structure.pdb file in the working_dir """
    clean_pdb_script_fn = join(rosetta_main_dir, "source/src/apps/public/relax_w_allatom_cst/clean_pdb_keep_ligand.py")

    # make sure the clean pdb python script is executable
    make_executable(clean_pdb_script_fn)

    # run the clean pdb script
    clean_pdb_cmd = ['conda', 'run', '-n', 'clean_pdb', clean_pdb_script_fn, 'structure.pdb', '-ignorechain']
    subprocess.call(clean_pdb_cmd, cwd=working_dir)

    # this script saves the output file in the same directory as the input file
    # the output filename is just the input filename with _00.pdb appended
    cleaned_pdb_fn = "structure.pdb_00.pdb"

    return cleaned_pdb_fn


def run_relax(rosetta_main_dir, working_dir, cleaned_pdb_fn, nstruct=1):
    """ run relax to prep the cleaned pdb for further use with Rosetta (as recommended by Rosetta docs) """
    relax_bin_fn = join(rosetta_main_dir, "source/bin/relax.static.linuxgccrelease")
    relax_cmd = [relax_bin_fn, '-s', cleaned_pdb_fn, '-nstruct', str(nstruct), '@flags_prepare_relax']
    subprocess.call(relax_cmd, cwd=working_dir)


def parse_scores(working_dir):
    """ get the filename of the lowest energy structure generated in the relax step """
    scores_fn = join(working_dir, "score.sc")

    # load the scores.sc file into a pandas dataframe
    df = pd.read_csv(scores_fn, delim_whitespace=True, skiprows=1)

    # get all structures with lowest energy (there may be multiple structures with same lowest energy)
    lowest_energy_df = df[df.total_score == df.total_score.min()]
    print("Found {} structures with lowest energy ({}).".format(len(lowest_energy_df),
                                                                lowest_energy_df.iloc[0]["total_score"]))

    # return the *first* structure with the lowest energy
    return join(working_dir, lowest_energy_df.iloc[0]["description"] + ".pdb")


def transfer_outputs(working_dir, lowest_energy_pdb_fn, original_pdb_fn):
    # generate the outputs containing the renamed lowest energy pdb and intermediate files
    # grab the first available output directory (increment integer to avoid overwriting a previous run)
    # assuming we won't have more than 100 runs... plus this is going to be different on condor anyway
    for i in range(1, 101):
        output_dir = "output/prepare_outputs/{}_{}".format(basename(original_pdb_fn)[:-4], i)
        if not isdir(output_dir):
            break

    os.makedirs(output_dir)

    # copy over the lowest energy PDB and rename it to match input filename
    shutil.copyfile(lowest_energy_pdb_fn, join(output_dir, "{}_prepared.pdb".format(basename(original_pdb_fn)[:-4])))

    # copy over other intermediate files (found it's just easier to copy over the whole working directory)
    # these can be compressed or deleted if filesize is a concern
    shutil.copytree(working_dir, join(output_dir, "intermediate_files"))


def main(args):

    # todo: this could be defined as a global constant and changed depending where the script is run
    #   actually, if this is running on condor, need to figure out specifically which folders/binaries are needed
    #   and reference only those
    rosetta_main_dir = "/home/sg/Desktop/rosetta/rosetta_bin_linux_2020.50.61505_bundle/main"

    template_dir = "prepare_wd_template"
    working_dir = "prepare_wd"

    # set up the working directory
    # this also copies over the PDB and renames it structure.pdb for consistency
    prep_working_dir(template_dir, working_dir, args.pdb_fn, overwrite_wd=True)

    # run the clean_pdb script
    cleaned_pdb_fn = run_clean_pdb(rosetta_main_dir, working_dir)

    # relax with all-heavy-atom constraints
    run_relax(rosetta_main_dir, working_dir, cleaned_pdb_fn, nstruct=10)

    # get the filename of the lowest scoring structure
    lowest_energy_pdb_fn = parse_scores(working_dir)

    # generate the outputs containing the renamed lowest energy pdb and intermediate files
    transfer_outputs(working_dir, lowest_energy_pdb_fn, args.pdb_fn)

    # delete the working directory
    shutil.rmtree(working_dir)


if __name__ == "__main__":
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)

        parser.add_argument("pdb_fn",
                            help="the PDB file to prepare",
                            type=str)

        main(parser.parse_args())

