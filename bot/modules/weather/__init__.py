import json
import re
import typing
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

try:
    from . import config as priv_config
except ImportError:
    from . import config_example as priv_config

HELP_MESSAGE = "天气模块帮助："
HELP_MESSAGE += "\n查询同济大学嘉定校区天气：查询同济大学嘉定校区天气"
HELP_MESSAGE += "\n定时天气 上海 08:30：每天 8:30 报告上海天气"
HELP_MESSAGE += "\n取消定时天气：取消所有定时天气"
HELP_MESSAGE += "\n上海市天气预警：开启上海市天气预警"
HELP_MESSAGE += "\n取消天气预警：取消所有天气预警"

WEATHER_DICT = {
    "CLEAR_DAY": "晴",
    "CLEAR_NIGHT": "晴",
    "PARTLY_CLOUDY_DAY": "多云",
    "PARTLY_CLOUDY_NIGHT": "多云",
    "CLOUDY": "阴",
    "WIND": "有大风",
    "HAZE": "有雾霾",
    "RAIN": "下雨",
    "LIGHT_RAIN": "下小雨",
    "MODERATE_RAIN": "下中雨",
    "HEAVY_RAIN": "下大雨",
    "STORM_RAIN": "有暴雨",
    "SNOW": "下雪",
    "LIGHT_SNOW": "下小雪",
    "MODERATE_SNOW": "下中雪",
    "HEAVY_SNOW": "下大雪",
    "STORM_SNOW": "有暴雪",
}

WIND_LIST = [
    "北风",
    "东北风",
    "东风",
    "东南风",
    "南风",
    "西南风",
    "西风",
    "西北风",
]

REGEX_LNG_LAT = re.compile(r'^(?P<lng>\d+(\.\d+)?),(?P<lat>\d+(\.\d+)?)$')
REGEX_TIME = re.compile(r'^(?P<hour>\d\d):(?P<minute>\d\d)$')

