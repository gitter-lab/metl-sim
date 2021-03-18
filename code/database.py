"""creating, storing, and accessing variant database
https://www.sqlitetutorial.net/sqlite-python/creating-database/"""

import sqlite3
import sys


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


def main():

    db_fn = "variant_database/database.db"
    con = sqlite3.connect(db_fn)

    create_tables(con)

    con.commit()
    con.close()


if __name__ == "__main__":
    main()
