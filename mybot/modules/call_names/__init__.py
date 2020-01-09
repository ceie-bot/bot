import random

from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const
from ... import util

try:
    from . import config as priv_config
except ImportError:
    from . import config_example as priv_config

class NameCallingBotModule(bot_module.BotModule):
    @classmethod
    async def on_init(cls):
        pass

    @classmethod
    async def all_state_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):

        if util.get_identity(context, const.INDIVIDUAL).strip() != priv_config.SRC:
            return False

        valid = False
        for msg_data in context['message']:
            if msg_data['type'] == 'at':
                if str(msg_data['data']['qq']) == str(context['self_id']):
                    valid = True
                else:
                    valid = False
                    break
            elif msg_data['type'] == 'text':
                pass
            else:
                valid = False
                break

        valid = valid and extras["_msg_filter"] == ""

        if valid:
            await bot.send(context, "[CQ:at,qq=%s] %s" % (priv_config.TARGET, random.choice(priv_config.NAME_CALLING_SENTENCES)))
            return True
        return False

module_class = NameCallingBotModule