class WeatherBotModule(bot_module.BotModule):
    @classmethod
    async def on_init(cls):
        pass

    @classmethod
    def wind_direction(cls, degree):
        return WIND_LIST[int((degree + 22.5) % 360 / 45)]

    @classmethod
    async def get_location_from_msg(cls, msg, extras: typing.Dict) -> typing.Dict:
        m = re.fullmatch(REGEX_LNG_LAT, msg)
        if m:
            return {
                "name": msg,
                "lng": float(m.group("lng")),
                "lat": float(m.group("lat")),
            }
        else:
            data = await util.http_get("https://apis.map.qq.com/ws/place/v1/suggestion", params={
                "keyword": msg,
                "key": "K76BZ-W3O2Q-RFL5S-GXOPR-3ARIT-6KFE5",
            }, headers={
                "Referer": "https://lbs.qq.com/tool/getpoint/getpoint.html",
            }, timeout_secs=15)

            await log.info("get_location_from_msg result: " + data)

            try:
                data = json.loads(data)
            except json.decoder.JSONDecodeError:
                data = {}

            if not "data" in data:
                extras["_error"] = data.get("message", "未知错误")
                return None

            if len(data["data"]) == 0:
                extras["_error"] = "找不到此地址"
                return None
                
            return {
                "name": data["data"][0]["title"],
                "lng": data["data"][0]["location"]["lng"],
                "lat": data["data"][0]["location"]["lat"],
            }


    @classmethod
    async def real_query_and_send(cls, job_id, bot, context, location):
        data = await util.http_get("https://api.caiyunapp.com/v2/%s/%lg,%lg/weather.json?alert=true" % (priv_config.API_KEY, location["lng"], location["lat"]))
        data = json.loads(data)
        if not "result" in data:
            await bot.send(context, "查询天气无结果")
            return
        data = data['result']
        daily = data['daily']
        hourly = data['hourly']
        alert = data['alert']['content']
        rainy_keypoint = data['forecast_keypoint']
        realtime = data['realtime']

        result = ""
        
        # Realtime & Today
        result += location["name"] + "：当前气温 " + str(realtime['temperature']) + "°C，"
        result += "AQI " + str(realtime['aqi']) + "，"
        result += "今日" + WEATHER_DICT.get(daily['skycon_20h_32h'][0]['value'], daily['skycon_20h_32h'][0]['value']) + ""
        result += "，明日" + WEATHER_DICT.get(daily['skycon_20h_32h'][1]['value'], daily['skycon_20h_32h'][1]['value']) + ""
        if realtime['wind']['speed'] > 8:
            result += "。当前" + cls.wind_direction(realtime['wind']['direction']) + " " + str(realtime['wind']['speed']) + "km/h。"
        else:
            result += "。"

        # Rain forecast
        rainForecastTime = None
        rainForecast = None
        for skycon in hourly['skycon']:
            if "RAIN" in skycon['value'] or "SNOW" in skycon['value']:
                rainForecast = WEATHER_DICT.get(skycon['value'], skycon['value'])
                rainForecastTime = skycon['datetime']
                break

        if rainForecast:
            result += "\n"
            result += "注意未来 " + rainForecastTime + " 时" + rainForecast + "。"

        for al in alert:
            result += "\n"
            result += al['description']

        # Hourly
        result += "\n"
        minTemp = 999
        minTempTime = ""
        maxTemp = -999
        maxTempTime = ""
        
        for hourTemp in hourly['temperature']:
            if hourTemp['value'] < minTemp:
                minTemp = hourTemp['value']
                minTempTime = hourTemp['datetime']
            if hourTemp['value'] > maxTemp:
                maxTemp = hourTemp['value']
                maxTempTime = hourTemp['datetime']

        result += "未来 48 小时，气温会在 " + minTempTime + " 降到最低 " + str(minTemp) + "°C，"
        result += "在 " + maxTempTime + " 升高到最高 " + str(maxTemp) + "°C。"

        result += "\n" + rainy_keypoint

        await bot.send(context, result)
        return


    @classmethod
    async def check_alert_update(cls, job_id, bot, context, location):
        data = await util.http_get("https://api.caiyunapp.com/v2/%s/%lg,%lg/weather.json?alert=true" % (priv_config.API_KEY, location["lng"], location["lat"]))
        data = json.loads(data)
        if not "result" in data:
            await bot.send(context, "查询天气无结果，预警配置错误")
            return

        history_var_name = "weather_history_alerts/%s" % location["name"]
        
        history_alerts = json.loads(db.get_variable(util.get_identity(context, const.GROUP), history_var_name, "[]"))
        alerts = [a["description"] for a in data['result']['alert']['content']]
        alerts_filtered = [a for a in alerts if a not in history_alerts]
        history_alerts = alerts
        db.set_variable(util.get_identity(context, const.GROUP), history_var_name, json.dumps(history_alerts))

        if len(alerts_filtered) == 0:
            return True

        result = "%s 有新的天气预警：\n" % location["name"]

        for al in alerts_filtered:
            result += "\n"
            result += al

        await bot.send(context, result)
        return


    @classmethod
    async def query_weather(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        if msg == "帮助":
            extras["_return"] = util.append_return(extras.get("_return", None), HELP_MESSAGE, "\n\n")
            return False

        if u'天气' in msg and (u'查询' in msg or (u'怎' in msg)):
            msg = msg.replace("天气", "")
            msg = msg.replace(" ", "")
            msg = msg.replace("\t", "")
            msg = msg.replace("\n", "")
            msg = msg.replace("怎样", "")
            msg = msg.replace("怎", "")
            msg = msg.replace("么样", "")
            msg = msg.replace("今天", "")
            msg = msg.replace("明天", "")
            msg = msg.replace("查询", "")
            msg = msg.strip()

            location = json.loads(input_vars["weather_location"])
            if msg != "":
                location = await cls.get_location_from_msg(msg, extras)
                if location is None:
                    await bot.send(context, "获取地理位置无结果：" + extras["_error"])
                    return True

                update_vars["weather_location", const.GROUP] = json.dumps(location)

            await cls.real_query_and_send("dummy", bot, context, location)
            return True
        return False

    
    @classmethod
    async def add_weather_job(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        if u'天气' in msg and u'定时' in msg:

            if u'取消' in msg:
                result = "取消了所有定时天气："
                j: Job
                for j in util.get_jobs():
                    real_id = j.id.split(":")[-1]
                    args = real_id.split("/")
                    if args[0] == "weather_crontab" and args[1] == util.get_identity(context, const.GROUP):
                        result += "\n" + args[-2] + " " + args[-1]
                        j.remove()

                await bot.send(context, result)
                return True

            else:
                msg = msg.replace("天气", "")
                msg = msg.replace("\t", " ")
                msg = msg.replace("\n", " ")
                msg = msg.replace("定时", "")
                msg = msg.strip()

                location_msg = ""
                time_hour = -1
                time_minute = -1

                for piece in msg.split(" "):
                    time_match = REGEX_TIME.fullmatch(piece)
                    if time_match:
                        time_hour = int(time_match.group("hour"))
                        time_minute = int(time_match.group("minute"))
                    else:
                        location_msg += piece

                if location_msg == "" or time_hour == -1 or time_minute == -1:
                    await bot.send(context, "用法示范：定时天气 上海 08:30")
                    return True
                
                location = await cls.get_location_from_msg(location_msg, extras)

                if location is None:
                    await bot.send(context, "获取地理位置无结果：" + extras["_error"])
                    return True

                jobcall = util.make_jobcall(cls.real_query_and_send, context, location)
                job_id = "weather_crontab/%s/%02d%02d/%s" % (util.get_identity(context, const.GROUP), time_hour, time_minute, location["name"].replace("/", ""))
                
                try:
                    util.add_job(jobcall, trigger=CronTrigger(hour=time_hour, minute=time_minute), id=job_id)
                except ConflictingIdError:
                    await bot.send(context, "设置每天的 %d:%d 提醒 %s 的天气：失败：已有这个任务" % (time_hour, time_minute, location["name"]))
                    return True

                await bot.send(context, "设置每天的 %d:%d 提醒 %s 的天气：成功" % (time_hour, time_minute, location["name"]))
                return True

        return False


    @classmethod
    async def add_alert_job(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        if u'天气' in msg and u'预警' in msg:

            if u'取消' in msg:
                result = "取消了所有天气预警："
                j: Job
                for j in util.get_jobs():
                    real_id = j.id.split(":")[-1]
                    args = real_id.split("/")
                    if args[0] == "weather_alert" and args[1] == util.get_identity(context, const.GROUP):
                        result += "\n" + args[-1]
                        j.remove()

                await bot.send(context, result)
                return True

            else:
                msg = msg.replace("天气", "")
                msg = msg.replace(" ", "")
                msg = msg.replace("\t", "")
                msg = msg.replace("\n", "")
                msg = msg.replace("预警", "")
                msg = msg.strip()

                location_msg = msg
                
                location = await cls.get_location_from_msg(location_msg, extras)

                if location is None:
                    await bot.send(context, "获取地理位置无结果：" + extras["_error"])
                    return True

                jobcall = util.make_jobcall(cls.check_alert_update, context, location)
                job_id = "weather_alert/%s/%s" % (util.get_identity(context, const.GROUP), location["name"].replace("/", ""))
                
                try:
                    util.add_job(jobcall, trigger=IntervalTrigger(minutes=10), id=job_id)
                except ConflictingIdError:
                    await bot.send(context, "设置提醒 %s 的天气预警：失败：已有这个任务" % (location["name"]))
                    return True

                await bot.send(context, "设置提醒 %s 的天气预警：成功" % (location["name"]))
                return True

        return False


    @classmethod
    def all_state_function_list(cls, base_priority):
        return [
            Interceptor(base_priority, cls.query_weather, const.TYPE_RULE_MSG_ONLY, {
                "weather_location": InputVarAttribute(json.dumps(priv_config.DEFAULT_LOCATION), const.GROUP)
            }, {}, None),
            Interceptor(base_priority + 1, cls.add_weather_job, const.TYPE_RULE_MSG_ONLY, {}, {}, None),
            Interceptor(base_priority + 2, cls.add_alert_job, const.TYPE_RULE_MSG_ONLY, {}, {}, None),
        ]

module_class = WeatherBotModule