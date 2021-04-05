""" useful functions for processing and analyzing results of energize/HTCondor runs """

import os
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
    # check if any jobs failed by looking for energies.csv in the output directory
    job_out_dirs = [join(energize_out_d, jd) for jd in os.listdir(energize_out_d)]
    failed_jobs = []
    for jd in job_out_dirs:
        if not isfile(join(jd, "energies.csv")):
            failed_jobs.append(int(parse_job_dir_name(basename(jd))["process"]))

    return failed_jobs


def check_for_missing_jobs(main_d, energize_out_d, num_expected_jobs=None):
    """ check for missing jobs on basis of no job folder in the energize output directory """
    job_out_dirs = [join(energize_out_d, jd) for jd in os.listdir(energize_out_d)]
    # check if any job output folders are missing by looking at the job nums
    job_nums = [int(parse_job_dir_name(basename(job_dir))["process"]) for job_dir in job_out_dirs]

    if num_expected_jobs is None:
        # automatically get the number of expected jobs from the env_vars.txt file
        env_vars_fn = join(main_d, "env_vars.txt")
        env_vars = parse_env_vars(env_vars_fn)
        num_expected_jobs = int(env_vars["NUM_JOBS"])

    # check if any job nums missing from expected range of job job_nums
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


def load_energies(energize_out_d):
    """ loads all energies across all jobs into a single pandas dataframe """
    job_out_dirs = [join(energize_out_d, jd) for jd in os.listdir(energize_out_d)]

    # load the energies dataframes for each job separately, then concatenate
    per_job_dfs = []
    for jd in job_out_dirs:
        energies_fn = join(jd, "energies.csv")
        skipped = []
        if isfile(energies_fn):
            per_job_dfs.append(pd.read_csv(energies_fn))
        else:
            skipped.append(energies_fn)

    print("Skipped {} log directories because they did not contain energies.txt".format(len(skipped)))
    return pd.concat(per_job_dfs, axis=0).reset_index(drop=True)


def main():
    pass


if __name__ == "__main__":
    main()
