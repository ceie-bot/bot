import json

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
                data = await util.http_get("https://api.caiyunapp.com/v2/%s/%s/weather.json?alert=true" % (priv_config.API_KEY, priv_config.LOCATION))
                data = json.loads(data)
                data = data['result']
                daily = data['daily']
                hourly = data['hourly']
                alert = data['alert']['content']
                rainy_keypoint = data['forecast_keypoint']
                realtime = data['realtime']

                result = ""
                
                # Realtime & Today
                result += "当前气温 " + str(realtime['temperature']) + "°C，"
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

module_class = WeatherBotModule