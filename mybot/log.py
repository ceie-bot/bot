import inspect

from . import util
from . import const

class SimpleLogger(object):
    def __init__(self, levels):
        for level in levels:
            setattr(self, level, gen_simple_logging(level))

def dummy(msg, *args, **kwargs):
    pass

def gen_log_level_method(name):
    async def log_level_method(msg, *args, **kwargs):
        inspect_stack_index = kwargs.get("inspect_stack_index", 2)
        if global_logger:
            msg = msg if isinstance(msg, str) else repr(msg)
            msg = "[%s] %s" % (get_outside_method_name(inspect_stack_index), msg % args)
            getattr(global_logger, name)(msg, **kwargs)
            
            if name in ["error", "critial", "fatal"]:
                for admin_id in const.QQ_ADMINISTRATORS:
                    await util.http_post(const.API_URL_PREFIX + "/send_private_msg", json={
                        "user_id": int(admin_id),
                        "message": msg
                    }, headers={"Content-Type": "application/json; charset=UTF-8"})

    return log_level_method

def get_outside_method_name(index):
    try:
        frame = inspect.stack()[index].frame
        args, _, _, locals = inspect.getargvalues(frame)
        clz = locals[args[0]]
        assert(hasattr(clz, "__class__"))
        if inspect.isclass(clz):
            # return frame.f_globals["__name__"].split(".")[-1] + "." + clz.__name__ + "." + inspect.stack()[index].frame.f_code.co_name
            return frame.f_globals["__name__"].split(".")[-1] + "." + inspect.stack()[index].frame.f_code.co_name
        else:
            # return frame.f_globals["__name__"].split(".")[-1] + "." + clz.__class__.__name__ + "." + inspect.stack()[index].frame.f_code.co_name
            return frame.f_globals["__name__"].split(".")[-1] + "." + inspect.stack()[index].frame.f_code.co_name
    except (KeyError, IndexError, AssertionError):
        return frame.f_globals["__name__"].split(".")[-1] + "." + inspect.stack()[index].frame.f_code.co_name

def gen_simple_logging(level):
    def simple_logging(msg, *args, **kwargs):
        print("[%s] %s" % (level ,msg % args))
    return simple_logging

levels = [
    "debug",
    "info",
    "warning",
    "warn",
    "error",
    "critial",
    "fatal"
]

global_logger = None

debug = dummy
info = dummy
warning = dummy
warn = dummy
error = dummy
critial = dummy
fatal = dummy

for level in levels:
    globals()[level] = gen_log_level_method(level)

global_logger = SimpleLogger(levels)