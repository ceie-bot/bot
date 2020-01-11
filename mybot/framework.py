import collections
import copy
import importlib
from typing import List
from operator import attrgetter
import apscheduler.schedulers.asyncio
import apscheduler.jobstores.sqlalchemy
import apscheduler.executors.pool
import apscheduler.executors.asyncio

from aiocqhttp import CQHttp
from aiocqhttp.message import Message, MessageSegment
from quart.logging import default_handler, serving_handler
import logging
import logging.config
import traceback

from . import const as const
from .bot_module import Interceptor, BotModule, InputVarAttribute
from . import util as util
from . import db as db
from . import log as log

state_function_mapping = {}
prior_function_list = []
idle_function_list = []
all_state_function_list = []

def load_modules():
    global state_function_mapping
    global idle_function_list
    global all_state_function_list
    global prior_function_list

    default_module = {
        "prior_priority": 0,
        "state_priority": 0,
        "idle_priority": 0,
        "all_state_priority": 0,
    }

    for module in const.MODULES:
        effective_module = copy.copy(default_module)
        effective_module.update(module)

        default_module = copy.copy(effective_module)
        del default_module["name"]
        default_module["prior_priority"] += 5
        default_module["state_priority"] += 5
        default_module["idle_priority"] += 5
        default_module["all_state_priority"] += 5

        clazz: BotModule = importlib.import_module(".modules." + effective_module["name"], package="mybot").module_class

        # TODO: async?
        util.block_await(clazz.on_init())

        for state, interceptors in clazz.state_function_mapping(effective_module["state_priority"]).items():
            if state in state_function_mapping:
                state_function_mapping[state] += interceptors
            else:
                state_function_mapping[state] = interceptors

        prior_function_list += clazz.prior_function_list(effective_module["prior_priority"])
        idle_function_list += clazz.idle_function_list(effective_module["idle_priority"])
        all_state_function_list += clazz.all_state_function_list(effective_module["all_state_priority"])

    interceptors: List[Interceptor]
    for interceptors in state_function_mapping.values():
        interceptors.sort(key=attrgetter("priority"))

    prior_function_list.sort(key=attrgetter("priority"))
    idle_function_list.sort(key=attrgetter("priority"))
    all_state_function_list.sort(key=attrgetter("priority"))

def init_scheduler():
    util.scheduler = apscheduler.schedulers.asyncio.AsyncIOScheduler(
        jobstores={
            'default': apscheduler.jobstores.sqlalchemy.SQLAlchemyJobStore(url="sqlite:///testjob.db")
        },
        executors={
            #"default": apscheduler.executors.pool.ThreadPoolExecutor(max_workers=2)
            "default": apscheduler.executors.asyncio.AsyncIOExecutor()
        },
        job_defaults={
            "coalesce": False,
            "max_instances": 3
        }
    )
    util.scheduler.start()

def init():
    # const.print_all()
    util.block_await(db.on_init())
    init_scheduler()
    load_modules()

def configure_log(bot):
    logging.config.dictConfig({
        'version': 1,
        'loggers': {
            '': {
                'level': 'ERROR',
                'handlers': []
            },
            'quart.serving': {
                'level': 'DEBUG',
                'handlers': []
            }
        }
    })

    bot.logger.setLevel('DEBUG')
    default_handler.setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s'))
    serving_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))

    log.global_logger = bot.logger


