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
    skipped = []
    for jd in job_out_dirs:
        energies_fn = join(jd, "energies.csv")
        if isfile(energies_fn):
            per_job_dfs.append(pd.read_csv(energies_fn))
        else:
            skipped.append(energies_fn)

    if len(skipped) > 0:
        print("skipped {} log directories because they did not contain energies.csv".format(len(skipped)))

    return pd.concat(per_job_dfs, axis=0).reset_index(drop=True)


def load_job_info(energize_out_d):
    """ loads all job info across all jobs into a single pandas dataframe
        SKIPS a job if there is no energies.csv
        similar to load_energies except it loads job.csv instead of energies.csv """

    job_out_dirs = [join(energize_out_d, jd) for jd in os.listdir(energize_out_d)]

    # load the energies dataframes for each job separately, then concatenate
    per_job_dfs = []
    skipped_energies = []
    skipped_job = []
    for jd in job_out_dirs:
        energies_fn = join(jd, "energies.csv")
        job_fn = join(jd, "job.csv")

        # check if energies.csv exists
        if not isfile(energies_fn):
            skipped_energies.append(energies_fn)
        # check if the job.csv file exists
        elif not isfile(job_fn):
            skipped_job.append(job_fn)
        else:
            per_job_dfs.append(pd.read_csv(job_fn, index_col=0, header=None).T)

    if len(skipped_energies) > 0:
        print("skipped {} log directories because they did not contain energies.csv".format(len(skipped_energies)))
    if len(skipped_job) > 0:
        print("skipped {} log directories because they did not contain job.csv".format(len(skipped_job)))

    return pd.concat(per_job_dfs, axis=0).reset_index(drop=True)


def load_hparams(energize_out_d):
    """ loads all hyperparam across all jobs into a single pandas dataframe
        SKIPS a job if there is no energies.csv
        similar to load_energies except it loads hparams.csv instead of energies.csv """

    # TODO: combine this function with load_job_info and load_energies
    # TODO: loading the hparams doesnt associate a job uuid with the hparams... can be solved in combined function

    job_out_dirs = [join(energize_out_d, jd) for jd in os.listdir(energize_out_d)]

    # load the energies dataframes for each job separately, then concatenate
    per_job_dfs = []
    skipped_energies = []
    skipped_hparam = []
    for jd in job_out_dirs:
        energies_fn = join(jd, "energies.csv")
        hparam_fn = join(jd, "hparams.csv")

        # check if energies.csv exists
        if not isfile(energies_fn):
            skipped_energies.append(energies_fn)
        # check if the job.csv file exists
        elif not isfile(hparam_fn):
            skipped_hparam.append(hparam_fn)
        else:
            per_job_dfs.append(pd.read_csv(hparam_fn, index_col=0, header=None).T)

    if len(skipped_energies) > 0:
        print("skipped {} log directories because they did not contain energies.csv".format(len(skipped_energies)))
    if len(skipped_hparam) > 0:
        print("skipped {} log directories because they did not contain hparams.csv".format(len(skipped_hparam)))

    return pd.concat(per_job_dfs, axis=0).reset_index(drop=True)


def main():
    pass


if __name__ == "__main__":
    main()
