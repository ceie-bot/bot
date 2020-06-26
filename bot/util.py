import aiohttp
import asyncio
import inspect
import typing
import collections
import apscheduler.schedulers.asyncio
from aiocqhttp import CQHttp

from . import const

scheduler: apscheduler.schedulers.asyncio.AsyncIOScheduler = None
global_bot: CQHttp = None

def get_identity(context, scope):
    """
    scope: one of const.INDIVIDUAL, const.GROUP and const.GLOBAL.
    """
    if scope == const.GLOBAL:
        return "_global_"
    if scope == const.INDIVIDUAL:
        if 'group_id' in context:
            return str(context["group_id"]) + "# " + str(context["user_id"])
        else:
            return str(context.get("user_id", "unknown_1"))
    else:
        if 'group_id' in context:
            return str(context["group_id"]) + "#"
        else:
            return str(context.get("user_id", "unknown_2"))

async def http_post(*args, **kwargs):
    timeout_secs = 5
    if 'timeout_secs' in kwargs:
        timeout_secs = kwargs['timeout_secs']
        del kwargs['timeout_secs']

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout_secs)) as session:
        async with session.post(*args, **kwargs) as resp:
            data = await resp.text()
    return data

async def http_get(*args, **kwargs):
    timeout_secs = 5
    if 'timeout_secs' in kwargs:
        timeout_secs = kwargs['timeout_secs']
        del kwargs['timeout_secs']

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout_secs)) as session:
        async with session.get(*args, **kwargs) as resp:
            data = await resp.text()
    return data


def block_await(coroutine):
    asyncio.get_event_loop().run_until_complete(coroutine)


JobCall = collections.namedtuple("JobCall", ["func", "args", "kwargs"])
def make_jobcall(func, *args, **kwargs):
    return JobCall(func, args, kwargs)

async def _call_jobcall_with_global_bot(jobcall: JobCall, orig_job_id: str):
    if global_bot is None:
        return
    return await jobcall.func(orig_job_id, global_bot, *jobcall.args, **jobcall.kwargs)

def _process_add_job_args(jobcall: JobCall, args: typing.List, kwargs: typing.Dict):
    if not isinstance(jobcall, JobCall):
        if isinstance(jobcall, typing.Callable):
            jobcall = JobCall(jobcall, [], {})
        else:
            raise ValueError("1st argument must be a JobCall created by util.make_jobcall")

    if not 'id' in kwargs:
        raise ValueError("Must provide id for job")
    
    orig_job_id = kwargs["id"]

    if kwargs.get("prefix_job_id", True):
        kwargs["id"] = inspect.stack()[2].frame.f_globals["__name__"] + ":" + orig_job_id
    
    if "prefix_job_id" in kwargs:
        del kwargs["prefix_job_id"]

    args.insert(0, _call_jobcall_with_global_bot)
    kwargs["kwargs"] = {}
    kwargs["args"] = [jobcall, orig_job_id]


def _process_edit_job_args(args: typing.List, kwargs: typing.Dict):
    job_id = args[0]
    if not isinstance(job_id, str):
        raise ValueError("job_id must be a string")

    if kwargs.get("prefix_job_id", True):
        args[0] = inspect.stack()[2].frame.f_globals["__name__"] + ":" + job_id
    
    if "prefix_job_id" in kwargs:
        del kwargs["prefix_job_id"]


def add_job(jobcall, *args, **kwargs):
    """
    Add a job.

    Typical usage:
    
    `util.add_job(util.make_jobcall(func, arg2, arg3, kwarg0="xxx", kwarg1="yyy"), "interval", seconds=5, job_id="my_job")`

    The parameters are identical to those of 
    `apscheduler.schedulers.base.BaseScheduler.add_job`,
    with the exception of `args[0]` is a `jobcall`, which
    could be a JobCall object created by `util.make_jobcall()`.

    `jobcall.func` must accept a `str` as its 1st
    argument. This `str` contains the job id
    (not prefixed).

    `jobcall.func` must accept a `Bot` instance as
    its 2nd argument, which is used in sending messages to 
    CQHTTP API. This `Bot` instance is provided by 
    the framework at RUNTIME.

    The two arguments must not be provided by `jobcall.args`.

    `kwargs["job_id"]` MUST BE PROVIDED.

    The JobCall object will be called in a way like:
    `jobcall.func(job_id, global_bot_provided_by_runtime, *jobcall.args, **jobcall.kwargs)`

    To ensure isolation, the id of jobs are *internally*
    prefixed with the module name. If `kwargs["prefix_job_id"]`
    is set to `False`, job ids will not be prefixed.

    It is similar to the rest of the job-related
    functions.
    """
    args = list(args)
    _process_add_job_args(jobcall, args, kwargs)
    print(args)
    print(kwargs)
    return scheduler.add_job(*args, **kwargs)


def get_job(*args, **kwargs):
    """
    Get a job.

    The parameters are identical to those of 
    `apscheduler.schedulers.base.BaseScheduler.get_job`.

    For the interal prefix of `job_id`, 
    please refer to `add_job`.
    """
    args = list(args)
    _process_edit_job_args(args, kwargs)
    return scheduler.get_job(*args, **kwargs)

def pause_job(*args, **kwargs):
    """
    Pause a job.

    The parameters are identical to those of 
    `apscheduler.schedulers.base.BaseScheduler.pause_job`.
    
    For the interal prefix of `job_id`, 
    please refer to `add_job`.
    """
    args = list(args)
    _process_edit_job_args(args, kwargs)
    return scheduler.pause_job(*args, **kwargs)

def remove_job(*args, **kwargs):
    """
    Remove a job.

    The parameters are identical to those of 
    `apscheduler.schedulers.base.BaseScheduler.remove_job`.
    
    For the interal prefix of `job_id`, 
    please refer to `add_job`.
    """
    _process_edit_job_args(args, kwargs)
    return scheduler.remove_job(*args, **kwargs)

def resume_job(*args, **kwargs):
    """
    Resume a job.

    The parameters are identical to those of 
    `apscheduler.schedulers.base.BaseScheduler.resume_job`.
    
    For the interal prefix of `job_id`, 
    please refer to `add_job`.
    """
    args = list(args)
    _process_edit_job_args(args, kwargs)
    return scheduler.resume_job(*args, **kwargs)

def modify_job(*args, **kwargs):
    """
    Modify a job.

    The parameters are identical to those of 
    `apscheduler.schedulers.base.BaseScheduler.modify_job`.
    
    For the interal prefix of `job_id`, 
    please refer to `add_job`.
    """
    args = list(args)
    _process_edit_job_args(args, kwargs)
    return scheduler.modify_job(*args, **kwargs)

def get_jobs(*args, **kwargs):
    """
    Get jobs.

    The parameters are identical to those of 
    `apscheduler.schedulers.base.BaseScheduler.get_jobs`.
    
    `job_id` OF JOBS RETURNED IS PREFIXED.
    """
    prefix = ""
    if kwargs.get("prefix_job_id", True):
        prefix = inspect.stack()[1].frame.f_globals["__name__"] + ":"
    
    if "prefix_job_id" in kwargs:
        del kwargs["prefix_job_id"]

    return [job for job in scheduler.get_jobs(*args, **kwargs) if job.id.startswith(prefix)]

def append_return(_return, string, delim):
    return {
        "reply": string,    
    } if _return == None else {
        "reply": _return["reply"] + delim + string,    
    }