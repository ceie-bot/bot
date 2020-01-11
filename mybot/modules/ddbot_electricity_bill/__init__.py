import bs4
import json
import aiohttp
import traceback

from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const
from ... import util

class DDBotElectricityBillBotModule(bot_module.BotModule):

    @classmethod
    async def intercept_ddbot_powerbill(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        msg = ""
        for msg_data in context['message']:
            if msg_data['type'] == 'text':
                msg += msg_data['data']['text']
            elif msg_data['type'] == 'at':
                if str(msg_data['data']['qq']) != str(context['self_id']):
                    msg = "_"
                    break
        msg = msg.strip()

        if u'电费' in msg:
            msg = msg.replace("电费", "")
            msg = msg.replace("查", "")
            msg = msg.replace("询", "")
            msg = msg.replace("剩", "")
            msg = msg.replace("还", "")
            msg = msg.replace("几", "")
            msg = msg.replace("块", "")
            msg = msg.replace("美", "")
            msg = msg.replace("刀", "")
            msg = msg.replace("元", "")
            msg = msg.replace("？", "")
            msg = msg.replace("?", "")
            msg = msg.replace("多少", "")

            msg = msg.strip()
            if msg == u'':
                return False

            try:
                data = await util.http_get("http://pc.washingpatrick.cn:2345/elec", params={"room": msg, "o": "1"}, timeout_secs=3)
            except Exception:
                tb = traceback.format_exc().strip()
                await bot.send(context, "ddbot 由于以下错误没有发出声音：\n" + tb)
                await log.error("ddbot 错误在 Context " + repr(context) + "：\n" + tb)
                return False

            if 'error' not in data.lower():
                extras["_return"] = {"reply": "ddbot 发出了 " + data + " 的声音", "auto_escape": False}
                return True
            else:
                await log.debug("ddbot: " + data)

        return False


    @classmethod
    def all_state_function_list(cls, base_priority):
        return [
            Interceptor(base_priority, cls.intercept_ddbot_powerbill, const.TYPE_RULE_MSG_ONLY, {}, {}, None),
        ]

module_class = DDBotElectricityBillBotModule