"""creating, storing, and accessing variant database
https://www.sqlitetutorial.net/sqlite-python/creating-database/"""
import os
from os.path import isfile, basename, join
import sqlite3
import argparse

import pandas as pd

import utils
from utils import sort_variant_mutations


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

    # todo: memory usage for this is absurd (75+gb for a 9gb dataset)
    #   figure out why and fix

    con = sqlite3.connect(db_fn)

    energies_db_ready = energies_df.rename(columns={"variant": "mutations"})

    # before adding the energies to the database, sort the variants so the mutations are in sorted order
    # of sequence position. variants generated via rosettafy *should* already be in this order
    # however, there was the whole gb1_dms_cov dataset which used the order from the dms dataset
    # also, just in case rosettafy generates variants in the wrong order, this is the backup
    energies_db_ready["mutations"] = sort_variant_mutations(energies_db_ready["mutations"].tolist())

    try:
        energies_db_ready.to_sql("variant", con, if_exists="append", chunksize=3000, index=False, method="multi")
    except sqlite3.IntegrityError as e:
        print("Encountered sqlite3.IntegrityError, data already exists in database?")
        print(e)

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


def add_pdb(db_fn, pdb_fn):
    """ add PDB file to database """

    seq = utils.get_seq_from_pdb(pdb_fn)

    # todo: check if pdb file already exists in database and if so don't add it
    #  or handle the exception that occurs when you try to add it anyway (sqlite3.IntegrityError)
    sql = "INSERT OR IGNORE INTO pdb_file(pdb_fn, aa_sequence, seq_len) VALUES(?,?,?)"
    con = sqlite3.connect(db_fn)
    cur = con.cursor()
    cur.execute(sql, (basename(pdb_fn), seq, len(seq)))
    con.commit()
    cur.close()
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

    elif args.mode == "add_pdbs":
        pdb_dir = "pdb_files/prepared_pdb_files"
        pdb_fns = [join(pdb_dir, x) for x in os.listdir(pdb_dir) if x.endswith(".pdb")]
        for pdb_fn in pdb_fns:
            add_pdb(args.db_fn, pdb_fn)

    elif args.mode == "pdb_index":
        # create a PDB file index, similar to the database table from "add_pdbs" above
        # todo: better file for this code? it's similar to add_pdbs so keeping it here for now
        pdb_dir = "pdb_files/prepared_pdb_files"
        pdb_fns = [join(pdb_dir, x) for x in os.listdir(pdb_dir) if x.endswith(".pdb")]
        with open(join(pdb_dir, "index.csv"), "w") as f:
            f.write("pdb_fn,aa_sequence,seq_len\n")
            for pdb_fn in pdb_fns:
                seq = utils.get_seq_from_pdb(pdb_fn)
                f.write("{},{},{}\n".format(basename(pdb_fn), seq, len(seq)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        fromfile_prefix_chars="@")

    parser.add_argument("mode",
                        help="run mode",
                        type=str,
                        choices=["create", "add_pdbs", "pdb_index"])

    parser.add_argument("--db_fn",
                        help="path to database file",
                        type=str,
                        default="variant_database/database.db")

    parser.add_argument("--condor_main_dir",
                        type=str,
                        help="path to the parent condor directory for run to process")

    main(parser.parse_args())

