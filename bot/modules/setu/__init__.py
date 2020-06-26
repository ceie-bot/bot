from telethon import TelegramClient, events, sync
from telethon import functions, utils
import socks
import base64
import json
import time
import datetime
import lxml.html
import traceback
import re
from aiocqhttp.message import Message, MessageSegment
import asyncio

from ... import log
from ... import db
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from .. import telegram
from ... import const
from ... import util

HELP_MESSAGE = "涩图模块帮助："
HELP_MESSAGE += "\n来点涩图：来点涩图"
HELP_MESSAGE += "\n再来点涩图：查看上一张涩图"
HELP_MESSAGE += "\n再再来点涩图：查看上上一张涩图"
HELP_MESSAGE += "\n搜图：搜索聊天中最近一张图片"
HELP_MESSAGE += "\n搜图 2：搜索聊天中最近的第二张图片"

try:
    from . import config as priv_config
except ImportError:
    from . import config_example as priv_config

FETCH_SETU_REGEX = re.compile(u"(再*)来[张,点](.+)图")

setu_lock = asyncio.Lock()

class SetuBotModule(bot_module.BotModule):
    @classmethod
    async def on_init(cls):
        if telegram.client is None:
            raise RuntimeError("telegram module not initialized")

    @classmethod
    async def all_state_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        if msg == "帮助":
            extras["_return"] = util.append_return(extras.get("_return", None), HELP_MESSAGE, "\n\n")
            return False

        async with setu_lock:
            msg_strip = extras["_msg_strip"].lower()
            
            setu_picurls = json.loads(input_vars['setu_picurls'])
            # setu_lasttime = json.loads(input_vars['setu_lasttime'])
            setu_lasttime = json.loads(db.get_variable(util.get_identity(context, const.GROUP), "setu_lasttime", "{\"fetch\": 0, \"search\": 0}"))

            if msg_strip == r'\dsetu' and str(util.get_identity(context, const.INDIVIDUAL)).split("#")[-1].strip() in const.QQ_ADMINISTRATORS:
                update_vars["setu_lasttime_saved", const.GROUP] = input_vars["setu_lasttime"]
                update_vars["setu_lasttime", const.GROUP] = json.dumps({
                    "fetch": int(datetime.datetime(2999, 12, 31, tzinfo=datetime.timezone.utc).timestamp()),
                    "search": int(datetime.datetime(2999, 12, 31, tzinfo=datetime.timezone.utc).timestamp()),
                })
                extras["_return"] = {"reply": "Setu Disabled", "auto_escape": False}
                return True

            if msg_strip == r'\esetu' and str(util.get_identity(context, const.INDIVIDUAL)).split("#")[-1].strip() in const.QQ_ADMINISTRATORS:
                update_vars["setu_lasttime", const.GROUP] = json.dumps({
                    "fetch": 0,
                    "search": 0,
                })
                extras["_return"] = {"reply": "Setu Enabled", "auto_escape": False}
                return True

            
            msg = ""
            has_setu_update = False
            for msg_data in context['message']:
                if msg_data['type'] == 'image':
                    setu_picurls += [msg_data['data']['url']]
                    has_setu_update = True
                elif msg_data['type'] == 'text':
                    msg += msg_data['data']['text']

            if has_setu_update:
                setu_picurls = setu_picurls[-10:]
                update_vars["setu_picurls", const.GROUP] = json.dumps(setu_picurls)

            spl = msg.split(" ")

            if spl[0] == "搜图" and len(setu_picurls):
                if datetime.datetime.fromtimestamp(setu_lasttime["search"], tz=datetime.timezone.utc) + datetime.timedelta(seconds=priv_config.SEARCH_INTERVAL) > datetime.datetime.now(datetime.timezone.utc):
                    extras["_return"] = {"reply": "不准搜图图", "auto_escape": False}
                    return True

                if len(spl) > 1 and spl[1].isdigit() and int(spl[1]) > 0 and int(spl[1]) <= len(setu_picurls):
                    url = setu_picurls[-int(spl[1])]
                else:
                    url = setu_picurls[-1]

                if not url:
                    extras["_return"] = {"reply": "不能搜我自己发的图图", "auto_escape": False}
                    return True

                setu_lasttime["search"] = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
                update_vars["setu_lasttime", const.GROUP] = json.dumps(setu_lasttime)
                
                db.set_variable(util.get_identity(context, const.GROUP), "setu_lasttime", update_vars["setu_lasttime", const.GROUP])

                try:
                    await bot.send(context, "正在搜色图：" + url)
                    tree = lxml.html.fromstring(await util.http_get("https://ascii2d.net/search/url/" + url, proxy=priv_config.PROXY_GFW, timeout_secs=20))

                    arr = [[], []]

                    arr[0].append(tree.xpath("string((//a[@rel=\"noopener\"][@target=\"_blank\"][not(@class)])[1]/text())"))
                    arr[0].append(tree.xpath("string((//a[@rel=\"noopener\"][@target=\"_blank\"][not(@class)])[2]/text())"))
                    arr[0].append(tree.xpath("string((//a[@rel=\"noopener\"][@target=\"_blank\"][not(@class)])[2]/following-sibling::small)"))
                    arr[0].append(tree.xpath("string((//a[@rel=\"noopener\"][@target=\"_blank\"][not(@class)])[1]/@href)"))
                    arr[1].append(tree.xpath("string((//a[@rel=\"noopener\"][@target=\"_blank\"][not(@class)])[3]/text())"))
                    arr[1].append(tree.xpath("string((//a[@rel=\"noopener\"][@target=\"_blank\"][not(@class)])[4]/text())"))
                    arr[1].append(tree.xpath("string((//a[@rel=\"noopener\"][@target=\"_blank\"][not(@class)])[4]/following-sibling::small)"))
                    arr[1].append(tree.xpath("string((//a[@rel=\"noopener\"][@target=\"_blank\"][not(@class)])[3]/@href)"))

                    arr[0] = " ".join([x.strip() for x in arr[0] if x.strip()])
                    arr[1] = " ".join([x.strip() for x in arr[1] if x.strip()])

                    result = ""
                    if arr[0]:
                        result += "1. " + arr[0]
                    if arr[1]:
                        result += "\n2. " + arr[1]

                    await bot.send(context, result)
                except Exception:
                    tb = traceback.format_exc()
                    await bot.send(context, "色图搜索错误：\n" + tb)
                    await log.error("色图搜索错误在 Context " + repr(context) + "：\n" + tb)
                    setu_lasttime["search"] = 0
                    update_vars["setu_lasttime", const.GROUP] = json.dumps(setu_lasttime)

                return True


            m = re.fullmatch(FETCH_SETU_REGEX, msg)

            if m is not None:
                index = len(m.groups()[0])
                setu_type = m.groups()[1]

                if re.fullmatch(priv_config.BANNED_SETU_TYPE, setu_type):
                    return True

                if datetime.datetime.fromtimestamp(setu_lasttime["fetch"], tz=datetime.timezone.utc) + datetime.timedelta(seconds=priv_config.FETCH_INTERVAL) > datetime.datetime.now(datetime.timezone.utc):
                    extras["_return"] = {"reply": "不准" + msg, "auto_escape": False}
                    return True

                try:
                    await bot.send(context, "稍等，在搞了")

                    setu_lasttime["fetch"] = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
                    update_vars["setu_lasttime", const.GROUP] = json.dumps(setu_lasttime)
                    db.set_variable(util.get_identity(context, const.GROUP), "setu_lasttime", update_vars["setu_lasttime", const.GROUP])

                    client = telegram.client
                    await client.connect()
                    setu_message = await client(functions.messages.GetHistoryRequest(peer=priv_config.TELEGRAM_CHANNEL_NAME, offset_id=0, offset_date=0, add_offset=index, limit=1, max_id=0, min_id=0, hash=0))

                    pic = None
                    media_url = None
                
                    try:
                        pic = await client.download_media(setu_message.messages[0].media.webpage.photo, bytes)
                        media_url = setu_message.messages[0].message + " " + setu_message.messages[0].media.webpage.url
                    except AttributeError:
                        pic = await client.download_media(setu_message.messages[0].media.photo, bytes)
                        media_url = setu_message.messages[0].message

                    if pic:
                        pic_data_url = u"base64://" + base64.b64encode(pic).decode("ascii")
                        out_message = Message(media_url + "\n") + MessageSegment(type_='image', data={'file': pic_data_url})
                        await bot.send(context, out_message)

                    setu_picurls.append("") # TODO
                    setu_picurls = setu_picurls[-10:]
                    update_vars["setu_picurls", const.GROUP] = json.dumps(setu_picurls)
                except Exception:
                    tb = traceback.format_exc()
                    await bot.send(context, "失败了失败了失败了失败了失败了")
                    await log.error("色图获取错误在 Context " + repr(context) + "：\n" + tb)
                    setu_lasttime["fetch"] = 0
                    update_vars["setu_lasttime", const.GROUP] = json.dumps(setu_lasttime)

                return True

            return False

    @classmethod
    def all_state_function_list(cls, base_priority):
        return [
            Interceptor(base_priority, cls.all_state_intercept, const.TYPE_RULE_MSG_ONLY, {
                "setu_picurls": InputVarAttribute("[]", const.GROUP),
                "setu_lasttime": InputVarAttribute("{\"fetch\": 0, \"search\": 0}", const.GROUP),
                "setu_lasttime_saved": InputVarAttribute("{\"fetch\": 0, \"search\": 0}", const.GROUP),
            }, {}, None)
        ]

module_class = SetuBotModule