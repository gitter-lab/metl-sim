"""creating, storing, and accessing variant database
https://www.sqlitetutorial.net/sqlite-python/creating-database/"""

from os.path import isfile
import sqlite3
import sys
import argparse

import pandas as pd


def create_tables(con):
    # retrieve table creation commands from file
    ct_fn = "variant_database/create_tables.sql"
    with open(ct_fn, "r") as f:
        sql_commands_str = f.read()
    sql_commands = sql_commands_str.split(';')

    # create cursor to interact with database connection
    cur = con.cursor()

    # run the table creation commands
    for command in sql_commands:
        cur.execute(command)


def add_energies(db_fn, energies_df):
    """ add new variant records into database """
    con = sqlite3.connect(db_fn)
    energies_db_ready = energies_df.rename(columns={"variant": "mutations"})

    try:
        energies_db_ready.to_sql("variant", con, if_exists="append", index=False)
    except sqlite3.IntegrityError:
        pass

    con.close()


def add_meta(db_fn, hparams_df, jobs_df):
    """ add job and hyperparameter metadata to database """
    con = sqlite3.connect(db_fn)

    # job info dataframe must be merged with the hparam dataframe as they are both in the same SQL table
    # also add an "hp_" prefix to the hparams dataframe because that's what the SQL table expects
    hparams_db_ready = hparams_df.add_prefix("hp_").rename(columns={"hp_job_uuid": "uuid"})
    jobs_db_ready = pd.merge(jobs_df, hparams_db_ready, on="uuid")

    # github_commit_id --> github_tag
    jobs_db_ready = jobs_db_ready.rename(columns={"github_commit_id": "github_tag"})

    try:
        jobs_db_ready.to_sql("job", con, if_exists="append", index=False)
    except sqlite3.IntegrityError:
        pass

    con.close()


def main(args):

    if args.mode == "create":
        # create a new database with the proper tables for storing energies
        if isfile(args.db_fn):
            print("error: database already exists: {}".format(args.db_fn))
        else:
            con = sqlite3.connect(args.db_fn)
            create_tables(con)
            con.commit()
            con.close()

    elif args.mode == "add":
        # adding to database is done in process_run instead of here
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        fromfile_prefix_chars="@")

    parser.add_argument("mode",
                        help="run mode",
                        type=str,
                        choices=["create", "add"])

    parser.add_argument("--db_fn",
                        help="path to database file",
                        type=str,
                        default="variant_database/database.db")

    parser.add_argument("--condor_main_dir",
                        type=str,
                        help="path to the parent condor directory for run to process")

    main(parser.parse_args())

