import json
import re

from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const
from ... import util

try:
    from . import config as priv_config
except ImportError:
    from . import config_example as priv_config

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

class WeatherBotModule(bot_module.BotModule):
    @classmethod
    async def on_init(cls):
        pass

    @classmethod
    def wind_direction(cls, degree):
        return WIND_LIST[int((degree + 22.5) % 360 / 45)]

    @classmethod
    async def all_state_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        if u'天气' in msg:
            if u'查询' in msg or (u'怎' in msg):
                msg = msg.replace("天", "")
                msg = msg.replace("气", "")
                msg = msg.replace(" ", "")
                msg = msg.replace("\t", "")
                msg = msg.replace("\n", "")
                msg = msg.replace("怎", "")
                msg = msg.replace("么", "")
                msg = msg.replace("样", "")
                msg = msg.replace("今", "")
                msg = msg.replace("明", "")
                msg = msg.replace("查询", "")
                msg = msg.strip()

                location = json.loads(input_vars["weather_location"])
                if msg != "":
                    m = re.fullmatch(REGEX_LNG_LAT, msg)
                    if m:
                        location = {
                            "name": msg,
                            "lng": float(m.group("lng")),
                            "lat": float(m.group("lat")),
                        }
                        update_vars["weather_location", const.GROUP] = json.dumps(location)
                    else:
                        data = await util.http_get("https://apis.map.qq.com/ws/geocoder/v1/", params={
                            "address": msg,
                            "key": "FBOBZ-VODWU-C7SVF-B2BDI-UK3JE-YBFUS"
                        }, headers={
                            "Referer": "http://www.gpsspg.com"
                        }, timeout_secs=3)
                        # await log.info(data)
                        data = json.loads(data)
                        if not "result" in data:
                            await bot.send(context, "查询位置无结果")
                            return True
                            
                        location = {
                            "name": data["result"]["title"],
                            "lng": data["result"]["location"]["lng"],
                            "lat": data["result"]["location"]["lat"],
                        }
                        update_vars["weather_location", const.GROUP] = json.dumps(location)

                data = await util.http_get("https://api.caiyunapp.com/v2/%s/%lg,%lg/weather.json?alert=true" % (priv_config.API_KEY, location["lng"], location["lat"]))
                data = json.loads(data)
                if not "result" in data:
                    await bot.send(context, "查询天气无结果")
                    return True
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
                return True
        return False

    @classmethod
    def all_state_function_list(cls, base_priority):
        return [
            Interceptor(base_priority, cls.all_state_intercept, const.TYPE_RULE_MSG_ONLY, {
                "weather_location": InputVarAttribute(json.dumps(priv_config.DEFAULT_LOCATION), const.GROUP)
            }, {}, None)
        ]

module_class = WeatherBotModule