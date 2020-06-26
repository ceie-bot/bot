import os
import json
import aiofiles
import traceback
import time
import datetime

from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const
from ... import util
from ... import db

chat_record_path_format = os.path.join(const.DB_SQLITE_DIR, "record/chat_record_%s.md")
chat_record_map = {}

class RecordBotModule(bot_module.BotModule):
    @classmethod
    async def get_file(cls, identity):
        f = chat_record_map.get(identity)
        filename = chat_record_path_format % identity.replace("#", "G")
        try:
            new_stat = os.stat(filename)
        except FileNotFoundError:
            new_stat = None
        if f is None or new_stat is None or os.fstat(f._file.fileno()) != new_stat:
            f = await aiofiles.open(filename, 'a', encoding='utf-8')
            chat_record_map[identity] = f
        return f

    @classmethod
    async def prior_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        f = await cls.get_file(util.get_identity(context, const.GROUP))
        result = "[" + datetime.datetime.fromtimestamp(context['time']).strftime("%Y-%m-%d %H:%M:%S") + "]"
        if context['post_type'] != 'message':
            result += "<" + context['post_type'].upper() + ">"
            result += repr(context)
        else:
            if not context.get('sender'):
                result += "<" + context['post_type'].upper() + ">"
                result += repr(context)
            else:
                if context['sender'].get('card'):
                    result += " `%s` " % context['sender']['card']
                else:
                    result += " `%s` " % context['sender']['nickname']

                result += "(%s)" % str(context['sender'].get('user_id', "unknown"))
                result += ": "
            
                for msg_data in context['message']:
                    if msg_data['type'] == 'text':
                        result += " `" + msg_data['data']['text'].replace("`", "'") + "` "
                    elif msg_data['type'] == 'image':
                        result += " <a href=\"%(url)s\"><img src=\"%(url)s\" height=\"150\" /></a> " % {"url": msg_data['data']['url']}
                    else:
                        result += " `(%s:%s)` " % (msg_data['type'], repr(msg_data['data']))

        await f.write(result + "\n\n")
        await f.flush()
            
        return False

    @classmethod
    def prior_function_list(cls, base_priority):
        return [
            Interceptor(base_priority, cls.prior_intercept, const.TYPE_RULE_ALL, {}, {}, None)
        ]

module_class = RecordBotModule