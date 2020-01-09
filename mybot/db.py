import json
import os
import sqlite3
import datetime
import contextlib

from . import bot_module
from . import const

def get_conn():
    return sqlite3.connect(const.DB_SQLITE_FILE)

def get_variable(identity, var_name, default):
    # Connection
    with contextlib.closing(get_conn()) as conn:
        # Transaction
        with conn as trans:
            cur = trans.cursor()
            cur.execute(const.DB_SQLITE_SQL_GETVAR, (var_name, identity))
            val = cur.fetchone()
            if val is None:
                cur.execute(const.DB_SQLITE_SQL_INSERTVAR, (identity, var_name, default))
                val = default
            else:
                val = val[0]
    return val

def set_variable(identity, var_name, val):
    with contextlib.closing(get_conn()) as conn:
        with conn as trans:
            cur = trans.cursor()
            cur.execute(const.DB_SQLITE_SQL_UPDATEVAR, (identity, var_name, val, identity, var_name))
            
            if cur.rowcount > 1:
                raise sqlite3.IntegrityError("Update affected 2 rows or more")

            if cur.rowcount == 0:
                cur.execute(const.DB_SQLITE_SQL_INSERTVAR, (identity, var_name, val))

async def on_init():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS main (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `user` varchar(30) NOT NULL,
            `variable` varchar(64) NOT NULL,
            `create_date` datetime NOT NULL DEFAULT current_timestamp,
            `modify_date` datetime NOT NULL DEFAULT current_timestamp,
            `data` mediumtext DEFAULT NULL,
            UNIQUE(`user`,`variable`)
    )""")

    conn.execute("""
        DROP TRIGGER IF EXISTS [UpdateLastTime];
    """)

    conn.execute("""
        DROP TRIGGER IF EXISTS [InsertLastTime];
    """)

    conn.execute("""
        CREATE TRIGGER [UpdateLastTime]
            AFTER
            UPDATE
            ON main
            WHEN NEW.modify_date <= OLD.modify_date  
        BEGIN
            update main set modify_date=CURRENT_TIMESTAMP where id=OLD.id;
        END
        """)

    conn.close()