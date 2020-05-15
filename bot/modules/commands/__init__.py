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
        msg = msg.replace("&#91;", "[").replace("&#93;", "]")

        # 重置对方当前的 GROUP 状态和 INDIVIDUAL 状态，使用方法为 \resetstatus
        if msg_strip == r'\resetstatus':
            update_vars["state", const.GROUP] = "idle"
            update_vars["state", const.INDIVIDUAL] = "idle"
            extras["_return"] = {"reply": "状态重置为 idle。", "auto_escape": False}
            return True

        # 显示对方当前的 GROUP 状态和 INDIVIDUAL 状态，使用方法为 \showstatus
        if msg_strip == r'\showstatus':
            extras["_return"] = {"reply": "当前 GROUP 状态：" + db.get_variable(util.get_identity(context, const.GROUP), "state", "idle") + "\n当前 INDIVIDUAL 状态：" + db.get_variable(util.get_identity(context, const.INDIVIDUAL), "state", "idle"), "auto_escape": False}
            return True

        # 向某个群号发送一条信息，使用如 \sendg 群号 消息
        if msg.startswith(r'\sendg ') and str(util.get_identity(context, const.INDIVIDUAL)) in const.QQ_ADMINISTRATORS:
            arr = msg.split(" ")
            group_id = int(arr[1])
            real_msg = ' '.join(arr[2:])
            await log.info(r"\sendG " + str(group_id) + " " + real_msg)
            
            # 在这里我们手动构造了向酷Q HTTP API 的 HTTP 请求，而不是用 bot.send。这是因为信息的接收者和目前的聊天对方不一致，此外还因为我们需要拿到信息是否发送成功的返回结果（data）
            data = await util.http_post(const.API_URL_PREFIX + "/send_group_msg", json={"group_id": group_id, "message": real_msg, "auto_escape": False}, headers={"Content-Type": "application/json; charset=UTF-8"})


            await bot.send(context, data)
            return True

        # 向某个私人号发送一条消息，用法和原理大致同上
        if msg.startswith(r'\sendp ') and str(util.get_identity(context, const.INDIVIDUAL)) in const.QQ_ADMINISTRATORS:
            arr = msg.split(" ")
            user_id = int(arr[1])
            real_msg = ' '.join(arr[2:])
            await log.info(r"\sendP " + str(user_id) + " " + real_msg)
            data = await util.http_post(const.API_URL_PREFIX + "/send_private_msg", json={"user_id": user_id, "message": real_msg, "auto_escape": False}, headers={"Content-Type": "application/json; charset=UTF-8"})

            await bot.send(context, data)
            return True

        return False

module_class = CommandsBotModule