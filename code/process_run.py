""" process an htcondor run """
import os
from os.path import join, isdir, isfile

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
    ax.set(title="Runtimes per variant (mean={:.2f})".format(energies["run_time"].mean()), xlabel="Runtime (seconds)", ylabel="Num jobs")
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


def main():
    # path to the parent condor directory for this run

    # GB1 runs
    # main_dir = "output/htcondor_runs/condor_energize_2021-03-31_15-29-09_gb1_ut3_1mv"
    # main_dir = "output/htcondor_runs/condor_energize_2021-04-15_13-46-55_gb1_s45_2mv"
    main_dir = "output/htcondor_runs/condor_energize_2021-05-14_12-24-59_gb1_s23_4mv"

    # condor log dir contains the condor .out, .err, and .log files for every job
    # the energize out dir contains the output folder for every job
    condor_log_dir = join(main_dir, "output", "condor_logs")
    energize_out_dir = join(main_dir, "output", "energize_outputs")

    # process run (does not add to database)
    processed_run_dir = join(main_dir, "processed_run")
    if isdir(processed_run_dir):
        print("err: processed run directory already exists, delete before reprocessing this run: {}".format(processed_run_dir))
    else:
        os.makedirs(processed_run_dir)
        process_run(main_dir, condor_log_dir, energize_out_dir, processed_run_dir)

    # add to database
    database_fn = "variant_database/database2.db"
    add_to_database(database_fn, processed_run_dir, energize_out_dir)

if __name__ == "__main__":
    main()