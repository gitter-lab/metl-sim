""" Copy and tar files from the rosetta distribution that are needed for rosettafy """

import argparse
import os
from os.path import join, isfile, isdir, basename, dirname, exists
import errno
import shutil


def main(args):

    # rosettafy was designed to work with Rosetta 2020.50.61505
    to_copy = ["source/bin/relax.static.linuxgccrelease",
               "source/bin/rosetta_scripts.static.linuxgccrelease",
               "database",
               "source/src/apps/public/relax_w_allatom_cst/clean_pdb_keep_ligand.py",
               "source/src/apps/public/relax_w_allatom_cst/amino_acids.py"]

    # create the output directory if it doesn't already exist
    # throw an error if it does exist (want a clean start -- user should delete the dir)
    try:
        os.makedirs(args.out_dir)
    except FileExistsError:
        print("Output directory already exists, please delete before continuing: {}".format(args.out_dir))
        raise

    # copy the scripts to the output directory but maintain the full paths
    for fn in to_copy:
        print("Copying {}".format(fn))

        # recreate the directory structure from the source dir inside the our output dir
        dir_struct = dirname(fn)
        full_out_dir = join(args.out_dir, dir_struct)
        try:
            os.makedirs(full_out_dir, exist_ok=True)
        except FileNotFoundError:
            # the directory structure is the root directory (""), happens when copying the database
            # no action needed
            pass

        # check if our source file or directory exists
        full_source_fn = join(args.rosetta_main_dir, fn)
        if not exists(full_source_fn):
            print("The source file does not exist: {}".format(full_source_fn))
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), full_source_fn)

        # copy the file or directory from the main rosetta dir to the newly created directory
        if isdir(full_source_fn):
            full_out_dir_with_dest_folder = join(full_out_dir, fn)
            os.makedirs(full_out_dir_with_dest_folder, exist_ok=True)
            shutil.copytree(full_source_fn, full_out_dir_with_dest_folder, dirs_exist_ok=True)
        elif isfile(full_source_fn):
            shutil.copy(full_source_fn, full_out_dir)
        else:
            raise RuntimeError("Somehow, the path exists but is not a file nor a directory: {}".format(full_source_fn))

        # todo: make file executable


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--rosetta_main_dir",
                        help="The main directory of the full rosetta distribution containing the binaries and "
                             "other files that are needed for this script",
                        type=str,
                        default="/home/sg/Desktop/rosetta/rosetta_bin_linux_2020.50.61505_bundle/main")

    parser.add_argument("--out_dir",
                        help="The output directory where to place the minimum rosetta binaries and scripts",
                        type=str,
                        default="rosetta_distribution")

    main(parser.parse_args())
