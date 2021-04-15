"""creating, storing, and accessing variant database
https://www.sqlitetutorial.net/sqlite-python/creating-database/"""

from os.path import isfile
import sqlite3
import sys
import argparse


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

