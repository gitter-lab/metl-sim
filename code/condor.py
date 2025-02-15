""" prepare and package HTCondor runs """
import itertools
import math
import time
import os
import hashlib
from typing import Optional

import urllib3
from os.path import join, basename, isfile
import argparse
import shutil
import subprocess
import urllib.parse
import tarfile
# todo: tqdm is only on the local environment, not on condor environment
#  shouldn't be a problem since this file isn't run during a condor run...
from tqdm import tqdm

import utils
from utils import save_argparse_args, get_seq_from_pdb

# todo: find a better way to handle reading PDBs with Rosetta's pose_energy_table at the end
#   or remove the pose energy table from all the PDBs
import warnings
warnings.filterwarnings("ignore", message="Ignoring unrecognized record ")
warnings.filterwarnings("ignore", message="'HEADER' line not found; can't determine PDB ID.")


def get_run_dir_name(run_name="unnamed"):
    dir_name_str = "condor_energize_{}_{}"
    return dir_name_str.format(time.strftime("%Y-%m-%d_%H-%M-%S"), run_name)


def get_prepare_run_dir_name(run_name="unnamed"):
    dir_name_str = "condor_prepare_{}_{}"
    return dir_name_str.format(time.strftime("%Y-%m-%d_%H-%M-%S"), run_name)


