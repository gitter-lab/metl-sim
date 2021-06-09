""" process an htcondor run """
import os
from os.path import join, isdir, isfile, basename
import subprocess
from collections import defaultdict
import time
import shutil

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

import analysis as an
import database as db


def check_for_failed_jobs(main_dir, energize_out_dir, out_dir):
    failed_jobs = an.check_for_failed_jobs(energize_out_dir)
    missing_jobs = an.check_for_missing_jobs(main_dir, energize_out_dir)

    with open(join(out_dir, "failed_jobs.txt"), "w") as f:
        num_failed = len(failed_jobs)
        # if missing_jobs is None, we were not able to infer the number of expected jobs (missing env_vars.txt)
        nun_missing = len(missing_jobs) if missing_jobs is not None else "<unable to compute>"
        f.write("Failed jobs: {}, Missing jobs: {}\n".format(num_failed, nun_missing))
        f.write("Failed job IDs: {}\n".format(failed_jobs))
        f.write("Missing job IDs: {}\n".format(missing_jobs if missing_jobs is not None else "<unable to compute>"))


def resource_usage(condor_log_dir, out_dir):
    resources = an.resource_usage(condor_log_dir)

    # also save resources tsv to a file
    resources.to_csv(join(out_dir, "resources.csv"), index=False)

    fig, ax = plt.subplots(1)
    sns.histplot(data=resources, x="memory", ax=ax, bins=30)
    ax.set(title="Memory usage per job", xlabel="Memory (MB)", ylabel="Num jobs")
    fig.tight_layout()
    fig.savefig(join(out_dir, "mem.png"))
    plt.close(fig)

    fig, ax = plt.subplots(1)
    sns.histplot(data=resources, x="cpus", ax=ax, bins=30)
    ax.set(title="CPU usage per job", xlabel="CPUs", ylabel="Num jobs")
    fig.tight_layout()
    fig.savefig(join(out_dir, "cpu.png"))
    plt.close(fig)

    fig, ax = plt.subplots(1)
    sns.histplot(x=resources["disk"] / 1000, ax=ax, bins=30)
    ax.set(title="Disk usage per job", xlabel="Disk (MB)", ylabel="Num jobs")
    fig.tight_layout()
    fig.savefig(join(out_dir, "disk.png"))
    plt.close(fig)


def runtimes_and_energies(energize_out_dir, out_dir):
    energies, job_info, hparams = an.load_multi_job_results(energize_out_dir)

    # cache main dataframes as these can take a while to build up from scratch
    energies.to_csv(join(out_dir, "energies_df.csv"), index=False)
    job_info.to_csv(join(out_dir, "jobs_df.csv"), index=False)
    hparams.to_csv(join(out_dir, "hparams_df.csv"), index=False)

    fig, ax = plt.subplots(1)
    sns.histplot(data=energies, x="run_time", ax=ax, bins=30)
    ax.set(title="Runtimes per variant (mean={:.2f})".format(energies["run_time"].mean()),
           xlabel="Runtime (seconds)", ylabel="Num jobs")
    fig.tight_layout()
    fig.savefig(join(out_dir, "runtimes.png"))
    plt.close(fig)

    # runtimes by number of mutations?
    # print("Avg runtime: {:.2f} seconds".format(energies["run_time"].mean()))

    # energies
    axes = energies.hist(bins=60, figsize=(20, 40), layout=(16, 4))
    fig = axes[0][0].get_figure()
    for i in range(len(energies.columns) - 4):
        ax = axes.flatten()[i]
        # ax.axvline(wt_energies.iloc[0, 4 + i], color="red", linestyle="dashed", linewidth=1.5)
        ax.axvline(energies.iloc[:, 4 + i].mean(), color="orange", linestyle="dashed", linewidth=1.5)
    #     ax.set_title(ax.get_title()+" (WT={})".format(wt_energies.iloc[0, 4+i]))
    fig.tight_layout()
    fig.savefig(join(out_dir, "energies.png"))
    plt.close(fig)


