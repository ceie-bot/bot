import bs4
import json
import aiohttp
import traceback
import lxml.html
import re

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.job import Job
from apscheduler.jobstores.base import ConflictingIdError

from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const
from ... import util
from ... import db

from .. import ddbot_electricity_bill

try:
    from . import config as priv_config
except ImportError:
    from . import config_example as priv_config

REGEX_TIME = re.compile(r'^(?P<hour>\d\d):(?P<minute>\d\d)$')

HELP_MESSAGE = "电费模块帮助："
HELP_MESSAGE += "\n查询电费：查询电费"
HELP_MESSAGE += "\n查询电费 个人限定：查询电费，但只为你自己（而非群）记录房间号"
HELP_MESSAGE += "\n电费：当记录了房间号，可以快速查询该房间号的电费"
HELP_MESSAGE += "\n电费 7 322：查询某个房间的电费，接口由 ddbot 提供"
HELP_MESSAGE += "\n删除电费房间数据：删除电费房间数据"
HELP_MESSAGE += "\n定时电费 08:30 7 322：每天固定时段查询电费，接口由 ddbot 提供"

class ElectricityBillBotModule(bot_module.BotModule):
    @classmethod
    async def before_campus(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        prefix = kwargs["prefix"]
        var_scope = kwargs["var_scope"]
        update_vars["state", var_scope] = prefix + "beforeCampus"
        
        await log.debug("Requesting EC...")
        text = await util.http_get("http://202.120.163.129:88/default.aspx", proxy = priv_config.PROXY_TJ)
        await log.debug("Response from EC: " + text)
        html = bs4.BeautifulSoup(text, "lxml")

        powerbill_viewStateStr = html.select_one("#__VIEWSTATE")["value"]
        update_vars[prefix + "viewStateStr", var_scope] = json.dumps(powerbill_viewStateStr)

        tagCampus = html.select_one("#drlouming")
        defaultCampusValue = tagCampus.find("option", {"selected": True})["value"]

        powerbill_campusList = []

        for child in tagCampus.select("option"):
            if child["value"] != defaultCampusValue:
                powerbill_campusList.append((child["value"], child.string.strip()))

        powerbill_campusList = dict(enumerate(powerbill_campusList))

        outString = ("（个人限定）" if var_scope == const.INDIVIDUAL else "") + u"（说“退出”可以退出流程）选择校区："
        outString += u"\n"
        
        for i in powerbill_campusList:
            outString += "\n" + str(i) + '. ' + powerbill_campusList[i][1]

        update_vars[prefix + "campusList", var_scope] = json.dumps(powerbill_campusList)
        extras["_return"] = {"reply": outString, "auto_escape": False}

        return True


    @classmethod
    def handle_exit(cls, update_vars, extras, var_scope):
        if extras["_msg_strip"] == "退出":
            update_vars["state", var_scope] = "idle"
            extras["_return"] = {"reply": "退出电费查询。", "auto_escape": False}
            return True
        return False

    @classmethod
    async def before_building(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        prefix = kwargs["prefix"]
        var_scope = kwargs["var_scope"]

        if cls.handle_exit(update_vars, extras, var_scope):
            return True

        msg_strip: str = extras["_msg_strip"]
        if not msg_strip.isdigit():
            return False

        opt = (msg_strip)

        powerbill_campusList = json.loads(input_vars[prefix + 'campusList'])
        powerbill_viewStateStr = json.loads(input_vars[prefix + 'viewStateStr'])

        await log.debug("campusList: " + str(powerbill_campusList))
        if opt in powerbill_campusList:
            powerbill_campus = powerbill_campusList[opt][0]
            update_vars[prefix + "campus", var_scope] = json.dumps(powerbill_campus)
        else:
            return False

        
        update_vars["state", var_scope] = prefix + "beforeBuilding"
        
        text = await util.http_post("http://202.120.163.129:88/default.aspx", data={"__EVENTTARGET": "drlouming", "__EVENTARGUMENT": "", "__LASTFOCUS": "", "__VIEWSTATE": powerbill_viewStateStr, "__VIEWSTATEGENERATOR": "CA0B0334", "drlouming": powerbill_campus, "drceng": "", "dr_ceng": "", "drfangjian": ""}, proxy = priv_config.PROXY_TJ)
        html = bs4.BeautifulSoup(text, "lxml")

        powerbill_viewStateStr = html.select_one("#__VIEWSTATE")["value"]
        update_vars[prefix + "viewStateStr", var_scope] = json.dumps(powerbill_viewStateStr)

        tagBuilding = html.select_one("#drceng")
        defaultBuildingValue = tagBuilding.find("option", {"selected": True})["value"]

        powerbill_buildingList = []

        for child in tagBuilding.select("option"):
            if child["value"] != defaultBuildingValue:
                powerbill_buildingList.append((child["value"], child.string.strip()))

        powerbill_buildingList = dict(enumerate(powerbill_buildingList))

        outString = u"（说“退出”可以退出流程）选择楼栋："
        outString += u"\n"
        
        for i in powerbill_buildingList:
            outString += "\n" + str(i) + '. ' + powerbill_buildingList[i][1]

        update_vars[prefix + "buildingList", var_scope] = json.dumps(powerbill_buildingList)
        
        extras["_return"] = {"reply": outString, "auto_escape": False}
        return True

    @classmethod
    async def before_floor(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        prefix = kwargs["prefix"]
        var_scope = kwargs["var_scope"]
        
        if cls.handle_exit(update_vars, extras, var_scope):
            return True

        msg_strip: str = extras["_msg_strip"]
        if not msg_strip.isdigit():
            return False

        opt = (msg_strip)

        powerbill_campus = json.loads(input_vars[prefix + 'campus'])
        powerbill_buildingList = json.loads(input_vars[prefix + 'buildingList'])
        powerbill_viewStateStr = json.loads(input_vars[prefix + 'viewStateStr'])

        if opt in powerbill_buildingList:
            powerbill_building = powerbill_buildingList[opt][0]
            update_vars[prefix + "final_location", var_scope] = powerbill_buildingList[opt][1]
            update_vars[prefix + "building", var_scope] = json.dumps(powerbill_building)
        else:
            return False

        update_vars["state", var_scope] = prefix + "beforeFloor"

        text = await util.http_post("http://202.120.163.129:88/default.aspx", data={"__EVENTTARGET": "drceng", "__EVENTARGUMENT": "", "__LASTFOCUS": "", "__VIEWSTATE": powerbill_viewStateStr, "__VIEWSTATEGENERATOR": "CA0B0334", "drlouming": powerbill_campus, "drceng": powerbill_building, "dr_ceng": "", "drfangjian": ""}, proxy=priv_config.PROXY_TJ)
        html = bs4.BeautifulSoup(text, "lxml")

        powerbill_viewStateStr = html.select_one("#__VIEWSTATE")["value"]
        update_vars[prefix + "viewStateStr", var_scope] = json.dumps(powerbill_viewStateStr)

        tagFloor = html.select_one("#dr_ceng")
        defaultFloorValue = tagFloor.find("option", {"selected": True})["value"]

        powerbill_floorList = []

        for child in tagFloor.select("option"):
            if child["value"] != defaultFloorValue:
                powerbill_floorList.append((child["value"], child.string.strip()))

        powerbill_floorList = dict(enumerate(powerbill_floorList))

        outString = u"（说“退出”可以退出流程）选择楼层："
        outString += u"\n"
        
        for i in powerbill_floorList:
            outString +=  "\n" + str(i) + '. ' + powerbill_floorList[i][1]

        update_vars[prefix + "floorList", var_scope] = json.dumps(powerbill_floorList)

        extras["_return"] = {"reply": outString, "auto_escape": False}
        return True


    @classmethod
    async def before_room(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        prefix = kwargs["prefix"]
        var_scope = kwargs["var_scope"]
        
        if cls.handle_exit(update_vars, extras, var_scope):
            return True

        msg_strip: str = extras["_msg_strip"]
        if not msg_strip.isdigit():
            return False

        opt = (msg_strip)

        powerbill_campus = json.loads(input_vars[prefix + 'campus'])
        powerbill_building = json.loads(input_vars[prefix + 'building'])
        powerbill_floorList = json.loads(input_vars[prefix + 'floorList'])
        powerbill_viewStateStr = json.loads(input_vars[prefix + 'viewStateStr'])

        if opt in powerbill_floorList:
            powerbill_floor = powerbill_floorList[opt][0]
            update_vars[prefix + "floor", var_scope] = json.dumps(powerbill_floor)
        else:
            return False

        update_vars["state", var_scope] = prefix + "beforeRoom"

        text = await util.http_post("http://202.120.163.129:88/default.aspx", data = {"__EVENTTARGET": "dr_ceng", "__EVENTARGUMENT": "", "__LASTFOCUS": "", "__VIEWSTATE": powerbill_viewStateStr, "__VIEWSTATEGENERATOR": "CA0B0334", "drlouming": powerbill_campus, "drceng": powerbill_building, "dr_ceng": powerbill_floor, "drfangjian": ""}, proxy=priv_config.PROXY_TJ)
        html = bs4.BeautifulSoup(text, "lxml")

        powerbill_viewStateStr = html.select_one("#__VIEWSTATE")["value"]
        update_vars[prefix + "viewStateStr", var_scope] = json.dumps(powerbill_viewStateStr)

        tagRoom = html.select_one("#drfangjian")
        defaultRoomValue = tagRoom.find("option")["value"]

        powerbill_roomList = []

        for child in tagRoom.select("option"):
            if child["value"] != defaultRoomValue:
                powerbill_roomList.append((child["value"], child.string.strip()))

        powerbill_roomList.sort(key=lambda x:x[1])
        powerbill_roomList = dict(enumerate(powerbill_roomList))

        outString = u"（说“退出”可以退出流程）选择房间（直接输入房间号）："
        outString += u"\n"
        
        for i in powerbill_roomList:
            outString += "\n" + powerbill_roomList[i][1]

        update_vars[prefix + "roomList", var_scope] = json.dumps(powerbill_roomList)

        extras["_return"] = {"reply": outString, "auto_escape": False}
        return True


    @classmethod
    async def after_room(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        prefix = kwargs["prefix"]
        var_scope = kwargs["var_scope"]
        msg_strip: str = extras["_msg_strip"]
        
        if cls.handle_exit(update_vars, extras, var_scope):
            return True
        
        powerbill_campus = json.loads(input_vars[prefix + 'campus'])
        powerbill_building = json.loads(input_vars[prefix + 'building'])
        powerbill_floor = json.loads(input_vars[prefix + 'floor'])
        powerbill_roomList = json.loads(input_vars[prefix + 'roomList'])
        powerbill_viewStateStr = json.loads(input_vars[prefix + 'viewStateStr'])

        final_location: str = ""

        valid = False
        for x in powerbill_roomList:
            if msg_strip == str(powerbill_roomList[x][1]):
                valid = True
                powerbill_room = powerbill_roomList[x][0]
                final_location = input_vars[prefix + 'final_location'] + powerbill_roomList[x][1]
                update_vars[prefix + "final_location", var_scope] = final_location
                update_vars[prefix + "room", var_scope] = json.dumps(powerbill_room)
                break

        if not valid:
            log.error("Room num not found!")
            return False

        update_vars["state", var_scope] = prefix + "askSave"

        # There will be a redirect, the destination page needs a Cookie, thus the Session.
        # RFC 2109 explicitly forbids cookie accepting from URLs with IP address instead of DNS name, but electricity API has IP as host now, thus the unsafe cookie jar.
        jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(cookie_jar=jar) as session:
            r = await session.post("http://202.120.163.129:88/default.aspx", data = {"__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": "", "__VIEWSTATE": powerbill_viewStateStr, "__VIEWSTATEGENERATOR": "CA0B0334", "drlouming": powerbill_campus, "drceng": powerbill_building, "dr_ceng": powerbill_floor, "drfangjian": powerbill_room, "radio": "usedR", "ImageButton1.x": 50, "ImageButton1.y": 50}, proxy = priv_config.PROXY_TJ)
            html = bs4.BeautifulSoup(await r.text(), "lxml")

        powerbill_viewStateStr = html.select_one("#__VIEWSTATE")["value"]
        powerbill_viewStateGeneratorStr = html.select_one("#__VIEWSTATEGENERATOR")["value"]
        #powerbill_eventValidationStr = html.select_one("#__EVENTVALIDATION")["value"]
        powerbill_eventValidationStr = "_ignored_"
        update_vars[prefix + "viewStateStr_new", var_scope] = json.dumps(powerbill_viewStateStr)
        update_vars[prefix + "viewStateGeneratorStr_new", var_scope] = json.dumps(powerbill_viewStateGeneratorStr)
        update_vars[prefix + "eventValidationStr_new", var_scope] = json.dumps(powerbill_eventValidationStr)

        credit = html.select_one(".number.orange").string

        extras["_return"] = {"reply": final_location + " 电费还剩 ￥ " + credit + "。是否为" + ("个人" if var_scope == const.INDIVIDUAL else "本群") + "保存" + ("" if var_scope == const.INDIVIDUAL else "公共") + "房间数据？", "auto_escape": False}
        return True

    @classmethod
    async def direct_query(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        prefix = kwargs["prefix"]
        var_scope = kwargs["var_scope"]

        final_location = input_vars[prefix + 'final_location']

        powerbill_campus = json.loads(input_vars[prefix + 'campus_saved'])
        powerbill_building = json.loads(input_vars[prefix + 'building_saved'])
        powerbill_floor = json.loads(input_vars[prefix + 'floor_saved'])
        powerbill_room = json.loads(input_vars[prefix + 'room_saved'])
        powerbill_viewStateStr = json.loads(input_vars[prefix + 'viewStateStr_saved'])

        jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(cookie_jar=jar, timeout=aiohttp.ClientTimeout(total=5)) as session:
            r = await session.post("http://202.120.163.129:88/default.aspx", data = {"__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": "", "__VIEWSTATE": powerbill_viewStateStr, "__VIEWSTATEGENERATOR": "CA0B0334", "drlouming": powerbill_campus, "drceng": powerbill_building, "dr_ceng": powerbill_floor, "drfangjian": powerbill_room, "radio": "usedR", "ImageButton1.x": 50, "ImageButton1.y": 50}, proxy = priv_config.PROXY_TJ)
            data = await r.text()
            extras["powerbill_direct_query_text"] = data
            html = bs4.BeautifulSoup(data, "lxml")

        credit = html.select_one(".number.orange").string

        extras["_return"] = {"reply": final_location + " 电费还剩 ￥ " + credit + "。" + ("（个人限定）" if var_scope == const.INDIVIDUAL else ""), "auto_escape": False}
        return True


    @classmethod
    async def after_ask_save(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        prefix = kwargs["prefix"]
        var_scope = kwargs["var_scope"]
        
        msg = ""
        for msg_data in context['message']:
            if msg_data['type'] == 'text':
                msg += msg_data['data']['text']
            elif msg_data['type'] == 'at':
                if str(msg_data['data']['qq']) != str(context['self_id']):
                    msg = "_"
                    break
        msg = msg.strip()
        
        if msg == "否" or "不" in msg or "别" in msg or "no" in msg.lower():
            update_vars["state", var_scope] = "idle"
            extras["_return"] = {"reply": "未保存房间数据。现在可以使用其他命令。", "auto_escape": False}
            return True
        
        if ("是" in msg or "保存" in msg or "要" in msg or "可以" in msg or "OK" in msg.upper() or "好" in msg) and "不" not in msg:
            update_vars[prefix + "viewStateStr_saved", var_scope] = input_vars[prefix + 'viewStateStr']
            update_vars[prefix + "campus_saved", var_scope] = input_vars[prefix + 'campus']
            update_vars[prefix + "building_saved", var_scope] = input_vars[prefix + 'building']
            update_vars[prefix + "floor_saved", var_scope] = input_vars[prefix + 'floor']
            update_vars[prefix + "room_saved", var_scope] = input_vars[prefix + 'room']

            update_vars["state", var_scope] = "idle"
            extras["_return"] = {"reply": "保存了房间数据。以后可以直接用“查询电费”来查询。如果要更改房间，请“删除电费房间数据”后再次查询。", "auto_escape": False}
            return True

        return False


    @classmethod
    async def intercept_powerbill(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        if msg == "帮助":
            extras["_return"] = util.append_return(extras.get("_return", None), HELP_MESSAGE, "\n\n")
            return False
            
        prefix = kwargs["prefix"]
        var_scope = kwargs["var_scope"]

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
            is_more_concrete = (u'个人限定' in msg and var_scope == const.INDIVIDUAL) or (u'查询' in msg or (u'剩' in msg and (u'多少' in msg or u'几' in msg)))
            powerbill_viewStateStr_saved = json.loads(input_vars[prefix + 'viewStateStr_saved'])
            if powerbill_viewStateStr_saved is not None and (msg == u'电费' or is_more_concrete): # powerbill_viewStateStr_saved != "null"
                direct_intercepted = await cls.direct_query(bot, context, msg, input_vars, update_vars, extras, **kwargs)
                if direct_intercepted and '别at我' in msg:
                    await bot.send(context, extras["_return"]['reply'])
                    extras["_return"] = None
                    return True
                return direct_intercepted
            
            if is_more_concrete and (u'个人限定' in msg or var_scope == const.GROUP):
                return await cls.before_campus(bot, context, msg, input_vars, update_vars, extras, **kwargs)

        return False


    @classmethod
    async def intercept_powerbill_delete(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        prefix = kwargs["prefix"]
        var_scope = kwargs["var_scope"]
        final_location = input_vars[prefix + 'final_location']

        msg = ""
        for msg_data in context['message']:
            if msg_data['type'] == 'text':
                msg += msg_data['data']['text']
            elif msg_data['type'] == 'at':
                if str(msg_data['data']['qq']) != str(context['self_id']):
                    msg = "_"
                    break
        msg = msg.strip()
        
        if msg == "删除电费房间数据" :
            powerbill_viewStateStr_saved = json.loads(input_vars[prefix + 'viewStateStr_saved'])
            if powerbill_viewStateStr_saved is not None and powerbill_viewStateStr_saved != "null":
                update_vars[prefix + "viewStateStr_saved", var_scope] = "null"
                update_vars["state", var_scope] = "idle"
                extras["_return"] = {"reply": "删除了 " + final_location + " 的房间数据。" + ("（个人限定）" if var_scope == const.INDIVIDUAL else ""), "auto_escape": False}
                return True

        return False


    @classmethod
    async def execute_crontab_job(cls, job_id, bot, context, building):
        if False:
            iden = util.get_identity(context, const.GROUP)
            powerbill_viewStateStr_saved = json.loads(db.get_variable(iden, "powerbill_viewStateStr_saved", "null"))
            powerbill_viewStateStr_saved = json.loads(db.get_variable(iden, "powerbill_viewStateStr_saved", "null"))

            if powerbill_viewStateStr_saved is not None:
                pseudo_extras = {}

                try:
                    await cls.direct_query(bot, context, "", {
                        "powerbill_final_location": db.get_variable(iden, "powerbill_final_location", "null"),
                        "powerbill_campus_saved": db.get_variable(iden, "powerbill_campus_saved", "null"),
                        "powerbill_building_saved": db.get_variable(iden, "powerbill_building_saved", "null"),
                        "powerbill_floor_saved": db.get_variable(iden, "powerbill_floor_saved", "null"),
                        "powerbill_room_saved": db.get_variable(iden, "powerbill_room_saved", "null"),
                        "powerbill_viewStateStr_saved": json.dumps(powerbill_viewStateStr_saved),
                    }, {}, pseudo_extras, prefix="powerbill_", var_scope=const.GROUP)
                except Exception as e:
                    print(e)
                    await cls.handle_exception(e, bot, context, "", {}, {}, pseudo_extras)
                    return
        
                await bot.send(context, pseudo_extras["_return"]['reply'])

        else:
            pseudo_extras = {}
            if await ddbot_electricity_bill.DDBotElectricityBillBotModule.real_query_ddbot(bot, context, building, pseudo_extras):
                await bot.send(context, pseudo_extras["_return"]['reply'])
            return True
            

    @classmethod
    async def add_crontab_job(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        if u'电费' in msg and u'定时' in msg:

            if u'取消' in msg:
                any = False
                for j in util.get_jobs():
                    real_id = j.id.split(":")[-1]
                    args = real_id.split("/")
                    if args[0] == "powerbill_crontab" and args[1] == util.get_identity(context, const.GROUP):
                        j.remove()
                        any = True

                if any:
                    result = "取消了定时电费。"
                    await bot.send(context, result)
                return True

            else:
                msg = msg.replace("查询", "")
                msg = msg.replace("电费", "")
                msg = msg.replace("\t", " ")
                msg = msg.replace("\n", " ")
                msg = msg.replace("定时", "")
                msg = msg.strip()

                time_hour = -1
                time_minute = -1
                
                building = ""

                for piece in msg.split(" "):
                    time_match = REGEX_TIME.fullmatch(piece)
                    if time_match:
                        time_hour = int(time_match.group("hour"))
                        time_minute = int(time_match.group("minute"))
                    elif piece:
                        building += piece + " "

                building = building.strip()

                print(building, time_hour, time_minute)
                if building == "" or time_hour == -1 or time_minute == -1:
                    await bot.send(context, "用法示范：（同一时间只能设定一个任务）定时电费 08:30 7 457")
                    return True

                jobcall = util.make_jobcall(cls.execute_crontab_job, context, building)
                job_id = "powerbill_crontab/%s/%02d%02d" % (util.get_identity(context, const.GROUP), time_hour, time_minute)
                
                try:
                    util.add_job(jobcall, trigger=CronTrigger(hour=time_hour, minute=time_minute), id=job_id)
                except ConflictingIdError:
                    await bot.send(context, "设置每天的 %d:%d 查询电费：失败：已有这个任务" % (time_hour, time_minute))
                    return True

                await bot.send(context, "设置每天的 %d:%d 查询电费：成功" % (time_hour, time_minute))
                return True

        return False


    @classmethod
    async def handle_exception(cls, e: Exception, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        await bot.send(context, "查询电费失败了：" + e.__class__.__name__)
        tb = traceback.format_exc().strip()
        await log.warning("查询电费错误在 Context " + repr(context) + "：\n" + tb)
        await log.warning("此时的 direct_query_text：" + extras.get("powerbill_direct_query_text", "<No key>"))
    
    @classmethod
    def state_function_mapping(cls, base_priority):
        template = {
            "beforeCampus": Interceptor(base_priority, cls.before_building, const.TYPE_RULE_MSG_ONLY, {
                "viewStateStr": InputVarAttribute("null", const.UNKNOWN),
                "campusList": InputVarAttribute("null", const.UNKNOWN)
            }, {}, cls.handle_exception),

            "beforeBuilding": Interceptor(base_priority, cls.before_floor, const.TYPE_RULE_MSG_ONLY, {
                "viewStateStr": InputVarAttribute("null", const.UNKNOWN),
                "campus": InputVarAttribute("null", const.UNKNOWN),
                "buildingList": InputVarAttribute("null", const.UNKNOWN),
            }, {}, cls.handle_exception),

            "beforeFloor": Interceptor(base_priority, cls.before_room, const.TYPE_RULE_MSG_ONLY, {
                "viewStateStr": InputVarAttribute("null", const.UNKNOWN),
                "campus": InputVarAttribute("null", const.UNKNOWN),
                "building": InputVarAttribute("null", const.UNKNOWN),
                "floorList": InputVarAttribute("null", const.UNKNOWN),
            }, {}, cls.handle_exception),

            "beforeRoom": Interceptor(base_priority, cls.after_room, const.TYPE_RULE_MSG_ONLY, {
                "viewStateStr": InputVarAttribute("null", const.UNKNOWN),
                "campus": InputVarAttribute("null", const.UNKNOWN),
                "building": InputVarAttribute("null", const.UNKNOWN),
                "floor": InputVarAttribute("null", const.UNKNOWN),
                "roomList": InputVarAttribute("null", const.UNKNOWN),
                "final_location": InputVarAttribute("", const.UNKNOWN),
            }, {}, cls.handle_exception),

            "askSave": Interceptor(base_priority, cls.after_ask_save, const.TYPE_RULE_MSG_ONLY, {
                "viewStateStr": InputVarAttribute("null", const.UNKNOWN),
                "campus": InputVarAttribute("null", const.UNKNOWN),
                "building": InputVarAttribute("null", const.UNKNOWN),
                "floor": InputVarAttribute("null", const.UNKNOWN),
                "room": InputVarAttribute("null", const.UNKNOWN),
            }, {}, cls.handle_exception),
        }

        retval = {}
        for k, v in template.items():
            input_vars_1 = {}
            for k1 in v.input_vars.keys():
                input_vars_1["powerbill_" + k1] = InputVarAttribute("null", const.GROUP)
                
            retval["powerbill_" + k] = [
                Interceptor(v.priority, v.func, v.type_rule, input_vars_1, {"prefix": "powerbill_", "var_scope": const.GROUP}, cls.handle_exception)
            ]

            input_vars_2 = {}
            for k2 in v.input_vars.keys():
                input_vars_2["powerbill_i_" + k2] = InputVarAttribute("null", const.INDIVIDUAL)

            retval["powerbill_i_" + k] = [
                Interceptor(v.priority, v.func, v.type_rule, input_vars_2, {"prefix": "powerbill_i_", "var_scope": const.INDIVIDUAL}, cls.handle_exception)
            ]

        return retval

        
    @classmethod
    def idle_function_list(cls, base_priority):
        return [
            Interceptor(base_priority + 1, cls.intercept_powerbill, const.TYPE_RULE_MSG_ONLY, {
                "powerbill_i_viewStateStr_saved": InputVarAttribute("null", const.INDIVIDUAL),
                "powerbill_i_campus_saved": InputVarAttribute("null", const.INDIVIDUAL),
                "powerbill_i_building_saved": InputVarAttribute("null", const.INDIVIDUAL),
                "powerbill_i_floor_saved": InputVarAttribute("null", const.INDIVIDUAL),
                "powerbill_i_room_saved": InputVarAttribute("null", const.INDIVIDUAL),
                "powerbill_i_final_location": InputVarAttribute("", const.INDIVIDUAL),
            }, {"prefix": "powerbill_i_", "var_scope": const.INDIVIDUAL}, cls.handle_exception),
            Interceptor(base_priority + 2, cls.intercept_powerbill, const.TYPE_RULE_MSG_ONLY, {
                "powerbill_viewStateStr_saved": InputVarAttribute("null", const.GROUP),
                "powerbill_campus_saved": InputVarAttribute("null", const.GROUP),
                "powerbill_building_saved": InputVarAttribute("null", const.GROUP),
                "powerbill_floor_saved": InputVarAttribute("null", const.GROUP),
                "powerbill_room_saved": InputVarAttribute("null", const.GROUP),
                "powerbill_final_location": InputVarAttribute("", const.GROUP),
            }, {"prefix": "powerbill_", "var_scope": const.GROUP}, cls.handle_exception),

            Interceptor(base_priority, cls.add_crontab_job, const.TYPE_RULE_MSG_ONLY, {}, {}, cls.handle_exception),
        ]


    @classmethod
    def all_state_function_list(cls, base_priority):
        return [
            Interceptor(base_priority, cls.intercept_powerbill_delete, const.TYPE_RULE_MSG_ONLY, {
                "powerbill_i_viewStateStr_saved": InputVarAttribute("null", const.INDIVIDUAL),
                "powerbill_i_final_location": InputVarAttribute("", const.INDIVIDUAL),
            }, {"prefix": "powerbill_i_", "var_scope": const.INDIVIDUAL}, cls.handle_exception),
            
            Interceptor(base_priority + 1, cls.intercept_powerbill_delete, const.TYPE_RULE_MSG_ONLY, {
                "powerbill_viewStateStr_saved": InputVarAttribute("null", const.GROUP),
                "powerbill_final_location": InputVarAttribute("", const.GROUP),
            }, {"prefix": "powerbill_", "var_scope": const.GROUP}, cls.handle_exception),
        ]

module_class = ElectricityBillBotModule
