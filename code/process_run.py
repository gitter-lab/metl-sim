""" process an htcondor run """
import argparse
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
    failed_log_dirs, failed_jobs, failed_variants = an.check_for_failed_jobs(energize_out_dir)
    missing_jobs = an.check_for_missing_jobs(main_dir, energize_out_dir)

    with open(join(out_dir, "failed_jobs.txt"), "w") as f:
        num_failed_dirs = len(failed_log_dirs)
        num_failed = len(failed_jobs)
        # if missing_jobs is None, we were not able to infer the number of expected jobs (missing env_vars.txt)
        num_missing = len(missing_jobs) if missing_jobs is not None else "<unable to compute>"
        f.write(
            "Failed log dirs: {}, Failed jobs: {}, Missing jobs: {}, Failed variants: {}\n".format(
                num_failed_dirs, num_failed, num_missing, len(failed_variants)))
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

    runtime_vars = ["run_time",
                    "mutate_run_time",
                    "relax_run_time",
                    "filter_run_time",
                    "centroid_run_time",
                    "dock_run_time"]

    for runtime_var in runtime_vars:
        # standard pipeline has different runtime vars than docking pipeline
        # make sure the runtime var is in the dataframe
        if runtime_var not in energies.columns:
            continue

        if runtime_var == "run_time":
            step_name = "total"
        else:
            step_name = runtime_var.split("_")[0]

        fig, ax = plt.subplots(1)
        sns.histplot(data=energies, x=runtime_var, ax=ax, bins=30)
        ax.set(title="{} runtimes per variant (mean={:.2f})".format(step_name.title(), energies[runtime_var].mean()),
               xlabel="Runtime (seconds)", ylabel="Num jobs")
        fig.tight_layout()
        fig.savefig(join(out_dir, "run_time_{}.png".format(step_name)))
        plt.close(fig)

    # runtimes by number of mutations?
    # print("Avg runtime: {:.2f} seconds".format(energies["run_time"].mean()))

    # energies
    # only plot starting at "run_time" column (i.e. skip the non-numeric columns)
    # rather than hard-coding the column index, find it dynamically
    # note this relies on "run_time" being the start of the numerical columns
    # which is true for both the standard and docking pipelines...
    # todo: this updated code hasn't been tested yet (from this line to below)
    starting_col = energies.columns.get_loc("run_time")

    # need to dynamically adjust the number of rows based on the number of columns
    # this accounts for different quantity of energy terms for each pipeline
    # the number of columns will always be 4, but the number of rows will vary

    num_cols = 4
    num_rows = int((len(energies.columns) - starting_col) / num_cols) + 1
    axes = energies.hist(bins=60, figsize=(20, 40), layout=(num_rows, num_cols))
    fig = axes[0][0].get_figure()
    for i in range(len(energies.columns) - starting_col):
        ax = axes.flatten()[i]
        # ax.axvline(wt_energies.iloc[0, 4 + i], color="red", linestyle="dashed", linewidth=1.5)
        ax.axvline(energies.iloc[:, starting_col + i].mean(), color="orange", linestyle="dashed", linewidth=1.5)
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


def gen_cleanup_run_def(main_run_dir):
    """ create an HTCondor run_def to re-process failed or missing jobs from a different run """

    # load the previous run def to match parameters with this new run
    run_def_fn = join(main_run_dir, "run_def.txt")
    run_def = parse_run_def(run_def_fn)
    print("new run is based on existing run {}".format(run_def["run_name"]))

    # the new run name is just the old name with _c subscript for "clean up"
    new_run_name = run_def["run_name"] + "_c"
    print("new run name will be {}".format(new_run_name))

    # get the failed and missing job ids
    energize_out_dir = join(main_run_dir, "output", "energize_outputs")

    # failed_log_dirs, failed_jobs, failed_variants = an.check_for_failed_jobs(energize_out_dir)
    # missing_jobs = an.check_for_missing_jobs(main_run_dir, energize_out_dir)
    # print("num failed variants: {}".format(len(failed_variants)))

    failed_variants = an.get_failed_variants(main_run_dir)
    print(failed_variants)
    print(len(failed_variants))
    quit()

    # determine which variants need to be re-run (based on failed+missing jobs) and create a new master variant list
    # need access to the args folder, so uncompress it into a temp directory
    temp_out_dir = join("output", "temp_{}".format(time.strftime("%Y-%m-%d_%H-%M-%S")))
    os.makedirs(temp_out_dir)
    args_tar_fn = join(main_run_dir, "args.tar.gz")
    tar_cmd = ["tar", "-C", temp_out_dir, "-xf", args_tar_fn]
    subprocess.call(tar_cmd)
    # open up the args file for each failed job and add the variants to a list
    variants = []
    for job_id in failed_jobs + missing_jobs:
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


def main(args):

    # stats, database, cleanup
    print("Running mode: {}".format(args.mode))

    for main_dir in args.main_run_dirs:
        print("Processing {}".format(basename(main_dir)))
        if args.mode == "stats":
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

        elif args.mode == "database":
            processed_run_dir = join(main_dir, "processed_run")
            energize_out_dir = join(main_dir, "output", "energize_outputs")

            # add to database
            add_to_database(args.database_fn, processed_run_dir, energize_out_dir)

        elif args.mode == "cleanup":
            # create a new condor run definition file to re-run failed jobs
            gen_cleanup_run_def(main_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        fromfile_prefix_chars="@")

    parser.add_argument("mode",
                        help="what method to use to generate variants",
                        type=str,
                        choices=["stats", "database"])

    # common args
    parser.add_argument("--main_run_dirs",
                        help="the main directory for the condor run(s) to process",
                        type=str,
                        nargs="+")

    parser.add_argument("--db_fn",
                        help="for mode 'database', the database to add the run to",
                        type=str,
                        default=None)

    main(parser.parse_args())

