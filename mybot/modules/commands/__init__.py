import bs4
import json
import aiohttp
import traceback
import time

from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const
from ... import util
from ... import db

try:
    from . import config as priv_config
except ImportError:
    from . import config_example as priv_config

class CommandsBotModule(bot_module.BotModule):

    @classmethod
    async def prior_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        msg_strip = extras["_msg_strip"].lower()

        if msg_strip == r'\resetstatus':
            #await bot.send(context, "状态重置为 idle。")
            update_vars["state", const.GROUP] = "idle"
            update_vars["state", const.INDIVIDUAL] = "idle"
            extras["_return"] = {"reply": "状态重置为 idle。", "auto_escape": False}
            return True

        if msg_strip == r'\showstatus':
            #await bot.send(context, "当前状态：" + state + "\n当前群聊个人状态：" + individualState)
            extras["_return"] = {"reply": "当前状态：" + db.get_variable(util.get_identity(context, const.GROUP), "state", "idle") + "\n当前群聊个人状态：" + db.get_variable(util.get_identity(context, const.INDIVIDUAL), "state", "idle"), "auto_escape": False}
            return True

        if msg.startswith(r'\sendg ') and str(util.get_identity(context, const.INDIVIDUAL)) in const.QQ_ADMINISTRATORS:
            arr = msg.split(" ")
            group_id = int(arr[1])
            real_msg = ' '.join(arr[2:])
            log.info(r"\sendG " + str(group_id) + " " + real_msg)
            data = await util.http_post(const.API_URL_PREFIX + "/send_group_msg", json={"group_id": group_id, "message": real_msg}, headers={"Content-Type": "application/json; charset=UTF-8"})

            await bot.send(context, data)
            return True

        if msg.startswith(r'\sendfavg ') and str(util.get_identity(context, const.INDIVIDUAL)) in const.QQ_ADMINISTRATORS:
            arr = msg.split(" ")
            group_id = priv_config.FAV_GROUP
            real_msg = ' '.join(arr[1:])
            log.info(r"\sendG " + str(group_id) + " " + real_msg)
            data = await util.http_post(const.API_URL_PREFIX + "/send_group_msg", json={"group_id": group_id, "message": real_msg}, headers={"Content-Type": "application/json; charset=UTF-8"})

            await bot.send(context, data)
            return True

        if msg.startswith(r'\sendp ') and str(util.get_identity(context, const.INDIVIDUAL)) in const.QQ_ADMINISTRATORS:
            arr = msg.split(" ")
            user_id = int(arr[1])
            real_msg = ' '.join(arr[2:])
            log.info(r"\sendP " + str(user_id) + " " + real_msg)
            data = await util.http_post(const.API_URL_PREFIX + "/send_private_msg", json={"user_id": user_id, "message": real_msg}, headers={"Content-Type": "application/json; charset=UTF-8"})

            await bot.send(context, data)
            return True

        return False

module_class = CommandsBotModule