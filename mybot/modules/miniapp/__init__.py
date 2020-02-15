import os
import json
import aiofiles
import traceback
import time
import datetime
import base64
import aiohttp

from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const
from ... import util
from ... import db
from aiocqhttp.message import Message, MessageSegment

class RevealMiniappBotModule(bot_module.BotModule):
    @classmethod
    async def prior_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        if context['post_type'] == 'message':
            if context.get('sender'):
                for msg_data in context['message']:
                    if msg_data['type'] == 'rich':
                        detail_1 = json.loads(msg_data.get('data', {}).get('content', "{}").replace("&#91;", "[").replace("&#93;", "]").replace("&#44;", ",")).get("detail_1", {})
                        pic_url = detail_1.get("preview", "")

                        if detail_1.get("title") is not None and detail_1.get("desc") is not None:
                            output_msg = Message(detail_1.get("title", "无标题") + "：" + detail_1.get("desc", "无简介"))
                            if not pic_url is None and not pic_url.strip() == "":
                                if not pic_url.startswith("http"):
                                    pic_url = "http://" + pic_url

                                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                                    async with session.get(pic_url) as resp:
                                        pic = await resp.read()

                                output_msg = output_msg + MessageSegment(type_='image', data={'file': "base64://" + base64.b64encode(pic).decode("ascii")})
                            
                            await bot.send(context, output_msg)

        return False

    @classmethod
    def prior_function_list(cls, base_priority):
        return [
            Interceptor(base_priority, cls.prior_intercept, const.TYPE_RULE_ALL, {}, {}, None)
        ]

module_class = RevealMiniappBotModule