def process_run(main_dir, condor_log_dir, energize_out_dir, out_dir):
    check_for_failed_jobs(main_dir, energize_out_dir, out_dir)
    resource_usage(condor_log_dir, out_dir)
    runtimes_and_energies(energize_out_dir, out_dir)


def add_to_database(db_fn, processed_run_dir, energize_out_dir):
    """ add an htcondor run to the variant database (variants, energies, and run metadata) """

    # check if main dataframes are cached from process_run() (runtimes_and_energies function)
    energies_cache_fn = "energies_df.csv"
    jobs_cache_fn = "jobs_df.csv"
    hparams_cache_fn = "hparams_df.csv"
    cache_fns = [energies_cache_fn, jobs_cache_fn, hparams_cache_fn]

    if all([isfile(join(processed_run_dir, cache_fn)) for cache_fn in cache_fns]):
        print("Loading energies_df, jobs_df, and hparams_df from cache")
        energies_df = pd.read_csv(join(processed_run_dir, energies_cache_fn))
        jobs_df = pd.read_csv(join(processed_run_dir, jobs_cache_fn))
        hparams_df = pd.read_csv(join(processed_run_dir, hparams_cache_fn))
    else:
        # load from scratch
        print("Loading energies_df, jobs_df, and hparams_df from scratch")
        energies_df, jobs_df, hparams_df = an.load_multi_job_results(energize_out_dir)

    # add these dataframes to the database
    db.add_energies(db_fn, energies_df)
    db.add_meta(db_fn, hparams_df, jobs_df)


def get_real_failed_jobs(failed_jobs, energize_out_dir):
    # todo: integrate this functionality into analysis.check_for_failed_jobs() and optimize...can be more efficient
    # some of the failed jobs might actually have succeeded if they got re-scheduled by HTCondor
    # in those cases, there could be multiple job log directories, and only one of them contains the complete output
    # create a dictionary of job ids to make these easier to find
    job_out_dirs = [join(energize_out_dir, jd) for jd in os.listdir(energize_out_dir)]  # all the job output dirs
    job_nums = [int(an.parse_job_dir_name(basename(job_dir))["process"]) for job_dir in job_out_dirs]
    job_num_dict = defaultdict(list)
    for job_num, job_out_dir in zip(job_nums, job_out_dirs):
        job_num_dict[job_num].append(job_out_dir)

    # check if any of the failed jobs have multiple log directories, and if so, did any of them complete successfully
    real_failed_jobs = []
    for fj in failed_jobs:
        if len(job_num_dict[fj]) == 1:
            # if the failed job only has 1 log directory, it's a real failed job
            real_failed_jobs.append(fj)
        elif len(job_num_dict[fj]) > 1:
            # if the failed job has multiple log directories, check if any of them succeeded
            job_succeeded = False
            for jld in job_num_dict[fj]:
                if isfile(join(jld, "energies.csv")):
                    job_succeeded = True
            if not job_succeeded:
                real_failed_jobs.append(fj)

    return real_failed_jobs


def parse_run_def(run_def_fn):
    # todo: this is better done with argparse
    with open(run_def_fn, "r") as f:
        run_def_txt = f.readlines()
    run_def = {}
    for i in range(0, len(run_def_txt), 2):
        var_name = run_def_txt[i].strip()[2:]
        value = run_def_txt[i + 1].strip()
        run_def[var_name] = value
    return run_def


