""" useful functions for processing and analyzing results of energize/HTCondor runs """

import os
from collections import defaultdict
from os.path import isfile, basename, join
import pandas as pd


def parse_job_dir_name(job_dir):
    # assuming no surprise underscores in job dir name
    tokens = job_dir.split("_")
    parsed = {"cluster": tokens[1],
              "process": tokens[2],
              "date": tokens[3],
              "time": tokens[4],
              "uuid": tokens[5]}
    return parsed


def parse_env_vars(env_vars_fn):
    """ parse the environment variables file that is used when calling condor_submit """
    with open(env_vars_fn, "r") as f:
        lines = f.readlines()

    env_vars = {}
    for line in lines:
        # first split to remove "export", second split to tokenize VAR_NAME=VALUE
        tokens = line.split(" ")[1].split("=")
        env_vars[tokens[0]] = tokens[1]

    return env_vars


def check_for_failed_jobs(energize_out_d):
    """ check for failed jobs on basis of missing energies.csv, return failed job numbers """

    # get all the job output directories / log directories
    job_out_dirs = [join(energize_out_d, jd) for jd in os.listdir(energize_out_d)]

    # create a dictionary of job ids --> job directories
    # helps keep track of multiple log directories per job ID, which might occur if jobs get rescheduled
    job_nums = [int(parse_job_dir_name(basename(job_dir))["process"]) for job_dir in job_out_dirs]
    job_num_dict = defaultdict(list)
    for job_num, job_out_dir in zip(job_nums, job_out_dirs):
        job_num_dict[job_num].append(job_out_dir)

    # loop through each job ID and check if it has failed or succeeded
    total_log_dirs = 0
    failed_log_dirs = []
    failed_jobs = []
    success_jobs = []
    multiple_success_jobs = []
    for job_id, job_out_dirs in job_num_dict.items():
        # a job id might have multiple log dirs, categorize them
        # keep track of how many log directories succeeded for this job ID
        num_succeeded = 0

        # loop through each log dir for this job ID
        for jd in job_out_dirs:
            total_log_dirs += 1
            # keep track of how many of this job's log dirs succeeded
            if not isfile(join(jd, "energies.csv")):
                # this log dir doesn't have energies.csv, so it is a failed log dir
                failed_log_dirs.append(job_id)
                # todo: also see if there are any failed variants by checking failed_variants.txt
                #  and keep track of jobs with failed variants but overall success
            else:
                num_succeeded += 1

        # if this job had zero successful log dirs, it is a completely failed job
        if num_succeeded == 0:
            failed_jobs.append(job_id)
        elif num_succeeded == 1:
            success_jobs.append(job_id)
        elif num_succeeded > 1:
            success_jobs.append(job_id)
            multiple_success_jobs.append(job_id)

    return failed_log_dirs, failed_jobs


def check_for_missing_jobs(main_d, energize_out_d, num_expected_jobs=None):
    """ check for missing jobs on basis of no job folder in the energize output directory """
    job_out_dirs = [join(energize_out_d, jd) for jd in os.listdir(energize_out_d)]
    # check if any job output folders are missing by looking at the job nums
    job_nums = [int(parse_job_dir_name(basename(job_dir))["process"]) for job_dir in job_out_dirs]

    # automatically get the number of expected jobs from the env_vars.txt file
    env_vars_fn = join(main_d, "env_vars.txt")

    if num_expected_jobs is None and isfile(env_vars_fn):
        # the number of expected jobs is not specified, but we can pull it out of the environment vars text file
        env_vars = parse_env_vars(env_vars_fn)
        num_expected_jobs = int(env_vars["NUM_JOBS"])
        # check if any job nums missing from expected range of job job_nums
        missing_jobs = list(set(range(num_expected_jobs)) - set(job_nums))
    elif num_expected_jobs is None and not isfile(env_vars_fn):
        # the expected number of jobs was not specified and we cannot find it in the environment vars text file
        # set missing jobs to None, rather than 0, to signify unable to compute
        missing_jobs = None
    else:
        # the number of expected jobs is specified as an argument
        missing_jobs = list(set(range(num_expected_jobs)) - set(job_nums))

    return missing_jobs


def resource_usage(condor_log_d):
    """ compute resource usage from HTCondor log files """

    parsed = {"job_num": [],
              "cpus": [],
              "disk": [],
              "memory": []}

    log_fns = [join(condor_log_d, lfn) for lfn in os.listdir(condor_log_d) if lfn.endswith(".log")]
    for lfn in log_fns:
        job_num = int(basename(lfn)[:-4].split("_")[-1])

        with open(lfn, "r") as f:
            lines = f.readlines()

        # note: in case the job restarted and there are multiple logs in the log file
        # just get the last resource usage (overwrite previous)
        cpus = None
        disk = None
        memory = None
        for line in lines:
            line = line.strip()
            if line.startswith("Cpus"):
                cpus = float(line.split(":")[1].split()[0])
            if line.startswith("Disk"):
                disk = int(line.split(":")[1].split()[0])
            if line.startswith("Memory"):
                memory = int(line.split(":")[1].split()[0])

        if cpus is None or disk is None or memory is None:
            print("could not parse condor log file for job: {}".format(job_num))
        else:
            parsed["job_num"].append(job_num)
            parsed["cpus"].append(cpus)
            parsed["disk"].append(disk)
            parsed["memory"].append(memory)

    return pd.DataFrame.from_dict(parsed).sort_values(by="job_num").reset_index(drop=True)


def load_multi_job_results(energize_out_d):
    """ loads energy terms, job info, and hyperparameters from a multi-job run (htcondor run) """
    job_out_dirs = [join(energize_out_d, jd) for jd in os.listdir(energize_out_d)]

    # load the energies dataframes for each job separately, then concatenate
    energies, job_info, hparams, skipped = [], [], [], []
    for jd in job_out_dirs:
        energies_fn = join(jd, "energies.csv")
        job_fn = join(jd, "job.csv")
        hparam_fn = join(jd, "hparams.csv")

        # if the job is missing any of the data files, cannot load this job
        if not isfile(energies_fn) or not isfile(job_fn) or not isfile(hparam_fn):
            skipped.append(jd)
        else:
            energies.append(pd.read_csv(energies_fn))
            job_info.append(pd.read_csv(job_fn, index_col=0, header=None).T)
            hparams.append(pd.read_csv(hparam_fn, index_col=0, header=None).T)

    if len(skipped) > 0:
        print("skipped {} log directories because they did not contain all output files".format(len(skipped)))

    energies_df = pd.concat(energies, axis=0).reset_index(drop=True)
    job_info_df = pd.concat(job_info, axis=0).reset_index(drop=True)
    hparams_df = pd.concat(hparams, axis=0).reset_index(drop=True)
    # the hparams_df does not have the job uuid but it is in the same order as energies and job info
    # just add it here to keep it simpler down the line
    hparams_df.insert(0, "job_uuid", job_info_df["uuid"])

    return energies_df, job_info_df, hparams_df


def main():
    pass


if __name__ == "__main__":
    main()
