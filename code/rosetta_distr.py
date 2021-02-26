""" Copy and tar files from the rosetta distribution that are needed for rosettafy """

import argparse


def main(args):

    # rosettafy was designed to work with Rosetta 2020.50.61505

    to_copy = ["source/bin/relax.static.linuxgccrelease",
               "source/bin/rosetta_scripts.static.linuxgccrelease",
               "database",
               "source/src/apps/public/relax_w_allatom_cst/clean_pdb_keep_ligand.py",
               "source/src/apps/public/relax_w_allatom_cst/amino_acids.py"]

    # copy the scripts to the output directory but maintain the full paths


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
