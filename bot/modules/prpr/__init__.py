from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const
from ... import util

try:
    from . import config as priv_config
except ImportError:
    from . import config_example as priv_config

class PrprBotModule(bot_module.BotModule):
    @classmethod
    async def on_init(cls):
        pass

    @classmethod
    async def state_func(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        await log.debug("Prpr in state func")

    @classmethod
    async def all_state_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        if extras['_msg_filter'] == r'\prpr':
            await log.info("Received prpr")
            qq = None
            for msg_data in context['message']:
                if msg_data['type'] == 'at':
                    qq = msg_data['data']['qq']

            if str(qq) in priv_config.HATED_PEOPLE:
                return False

            if qq is not None:
                extras.update({"_return": None})
                await bot.send(context, "[CQ:at,qq=%s] Pero pero[CQ:face,id=66]" % str(qq))
            else:
                extras.update({
                    "_return": {
                        "reply": "Pero pero[CQ:face,id=66]",
                        "auto_escape": False
                    }})
            return True
        return False

    @classmethod
    def state_function_mapping(cls, base_priority):
        return {
            "idle": [
                Interceptor(base_priority, cls.state_func, {
                    "post_type": ["message"],
                    "message_type": ["group", "private"],
                    "^sub_type": ["notice"]
                }, {
                    "prpr": InputVarAttribute("nyaa", const.INDIVIDUAL)
                }, {}, None)
            ]
        }

module_class = PrprBotModule