def main():
    init()
    bot = CQHttp(api_root = const.API_URL_PREFIX, message_class=Message)

    async def execute_interceptor(interceptor, state, bot, context, msg, update_vars, extras):
        if not interceptor.accepts(context):
            return False

        input_vars = {}
        if state is not None:
            input_vars = {"state": state}

        var_name: str
        var_attr: InputVarAttribute
        for var_name, var_attr in interceptor.input_vars.items():
            input_vars[var_name] = db.get_variable(util.get_identity(context, var_attr.identity_scope), var_name, var_attr.default_val)

        intercepted = False

        if interceptor.exception_handler:
            try:
                intercepted = await interceptor.func(bot, context, msg, input_vars, update_vars, extras, **interceptor.kwargs)
            except Exception as e:
                intercepted = interceptor.exception_handler(e, bot, context, msg, input_vars, update_vars, extras, **interceptor.kwargs)
                if intercepted is None:
                    intercepted = True
        else:
            intercepted = await interceptor.func(bot, context, msg, input_vars, update_vars, extras, **interceptor.kwargs)

        return intercepted

    @bot.on_message()
    @bot.on_meta_event()
    @bot.on_notice()
    @bot.on_request()
    async def handle(context):
        # await log.debug(repr(context))

        identity = util.get_identity(context, const.GROUP)
        individual_identity = util.get_identity(context, const.INDIVIDUAL)

        state = db.get_variable(identity, "state", "idle")
        individual_state = db.get_variable(individual_identity, "state", "idle")

        msg = context.get("raw_message", "")

        filtered_msg = ""
        for msg_data in context.get('message', []):
            if msg_data['type'] == 'text':
                filtered_msg += msg_data['data']['text']
        filtered_msg = filtered_msg.strip()

        update_vars = {}
        extras = {
            "_msg_strip": msg.strip(),
            "_return": None,
            "_msg_filter": filtered_msg,
        }

        try:
            ever_intercepted = False
            for interceptor in prior_function_list:
                intercepted = await execute_interceptor(interceptor, None, bot, context, msg, update_vars, extras)
                
                if intercepted:
                    await log.info("intercepted by: %s.%s", interceptor.func.__module__.split(".")[-1], interceptor.func.__name__)
                    ever_intercepted = True
                    break

            if not ever_intercepted and individual_state != "idle":
                if individual_state in state_function_mapping:
                    interceptor: Interceptor
                    for interceptor in state_function_mapping[individual_state]:

                        intercepted = await execute_interceptor(interceptor, individual_state, bot, context, msg, update_vars, extras)
                        
                        if intercepted:
                            await log.info("intercepted by: %s.%s", interceptor.func.__module__.split(".")[-1], interceptor.func.__name__)
                            ever_intercepted = True
                            break
                else:
                    await log.warn("Undefined individual state: " + individual_state + ", now resetting it to idle")
                    individual_state = "idle"
                    db.set_variable(util.get_identity(context, const.INDIVIDUAL), "state", "idle")

            if not ever_intercepted and state != "idle":
                if state in state_function_mapping:
                    interceptor: Interceptor
                    for interceptor in state_function_mapping[state]:

                        intercepted = await execute_interceptor(interceptor, state, bot, context, msg, update_vars, extras)
                        
                        if intercepted:
                            await log.info("intercepted by: %s.%s", interceptor.func.__module__.split(".")[-1], interceptor.func.__name__)
                            ever_intercepted = True
                            break
                else:
                    await log.warn("Undefined state: " + state + ", now resetting it to idle")
                    state = "idle"
                    db.set_variable(util.get_identity(context, const.GROUP), "state", "idle")

            if not ever_intercepted:
                interceptor: Interceptor
                for interceptor in all_state_function_list:

                    intercepted = await execute_interceptor(interceptor, None, bot, context, msg, update_vars, extras)
                    
                    if intercepted:
                        await log.info("intercepted by: %s.%s", interceptor.func.__module__.split(".")[-1], interceptor.func.__name__)
                        ever_intercepted = True
                        break

                if not ever_intercepted and state == "idle":
                    for interceptor in idle_function_list:

                        intercepted = await execute_interceptor(interceptor, None, bot, context, msg, update_vars, extras)
                        
                        if intercepted:
                            await log.info("intercepted by: %s.%s", interceptor.func.__module__.split(".")[-1], interceptor.func.__name__)
                            ever_intercepted = True
                            break

            for ((var_name, var_scope), var_val) in update_vars.items():
                db.set_variable(util.get_identity(context, var_scope), var_name, var_val)

            return extras.get("_return", None)
        except PermissionError:
            tb = traceback.format_exc().strip()
            await log.warning("错误在 Context " + repr(context) + "：\n" + tb)
            return False
        except Exception:
            tb = traceback.format_exc().strip()
            await bot.send(context, "错误：\n" + tb)
            await log.error("错误在 Context " + repr(context) + "：\n" + tb)
            return False

    configure_log(bot)

    bot.run(host = const.LISTEN_ADDRESS, port = const.LISTEN_PORT, access_log_format="%(h)s %(r)s %({x-self-id}i)s %(s)s %(b)s %(L)ss")


if __name__ == "__main__":
    main()