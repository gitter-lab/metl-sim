""" Copy and tar files from the rosetta distribution that are needed for rosettafy """

import argparse


def main(args):

    to_copy = ["source/bin/relax.static.linuxgccrelease",
               "source/bin/rosetta_scripts.static.linuxgccrelease"]
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--rosetta_main_dir",
                        help="The main directory of the full rosetta distribution containing the binaries and "
                             "other files that are needed for this script",
                        type=str,
                        default="/home/sg/Desktop/rosetta/rosetta_bin_linux_2020.50.61505_bundle/main")

    main(parser.parse_args())
