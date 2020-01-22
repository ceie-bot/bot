import json
import re
import typing
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.job import Job
from apscheduler.jobstores.base import ConflictingIdError

import datetime

from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const
from ... import util
from ... import db


REGEX_NEWS_EXTRACT_JSON = re.compile(r'try\s*\{\s*window\.getTimelineService\s*\=\s*(?P<json>[^\<]*)\}\s*catch\s*\(\s*e\s*\)\s*\{\s*\}')
REGEX_SUMMARY_EXTRACT_JSON = re.compile(r'try\s*\{\s*window\.getListByCountryTypeService1\s*\=\s*(?P<json>[^\<]*)\}\s*catch\s*\(\s*e\s*\)\s*\{\s*\}')

class PneumoniaBotModule(bot_module.BotModule):
    @classmethod
    async def on_init(cls):
        pass

    @classmethod
    def news_obj_to_str(cls, obj):
        return "%s@%s：%s\n%s\n\nfrom%s %s" % (
            datetime.datetime.fromtimestamp(obj["modifyTime"] / 1000, tz=datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
            obj["provinceName"],
            obj["title"],
            obj["summary"],
            obj["infoSource"],
            obj["sourceUrl"],
        )

    @classmethod
    async def check_alert_update(cls, job_id, bot, context):
        data = await util.http_get("https://3g.dxy.cn/newh5/view/pneumonia", timeout_secs=3)
        data = REGEX_NEWS_EXTRACT_JSON.search(data).group("json")
        data = json.loads(data)
        if not "result" in data:
            await bot.send(context, "查询疫情无结果，预警配置错误")
            return

        history_var_name = "pneumonia_alerts_new"
        
        history_alerts = json.loads(db.get_variable(util.get_identity(context, const.GROUP), history_var_name, "[" + str(data['result'][0]["id"]) + "]"))

        result = "有新的疫情动态\n"
        count = 0
        for news_obj in data['result']:
            alert = cls.news_obj_to_str(news_obj)
            alert_spoken = alert in history_alerts
            alert_is_old = news_obj["id"] < history_alerts[-1]
            history_alerts.insert(0, alert)

            if alert_is_old or count >= 5:
                break

            if not alert_spoken:
                result += "\n" + alert
                count += 1

        db.set_variable(util.get_identity(context, const.GROUP), history_var_name, json.dumps(history_alerts))

        if count:
            await bot.send(context, result)
        return


    @classmethod
    async def all_state_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        if u'疫情' in msg and u'提醒' in msg:

            if u'取消' in msg:
                result = "取消了疫情动态。"
                j: Job
                for j in util.get_jobs():
                    real_id = j.id.split(":")[-1]
                    args = real_id.split("/")
                    if args[0] == "pneunomia_alert" and args[1] == util.get_identity(context, const.GROUP):
                        j.remove()

                await bot.send(context, result)
                return True

            else:
                jobcall = util.make_jobcall(cls.check_alert_update, context)
                job_id = "pneunomia_alert/%s" % (util.get_identity(context, const.GROUP))
                
                try:
                    util.add_job(jobcall, trigger=IntervalTrigger(minutes=10), id=job_id)
                except ConflictingIdError:
                    await bot.send(context, "设置开启疫情动态：失败：已有这个任务")
                    return True

                await bot.send(context, "设置开启疫情动态：成功")
                return True

        elif u'疫情' == msg.strip():
            data = await util.http_get("https://3g.dxy.cn/newh5/view/pneumonia")
            summary_data = REGEX_SUMMARY_EXTRACT_JSON.search(data).group("json")
            summary_data = json.loads(summary_data)

            news_data = REGEX_NEWS_EXTRACT_JSON.search(data).group("json")
            news_data = json.loads(news_data)

            if not "result" in news_data:
                await bot.send(context, "查询疫情无结果")
                return

            result = ""

            for region in summary_data:
                result += ("%s：%s\n" % (region["provinceShortName"], region["tags"]))

            result += "\n"

            for i, news_obj in enumerate(news_data["result"][0:5]):
                result += ("%d. " % (i+1)) + news_obj["pubDateStr"] + " - " + news_obj["title"] + "\n"

            await bot.send(context, result.strip())
            return

        return False

module_class = PneumoniaBotModule