""" prepare and package HTCondor runs """
import time
from os.path import join


def get_run_dir_name(run_name="noname"):
    dir_name_str = "condor_energize_{}_{}"
    return dir_name_str.format(time.strftime("%Y-%m-%d_%H-%M-%S"), run_name)


def main():

    run_name = "test_run"
    out_dir = join("output", "htcondor_runs", get_run_dir_name(run_name))

    variants_fn = "input_variants/gb1_test_variants.txt"

    # need to create an input variant file for each job based on the master list of input variants
    # need to substitute the number of jobs in energize.sub
    # need to substitute the github tag in run.sh
    # need to create output directories to collect output from each job
    # need to package all these files in a directory so I can submit the job with a one-liner
    # need to have an args.txt or similar so it is clear how the condor run was generated



    pass


if __name__ == "__main__":
    main()
