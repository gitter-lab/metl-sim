""" prepare and package HTCondor runs """
import time
import os
from os.path import join
import argparse
import shutil
import subprocess
import urllib3


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


def save_argparse_args(args_dict, out_fn):
    """ save argparse arguments out to a file """
    with open(out_fn, "w") as f:
        for k, v in args_dict.items():
            # if a flag is set to false, dont include it in the argument file
            if (not isinstance(v, bool)) or (isinstance(v, bool) and v):
                f.write("--{}\n".format(k))
                # if a flag is true, no need to specify the "true" value
                if not isinstance(v, bool):
                    f.write("{}\n".format(v))


def fetch_repo(github_tag, github_token, out_dir):
    """ fetches the codebase from Github """
    # https://stackoverflow.com/questions/17285464/whats-the-best-way-to-download-file-using-urllib3
    # https://stackoverflow.com/questions/27387783/how-to-download-a-file-with-urllib3

    url = "https://github.com/samgelman/rosettafy/archive/{}.tar.gz".format(github_tag)

    http = urllib3.PoolManager()
    # todo: when repo is public, authorization token will no longer be needed
    response = http.request("GET", url, preload_content=False, headers={"Authorization": "token {}".format(github_token)})

    # save_fn = join(out_dir, "{}.tar.gz".format(github_tag))
    # use static output filename to make transfer/unzipping easier (less need to fill in github_tag everywhere)
    save_fn = join(out_dir, "code.tar.gz")

    with open(save_fn, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

    # unclear whether this is needed or not, can't hurt though
    response.release_conn()
    response.close()


def main(args):

    out_dir = join("output", "htcondor_runs", get_run_dir_name(args.run_name))
    os.makedirs(out_dir)

    # save the arguments for this condor run as run_def.txt in the log directory
    # remove the github authorization token to avoid storing it in a file
    args_dict = dict(vars(args))
    del args_dict["github_token"]
    save_argparse_args(vars(args), join(out_dir, "run_def.txt"))

    # download the repository
    fetch_repo(args.github_tag, args.github_token, out_dir)

    # generate arguments files from the master variant list. returns the number of jobs
    # could also use a different system based on the master list, and computing variants per job dynamically
    num_jobs = gen_args(args.master_variant_fn, args.variants_per_job, out_dir)

    # create an env_vars.txt file to define environment variables for run.sh and energize.sub
    with open(join(out_dir, "env_vars.txt"), "w") as f:
        f.write("export GITHUB_TAG={}\n".format(args.github_tag))
        f.write("export NUM_JOBS={}\n".format(num_jobs))

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

    parser.add_argument("--github_token",
                        type=str,
                        help="authorization token for private rosettafy repository")

    main(parser.parse_args())