def gen_cleanup_rundef(main_run_dir):
    """ create an HTCondor run_def to re-process failed or missing jobs from a different run """

    # load the previous rundef to match parameters with this new run
    run_def_fn = join(main_run_dir, "run_def.txt")
    run_def = parse_run_def(run_def_fn)
    print("new run is based on existing run {}".format(run_def["run_name"]))

    # the new run name is just the old name with _c subscript for "clean up"
    new_run_name = run_def["run_name"] + "_c"
    print("new run name will be {}".format(new_run_name))

    # get the failed and missing job ids
    energize_out_dir = join(main_run_dir, "output", "energize_outputs")
    failed_jobs = an.check_for_failed_jobs(energize_out_dir)
    real_failed_jobs = get_real_failed_jobs(failed_jobs, energize_out_dir)
    missing_jobs = an.check_for_missing_jobs(main_run_dir, energize_out_dir)
    print("num failed jobs: {}".format(len(failed_jobs)))
    print("num real failed jobs: {}".format(len(real_failed_jobs)))
    print("num missing jobs: {}".format(len(missing_jobs)))

    # determine which variants need to be re-run (based on failed+missing jobs) and create a new master variant list
    # need access to the args folder, so uncompress it into a temp directory
    temp_out_dir = join("output", "temp_{}".format(time.strftime("%Y-%m-%d_%H-%M-%S")))
    os.makedirs(temp_out_dir)
    args_tar_fn = join(main_run_dir, "args.tar.gz")
    tar_cmd = ["tar", "-C", temp_out_dir, "-xf", args_tar_fn]
    subprocess.call(tar_cmd)
    # open up the args file for each failed job and add the variants to a list
    variants = []
    for job_id in real_failed_jobs + missing_jobs:
        with open(join(temp_out_dir, "args", "{}.txt".format(job_id)), "r") as f:
            variants = variants + f.read().splitlines()
    # remove temp directory
    shutil.rmtree(temp_out_dir)

    # save the variants to a new master variant list
    master_list_fn = join("variant_lists", "{}_variants.txt".format(new_run_name))
    if isfile(master_list_fn):
        print("err: variant master list already exists. delete before continuing: {}".format(master_list_fn))
        quit()
    with open(master_list_fn, "w") as f:
        for variant in variants:
            f.write("{}\n".format(variant))
    print("saved variant master list to {}".format(master_list_fn))

    # create the run_def file for this clean up run
    new_run_def_fn = join("htcondor", "run_defs", "{}.txt".format(new_run_name))
    if isfile(new_run_def_fn):
        print("err: run def already exists. delete before continuing: {}".format(new_run_def_fn))
        quit()
    with open(new_run_def_fn, "w") as f:
        f.write("--run_name\n{}\n".format(new_run_name))
        f.write("--energize_args_fn\n{}\n".format(run_def["energize_args_fn"]))
        f.write("--master_variant_fn\n{}\n".format(master_list_fn))
        f.write("--variants_per_job\n{}\n".format(run_def["variants_per_job"]))
        f.write("--github_tag\n{}".format(run_def["github_tag"]))
    print("saved run def to {}".format(new_run_def_fn))


def main():
    # path to the parent condor directory for this run

    # stats, database, cleanup
    mode = "cleanup"

    # GB1 runs
    # main_dir = "output/htcondor_runs/condor_energize_2021-03-31_15-29-09_gb1_ut3_1mv"
    # main_dir = "output/htcondor_runs/condor_energize_2021-04-15_13-46-55_gb1_s45_2mv"
    # main_dir = "output/htcondor_runs/condor_energize_2021-05-14_12-24-59_gb1_s23_4mv"

    # avGFP runs
    main_dir = "output/htcondor_runs/condor_energize_2021-05-26_15-03-47_avgfp_s12_200kv"

    if mode == "stats":
        # output directory for processed run stats
        processed_run_dir = join(main_dir, "processed_run")

        # condor log dir contains the condor .out, .err, and .log files for every job
        # the energize out dir contains the output folder for every job
        condor_log_dir = join(main_dir, "output", "condor_logs")
        energize_out_dir = join(main_dir, "output", "energize_outputs")

        if isdir(processed_run_dir):
            print("err: processed run directory already exists, delete before continuing: {}".format(processed_run_dir))
        else:
            os.makedirs(processed_run_dir)
            process_run(main_dir, condor_log_dir, energize_out_dir, processed_run_dir)

    elif mode == "database":
        processed_run_dir = join(main_dir, "processed_run")
        energize_out_dir = join(main_dir, "output", "energize_outputs")

        # add to database
        database_fn = "variant_database/database2.db"
        add_to_database(database_fn, processed_run_dir, energize_out_dir)

    elif mode == "cleanup":
        # create a new condor run definition file to re-run failed jobs
        gen_cleanup_rundef(main_dir)


if __name__ == "__main__":
    main()
