""" prepare and package HTCondor runs """
import itertools
import math
import time
import os
from os.path import join
import argparse
import shutil
import subprocess
import urllib3
# todo: tqdm is only on the local environment, not on condor environment
#  shouldn't be a problem since this file isn't run during a condor run... but maybe specify separate env files for each
from tqdm import tqdm

from utils import save_argparse_args, get_seq_from_pdb

# todo: find a better way to handle reading PDBs with Rosetta's pose_energy_table at the end
#   or remove the pose energy table from all the PDBs
import warnings
warnings.filterwarnings("ignore", message="Ignoring unrecognized record ")
warnings.filterwarnings("ignore", message="'HEADER' line not found; can't determine PDB ID.")


def get_run_dir_name(run_name="unnamed"):
    dir_name_str = "condor_energize_{}_{}"
    return dir_name_str.format(time.strftime("%Y-%m-%d_%H-%M-%S"), run_name)


def chunks(lst, n):
    """https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def expected_runtime(seq_len):
    # estimate the total expected runtime for a variant with given seq len, in seconds
    return (0.66 * seq_len) + 42


def gen_args(master_variant_fn, variants_per_job, out_dir, keep_sep_files=False):
    """generate arguments files from the master variant list"""

    # load the master list of variants
    pdbs_variants = []
    for mv_fn in master_variant_fn:
        with open(mv_fn, "r") as f:
            pdbs_variants += f.read().splitlines()

    if variants_per_job == -1:
        # todo: implement auto load balancing based on expected runtimes

        total_expected_time = 0
        seq_len_dict = {}
        for pdb_v in pdbs_variants:
            base_pdb_fn = pdb_v.split()[0]
            pdb_fn = "pdb_files/prepared_pdb_files/{}".format(base_pdb_fn)

            if base_pdb_fn not in seq_len_dict:
                seq_len_dict[base_pdb_fn] = len(get_seq_from_pdb(pdb_fn))

            total_expected_time += seq_len_dict[base_pdb_fn]

        print("total expected time: {}".format(total_expected_time))

        time_per_job = 5 * 60 * 60  # each job should take 5 hours (5 * 60 * 60 seconds)
        num_chunks = math.ceil(total_expected_time / time_per_job)
        print("num chunks: {}".format(num_chunks))

        # sort the PDBs and variants into descending order
        sorted_pdbs_variants = sorted(pdbs_variants, key=lambda x: seq_len_dict[x.split()[0]], reverse=True)

        # too slow
        # # now greedily distribute the variants into num_chunks chunks so each has roughly the same runtime
        # split_variant_lists = [[] for _ in range(num_chunks)]
        # split_variant_times = [0] * num_chunks
        #
        # # simple greedy algorithm
        # # add items one at a time to the group with the smallest total time
        # for p_v in tqdm(sorted_pdbs_variants):
        #     t = seq_len_dict[p_v.split()[0]]
        #     i = split_variant_times.index(min(split_variant_times))
        #
        #     split_variant_lists[i].append(p_v)
        #     split_variant_times[i] += t

        # different idea: round robin (probably good enough)
        split_variant_lists = [[] for _ in range(num_chunks)]
        svl_cycle = itertools.cycle(split_variant_lists)
        for p_v in tqdm(sorted_pdbs_variants):
            next(svl_cycle).append(p_v)

        # check runtimes of final splits
        rts = []
        for svl in split_variant_lists:
            rt = sum([seq_len_dict[x.split()[0]] for x in svl])
            rts.append(rt)
        print("min RT: {}".format(min(rts)))
        print("max RT: {}".format(max(rts)))

    else:
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

    # # create a file containing the list of separate variant lists files (for condor queue)
    # with open(join(out_dir, "variant_list_fns.txt"), "w") as f:
    #     for i in range(len(split_variant_lists)):
    #         f.write("{}.txt\n".format(i))

    # return the number of args files (jobs)
    return len(split_variant_lists)


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
    save_argparse_args(args_dict, join(out_dir, "run_def.txt"))

    # download the repository
    fetch_repo(args.github_tag, args.github_token, out_dir)

    # generate arguments files from the master variant list. returns the number of jobs
    # also generates a file containing the filenames of the separate variant lists (for condor queue)
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
                        nargs="+",
                        help="file containing all variants for this run. can be a list of files.")

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
