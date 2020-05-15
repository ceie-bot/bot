import os

LISTEN_ADDRESS = "0.0.0.0" # events report api listening address
LISTEN_PORT = 1000 # events report api listening port

API_URL_PREFIX = "http://coolq-api:1001" # api listening port
QQ_ADMINISTRATORS = ["10000"] # qq id of administrators

DB_SQLITE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir)
DB_SQLITE_FILE = os.path.join(DB_SQLITE_DIR, "qqbot.db")
DB_SQLITE_JOB_FILE = os.path.join(DB_SQLITE_DIR, "jobs.db")

MODULES = [
    {
        "name": "hello",
        "prior_priority": 3000,
        "state_priority": 3000,
        "idle_priority": 3000,
        "all_state_priority": 3000
    },
]