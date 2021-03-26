""" Copy and tar files from the rosetta distribution that are needed for rosettafy """

import argparse
import os
from os.path import join, isfile, isdir, basename, dirname, exists
import errno
import shutil
import stat
import subprocess


def prep_for_squid(rosetta_minimal_dir, squid_dir):
    """ prepares the distribution for SQUID by compressing and splitting it """
    # could probably do this in pure python using tarfile package and
    # https://stackoverflow.com/questions/45250329/split-equivalent-of-gzip-files-in-python
    # however, just going to do it with linux utilities for simplicity right now

    # create output directory
    # crash if output directory already exists -- don't overwrite
    os.makedirs(squid_dir, exist_ok=False)

    # compress the rosetta minimal distribution
    tar_fn = join(squid_dir, "rosetta_minimal.tar.gz")
    tar_cmd = ["tar", "-czvf", tar_fn, rosetta_minimal_dir]
    subprocess.call(tar_cmd)

    # split into files less than 1gb (let's go with 700mb just because)
    # note: this might not work on windows or mac
    split_cmd = ["split", "-b", "500m", tar_fn, tar_fn + "."]
    subprocess.call(split_cmd)


def make_executable(fn):
    st = os.stat(fn)
    os.chmod(fn, st.st_mode | stat.S_IEXEC)


def gen_minimal_distr(rosetta_main_dir, out_dir):
    """ generates a minimal distribution of just what is needed for rosettafy """
    # rosettafy was designed to work with Rosetta 2020.50.61505
    # note the relax/scripts binary paths are symlinks, which is okay, because shutil.copyfile follows them
    # (path, executable) -- note the "executable" is ignored for directories (can't make a dir executable)
    to_copy = [("source/bin/relax.static.linuxgccrelease", True),
               ("source/bin/rosetta_scripts.static.linuxgccrelease", True),
               ("source/bin/score_jd2.static.linuxgccrelease", True),
               ("database", None),
               ("source/src/apps/public/relax_w_allatom_cst/clean_pdb_keep_ligand.py", True),
               ("source/src/apps/public/relax_w_allatom_cst/amino_acids.py", True)]

    # create the output directory if it doesn't already exist
    # throw an error if it does exist (want a clean start -- user should delete the dir)
    try:
        os.makedirs(out_dir)
    except FileExistsError:
        print("Output directory already exists, please delete before continuing: {}".format(out_dir))
        raise

    # copy the scripts to the output directory but maintain the full paths
    for (fn, executable) in to_copy:
        print("Copying {}".format(fn))

        # recreate the directory structure from the source dir inside the our output dir
        dir_struct = dirname(fn)
        full_out_dir = join(out_dir, dir_struct)
        try:
            os.makedirs(full_out_dir, exist_ok=True)
        except FileNotFoundError:
            # the directory structure is the root directory (""), happens when copying the database
            # no action needed
            pass

        # check if our source file or directory exists
        full_source_fn = join(rosetta_main_dir, fn)
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
            if executable:
                make_executable(join(full_out_dir, basename(fn)))
        else:
            raise RuntimeError("Somehow, the path exists but is not a file nor a directory: {}".format(full_source_fn))


def main(args):
    gen_minimal_distr(args.rosetta_main_dir, args.out_dir)

    if args.prep_for_squid:
        prep_for_squid(args.out_dir, args.squid_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--rosetta_main_dir",
                        help="the main directory of the full rosetta distribution containing the binaries and "
                             "other files that are needed for this script",
                        type=str,
                        default="/home/sg/Desktop/rosetta/rosetta_bin_linux_2020.50.61505_bundle/main")

    parser.add_argument("--out_dir",
                        help="the output directory where to place the minimal rosetta binaries and scripts",
                        type=str,
                        default="rosetta_minimal")

    parser.add_argument("--prep_for_squid",
                        help="set this to also create a compressed and split version for squid",
                        action="store_true")

    parser.add_argument("--squid_dir",
                        help="the output directory where to place the compressed and split version for squid",
                        type=str,
                        default="output/squid_rosetta")

    main(parser.parse_args())
