""" prepare and package HTCondor runs """
import time
import os
from os.path import join
import argparse
import shutil
import subprocess


def get_run_dir_name(run_name="unnamed"):
    dir_name_str = "condor_energize_{}_{}"
    return dir_name_str.format(time.strftime("%Y-%m-%d_%H-%M-%S"), run_name)


def chunks(lst, n):
    """https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def gen_args(master_variant_fn, variants_per_job, out_dir, keep_sep_files=False):
    """generate arguments files from the master variant list"""
    # load the master list of variants
    with open(master_variant_fn, "r") as f:
        pdbs_variants = f.read().splitlines()

    # split the master variant list into separate args files
    split_variant_lists = list(chunks(pdbs_variants, variants_per_job))
    args_dir = join(out_dir, "args")
    os.makedirs(args_dir)
    for job_num, svl in enumerate(split_variant_lists):
        with open(join(args_dir, "{}.txt".format(job_num)), "w") as f:
            for line in svl:
                f.write("{}\n".format(line))

    # tar the argument files -- easier to transfer lots of arg files to/from condor servers
    tar_cmd = ["tar", "-C", out_dir, "-czf", join(out_dir, "args.tar.gz"), "args"]
    subprocess.call(tar_cmd)

    # delete the separate args files
    if not keep_sep_files:
        shutil.rmtree(args_dir)

    # return the number of args files (jobs)
    return len(split_variant_lists)


def fill_templates(github_tag, num_jobs, out_dir):

    # run.sh
    run_sh_template_fn = "htcondor/templates/run.sh"
    with open(run_sh_template_fn, "r") as f:
        run_sh_template_str = f.read()
        formatted_run_sh = run_sh_template_str.format(github_tag=github_tag)

    with open(join(out_dir, "run.sh", "w")) as f:
        f.write(formatted_run_sh)

    # energize.sub


def main(args):

    out_dir = join("output", "htcondor_runs", get_run_dir_name(args.run_name))
    os.makedirs(out_dir)

    # save the arguments for this condor run as run_def.txt in the log directory
    pass

    # generate arguments files from the master variant list. returns the number of jobs
    # could also use a different system based on the master list, and computing variants per job dynamically
    num_jobs = gen_args(args.master_variant_fn, args.variants_per_job, out_dir)

    # create an env_vars.txt file to define environment variables for run.sh and energize.sub
    with open(join(out_dir, "env_vars.txt"), "w") as f:
        f.write("GITHUB_TAG={}\n".format(args.github_tag))
        f.write("NUM_JOBS={}\n".format(num_jobs))

    # copy over energize.sub and run.sh
    shutil.copy("htcondor/templates/energize.sub", out_dir)
    shutil.copy("htcondor/templates/run.sh", out_dir)

    # copy over the energize args and rename to standard filename
    shutil.copyfile(args.energize_args_fn, join(out_dir, "energize_args.txt"))

    # create output directories where jobs will place their outputs
    os.makedirs(join(out_dir, "output/condor_logs"))
    os.makedirs(join(out_dir, "output/energize_outputs"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        fromfile_prefix_chars="@")

    parser.add_argument("--run_name",
                        help="name for this condor run, used for log directory",
                        type=str,
                        default="unnamed")

    parser.add_argument("--energize_args_fn",
                        type=str,
                        help="argparse params file for energize.py that will be used with all jobs")

    parser.add_argument("--master_variant_fn",
                        type=str,
                        help="file containing all variants for this run")

    parser.add_argument("--variants_per_job",
                        type=int,
                        help="the number of variants per job")

    parser.add_argument("--github_tag",
                        type=str,
                        help="github tag specifying which version of code to retrieve for this run")

    main(parser.parse_args())