def chunks(lst, n):
    """https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def expected_runtime(seq_len):
    # estimate the total expected runtime for a variant with given seq len, in seconds
    return (0.52 * seq_len) + 28.50


def gen_args(master_variant_fn, variants_per_job, out_dir, keep_sep_files=False):
    """generate arguments files from the master variant list"""

    # load the master list of variants
    pdbs_variants = []
    for mv_fn in master_variant_fn:
        with open(mv_fn, "r") as f:
            pdbs_variants += f.read().splitlines()

    if variants_per_job == -1:

        # compute the total expected runtime for all variants
        # will be used to determine how many jobs there should be
        total_expected_time = 0
        seq_len_dict = {}
        for pdb_v in pdbs_variants:
            base_pdb_fn = pdb_v.split()[0]
            pdb_fn = "pdb_files/prepared_pdb_files/{}".format(base_pdb_fn)

            if base_pdb_fn not in seq_len_dict:
                seq_len_dict[base_pdb_fn] = len(get_seq_from_pdb(pdb_fn))

            total_expected_time += expected_runtime(seq_len_dict[base_pdb_fn])

        print("average sequence length: {}".format(sum(seq_len_dict.values()) / len(seq_len_dict.values())))
        print("total expected time: {}".format(total_expected_time))

        time_per_job = 7 * 60 * 60  # each job should take 7 hours (7 * 60 * 60 seconds)
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
            rt = sum([expected_runtime(seq_len_dict[x.split()[0]]) for x in svl])
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
    tar_command = utils.get_tar_command()   # tar or gtar depending on OS
    tar_cmd = [tar_command, "-C", out_dir, "-czf", join(out_dir, "args.tar.gz"), "args"]
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

    url = "https://github.com/gitter-lab/metl-sim/archive/{}.tar.gz".format(github_tag)

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


def load_lines(fn):
    """ loads each line from given file """
    lines = []
    with open(fn, "r") as f_handle:
        for line in f_handle:
            lines.append(line.strip())
    return lines


def check_pass_file(pass_fn="htcondor/templates/pass.txt"):
    """ check if the pass.txt file is still using the default password """

    # load the contents
    with open(pass_fn, "r") as f:
        pass_contents = f.read().strip()

    if pass_contents == "password":
        warnings.warn("The pass.txt file is still using the default password. "
                      "Please change the password in pass.txt to the one you used to encrypt Rosetta.")


def create_custom_tar(exclude_dirs, output_name, root_dir_name):
    """
    Create a tar archive of all files and directories in the current directory,
    excluding specified directories, and with a custom root name when extracted.

    Parameters:
    - exclude_dirs (list of str): Names of directories to exclude from the tar.
    - output_name (str): Name of the output tar file.
    - root_dir_name (str): The name to give the root directory in the tar archive.
    """
    with tarfile.open(output_name, "w:gz") as tar:
        for item in os.listdir('.'):
            # Skip excluded directories
            if item in exclude_dirs:
                continue
            # Add each item to the archive with the specified root directory name
            tar.add(item, arcname=os.path.join(root_dir_name, item))
            print(f"Added {item} to {output_name} under root {root_dir_name}")
    
    print(f"Tar file '{output_name}' created successfully with root '{root_dir_name}', excluding {exclude_dirs}.")


def prep_energize(args):
    """
    Prepare a condor run for calculating Rosetta energies
    """

    # supports original energies (energize.py) or docking for GB1 docking energies (gb1_docking.py)
    if args.run_type == "energize":
        pyscript = "energize.py"
    elif args.run_type == "energize_docking":
        pyscript = "gb1_docking.py"
    else:
        raise ValueError("Invalid run type: {}".format(args.run_type))

    out_dir = join("output", "htcondor_runs", get_run_dir_name(args.run_name))
    os.makedirs(out_dir)

    # save the arguments for this condor run as run_def.txt in the log directory
    # remove the github authorization token to avoid storing it in a file
    args_dict = dict(vars(args))
    del args_dict["github_token"]
    save_argparse_args(args_dict, join(out_dir, "run_def.txt"))

    # download the repository
    if args.github_tag=='source_local':
        # Specify the directories to exclude and the name of the output tar file
        exclude_dirs = ['notebooks', 'output']
        output_name = f'{out_dir}{os.sep}code.tar.gz'
        root_dir_name = 'metl-sim-source_local'
    
        # Create the tar file
        create_custom_tar(exclude_dirs, output_name, root_dir_name)
                
    else: 
        fetch_repo(args.github_tag, args.github_token, out_dir)

    # generate arguments files from the master variant list. returns the number of jobs
    # also generates a file containing the filenames of the separate variant lists (for condor queue)
    num_jobs = gen_args(args.master_variant_fn, args.variants_per_job, out_dir)

    # create an env_vars.txt file to define environment variables for run.sh and energize.sub
    with open(join(out_dir, "env_vars.txt"), "w") as f:
        f.write("export GITHUB_TAG={}\n".format(args.github_tag))
        f.write("export NUM_JOBS={}\n".format(num_jobs))
        # additional environment variables to handle the different types of runs
        f.write("export PYSCRIPT={}\n".format(pyscript))

    # prepare the additional data files
    if args.use_additional_data_as_is:
        additional_files = args.additional_data_files
    else:
        additional_files = prep_additional_data_files(
            args.additional_data_files,
            out_dir,
            args.additional_data_dir
        )

    # fill in the template and save it
    fill_submit_template(template_fn="htcondor/templates/energize.sub",
                         osdf_python_distribution=args.osdf_python_distribution,
                         osdf_rosetta_distribution=args.osdf_rosetta_distribution,
                         additional_data_files=additional_files,
                         save_dir=out_dir)

    # copy over energize.sub and run.sh and the pass.txt
    # shutil.copy("htcondor/templates/energize.sub", out_dir)
    shutil.copy("htcondor/templates/run.sh", out_dir)

    if args.rosetta_decryption_password is not None:
        with open(join(out_dir, "pass.txt"), "w") as f:
            f.write(args.rosetta_decryption_password)
    else:
        check_pass_file("htcondor/templates/pass.txt")
        shutil.copy("htcondor/templates/pass.txt", out_dir)

    # copy over energize args and rename to standard filename
    shutil.copyfile(args.energize_args_fn, join(out_dir, "energize_args.txt"))

    # create output directories where jobs will place their outputs
    os.makedirs(join(out_dir, "output/condor_logs"))
    os.makedirs(join(out_dir, "output/energize_outputs"))


def fill_submit_template(template_fn: str,
                         osdf_python_distribution: Optional[str],
                         osdf_rosetta_distribution: Optional[str],
                         additional_data_files: Optional[list[str]],
                         save_dir: str):

    template_lines = load_lines(template_fn)
    template_str = "\n".join(template_lines)

    format_dict = {}

    if "{osdf_python_distribution}" in template_str:
        if osdf_python_distribution is not None:
            # load the osdf python distribution files into a list
            osdf_python_distribution_lines = load_lines(osdf_python_distribution)
            # fill in the template with the osdf python distribution
            format_dict["osdf_python_distribution"] = ", ".join(osdf_python_distribution_lines)
        else:
            format_dict["osdf_python_distribution"] = ""

    # same for Rosetta distribution
    if "{osdf_rosetta_distribution}" in template_str:
        if osdf_rosetta_distribution is not None:
            osdf_rosetta_distribution_lines = load_lines(osdf_rosetta_distribution)
            format_dict["osdf_rosetta_distribution"] = ", ".join(osdf_rosetta_distribution_lines)
        else:
            format_dict["osdf_rosetta_distribution"] = ""

    if additional_data_files is None:
        # if there are no additional data files, make it an empty list
        additional_data_files = []

    # combine all files that need to be added to transfer_input_files
    transfer_input_files = additional_data_files
    transfer_input_files_str = ", ".join(transfer_input_files)

    # if there is a spot to fill in the transfer_input_files, fill those in
    if "{transfer_input_files}" in template_str:
        format_dict["transfer_input_files"] = transfer_input_files_str

    template_str = template_str.format(**format_dict)

    with open(join(save_dir, basename(template_fn)), "w") as f:
        f.write(template_str)

    return template_str


def prep_prepare(args):
    out_dir = join("output", "htcondor_runs", get_prepare_run_dir_name(args.run_name))
    os.makedirs(out_dir)

    # save the arguments for this condor run as run_def.txt in the log directory
    # remove the github authorization token to avoid storing it in a file
    args_dict = dict(vars(args))
    del args_dict["github_token"]
    save_argparse_args(args_dict, join(out_dir, "run_def.txt"))

    # download the repository
    fetch_repo(args.github_tag, args.github_token, out_dir)

    # prepare the additional data files
    additional_files = prep_additional_data_files(args.additional_data_files, out_dir, args.additional_data_dir)

    # fill in the template and save it
    fill_submit_template(template_fn="htcondor/templates/prepare.sub",
                         osdf_python_distribution=args.osdf_python_distribution,
                         osdf_rosetta_distribution=args.osdf_rosetta_distribution,
                         additional_data_files=additional_files,
                         save_dir=out_dir)

    # copy over energize.sub and run.sh
    # shutil.copy("htcondor/templates/prepare.sub", out_dir)
    shutil.copy("htcondor/templates/run_prepare.sh", out_dir)

    if args.rosetta_decryption_password is not None:
        with open(join(out_dir, "pass.txt"), "w") as f:
            f.write(args.rosetta_decryption_password)
    else:
        check_pass_file("htcondor/templates/pass.txt")
        shutil.copy("htcondor/templates/pass.txt", out_dir)

    # copy over the pdb list (passed in as master_variant_fn)
    shutil.copyfile(args.master_variant_fn[0], join(out_dir, "pdb_list.txt"))

    # # tar and copy over the KJ directory
    # tar_fn = join(out_dir, "kj.tar.gz")
    # cmd = ["tar", "-czf", tar_fn, "pdb_files/KosciolekAndJones"]
    # subprocess.call(cmd)

    # create output directories where jobs will place their outputs
    os.makedirs(join(out_dir, "output/condor_logs"))
    os.makedirs(join(out_dir, "output/prepare_outputs"))


def is_url(path):
    if urllib.parse.urlparse(path).scheme in ("http", "https"):
        return True
    else:
        return False


def zip_additional_data(data_fns):
    """ zips up model checkpoint (for transfer learning) or other additional data
        for either squid or direct to submit node """

    if not isinstance(data_fns, list):
        data_fns = [data_fns]

    # compute hash of the files, this will become the zip filename
    # prevents uploading the same file over and over to squid and
    # having to keep track of which files are already on squid
    hash_len = 6
    # todo: this only hashes filenames, it would be more fool-proof to hash file contents
    hash_object = hashlib.shake_256(",".join(data_fns).encode("utf-8"))
    fns_hash = hash_object.hexdigest(hash_len)

    # create the output directory containing
    out_dir = join("output", "zipped_data", fns_hash)
    os.makedirs(out_dir, exist_ok=True)

    # check if zipped file already exists, if so just print a message and return
    out_fn = join(out_dir, "{}.tar.gz".format(fns_hash))
    if isfile(out_fn):
        print("Zipped data file already exists: {}. "
              "Existing file should be correct unless source contents were changed. Skipping...".format(out_fn))
    else:
        cmd = ["tar", "-czf", out_fn] + data_fns
        subprocess.call(cmd)

        # split files if needed (if the data file is bigger than 950mb)
        size_limit_bytes = 1000000000
        if os.path.getsize(out_fn) > size_limit_bytes:
            raise NotImplementedError("The compressed additional data files are greater than 1GB. "
                                      "That means the .tar.gz file is too big for SQUID, and it needs to be "
                                      "split into multiple files. However, the pipeline for processing multiple "
                                      "files is not implemented yet.")
            # split_cmd = ["split", "-b", "900m", out_fn, out_fn + "."]
            # subprocess.call(split_cmd)

    return out_fn


def prep_additional_data_files(
        additional_data_files,
        run_dir,
        additional_data_dir,
):
    """ parses additional data files to determine what is coming from squid and
        what needs to be copied to submit file or zipped up and copied to submit file """

    if additional_data_files is None:
        additional_data_files = []

    # files from additional_data_files that are coming from squid or remote location
    remote_files = []

    # files from additional_data_files that are coming from local disk
    # might need to be compressed and uploaded to squid depending on file size
    # otherwise, need to be copied over to run directory to be uploade to submit node
    local_files = []

    for fn in additional_data_files:
        if is_url(fn):
            remote_files.append(fn)
        else:
            local_files.append(fn)

    # create a zip file w/ all the local additional data
    additional_final_path = None
    if len(local_files) > 0:
        zipped_local_files_fn = zip_additional_data(local_files)

        size_limit_bytes = 100000000
        if os.path.getsize(zipped_local_files_fn) > size_limit_bytes:
            # this file needs to be transferred to OSDF, too big for submit node
            # additional data dir needs to be specified in this scenario
            if additional_data_dir is None:
                raise ValueError("The compressed additional data files are greater than 100MB. "
                                 "The additional_data_dir must be specified to transfer these files to OSDF.")
            additional_final_path = join(additional_data_dir, basename(zipped_local_files_fn))
            print(f"ADDITIONAL DATA FILES NEED TO BE TRANSFERRED TO STORAGE SERVER. "
                  f"Transfer to OSDF: {zipped_local_files_fn}. Expected final location: {additional_final_path}")
        else:
            # this file can be transferred from submit node, copy to run dir
            print("Copying compressed additional data files to run directory")
            shutil.copy(zipped_local_files_fn, run_dir)
            additional_final_path = basename(zipped_local_files_fn)

    # create the final list of additional files that should be filled in submit template
    # consists of remote files originally specified (unchanged), PLUS
    # additional local files that were zipped up and may need to be transferred to run dir or uploaded to squid
    final_files = remote_files + [additional_final_path] if additional_final_path is not None else remote_files

    return final_files


def main(args):
    if args.run_type in ["energize", "energize_docking"]:
        prep_energize(args)
    elif args.run_type == "prepare":
        prep_prepare(args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        fromfile_prefix_chars="@")

    parser.add_argument("--run_type",
                        help="prepare or energize",
                        type=str,
                        default="energize",
                        choices=["prepare", "energize", "energize_docking"])

    parser.add_argument("--run_name",
                        help="name for this condor run, used for log directory",
                        type=str,
                        default="unnamed")

    parser.add_argument("--energize_args_fn",
                        type=str,
                        help="argparse params file for energize.py that will be used with all jobs",
                        default=None)

    parser.add_argument("--master_variant_fn",
                        type=str,
                        nargs="+",
                        help="file containing all variants for this run. can be a list of files.")

    parser.add_argument("--variants_per_job",
                        type=int,
                        help="the number of variants per job")

    parser.add_argument("--osdf_python_distribution",
                        type=str,
                        help="text file containing the OSDF paths to Python distribution files",
                        default=None)

    parser.add_argument("--osdf_rosetta_distribution",
                        type=str,
                        help="text file containing the OSDF paths to Rosetta distribution files",
                        default=None)

    parser.add_argument("--rosetta_decryption_password",
                        type=str,
                        help="password to decrypt Rosetta files (will use pass.txt from templates directory if not provided)",
                        default=None)

    parser.add_argument("--additional_data_files",
                        type=str,
                        help="additional data files to transfer to execute node. these will "
                             "get added to transfer_input_files in the HTCondor submit file.",
                        nargs="*")

    parser.add_argument("--additional_data_dir",
                        type=str,
                        help="OSDF directory where additional data files should be placed. only used "
                             "when additional_data_files are present and need to be transferred to storage "
                             "server due to the file size being too big")

    parser.add_argument("--use_additional_data_as_is",
                        action="store_true",
                        help="use additional data files as is, don't zip them up or split them")

    parser.add_argument("--github_tag",
                        type=str,
                        help="github tag specifying which version of code to retrieve for this run")

    parser.add_argument("--github_token",
                        type=str,
                        help="authorization token for private metl-sim repository")

    main(parser.parse_args())
