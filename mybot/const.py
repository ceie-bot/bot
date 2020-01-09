import types

try:
    from .config import *
except ImportError:
    from .config_example import *

DB_SQLITE_SQL_GETVAR = "SELECT data FROM `main` WHERE variable=? AND user=?"
DB_SQLITE_SQL_INSERTVAR = "INSERT INTO `main` (`user`, `variable`, `data`) VALUES (?, ?, ?)"
DB_SQLITE_SQL_UPDATEVAR = """
UPDATE main
    SET user = ?, variable = ?, data = ?
    WHERE user = ? AND variable = ?;
"""

# State scope types.
UNKNOWN = -1    # not used
INDIVIDUAL = 1
GROUP = 0
GLOBAL = 2

TYPE_RULE_ALL = {
}

TYPE_RULE_MSG_ONLY = {
    "post_type": ["message"],
    "message_type": ["group", "private"],
    "^sub_type": ["notice"]
}

def print_all():
    tmp = globals()
    [print(k,'=',v) for k,v in tmp.items() if not k.startswith('_') and not isinstance(v, types.ModuleType) and k!='tmp' and k!='In' and k!='Out' and not hasattr(v, '__call__')]