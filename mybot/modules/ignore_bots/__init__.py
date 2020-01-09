
from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const
from ... import util
from ... import db

class IgnoreBotsBotModule(bot_module.BotModule):

    @classmethod
    async def prior_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):

        sender = context.get('sender', {})
        card = sender.get('card', sender.get('nickname', ''))
        if u'bot' in card:
            return True

        return False

module_class = IgnoreBotsBotModule