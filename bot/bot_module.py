import collections
import typing
from . import const

class Interceptor(collections.namedtuple("Interceptor", ["priority", "func", "type_rule", "input_vars", "kwargs", "exception_handler"])):

    def accepts(self, context):
        type_rule: typing.Dict = self.type_rule
        accept = True
        k: str
        for k, vals in type_rule.items():
            real_val = context.get(k, "")
            if k.startswith("^"):
                for disallowed_val in vals:
                    if disallowed_val == real_val:
                        accept = False
                        break
            else:
                curr_accept = False
                for allowed_val in vals:
                    if allowed_val == real_val:
                        curr_accept = True
                        break
                if not curr_accept:
                    accept = False
            if not accept:
                break
        return accept

InputVarAttribute = collections.namedtuple("InputVarAttribute", ["default_val", "identity_scope"])

class BotModule(object):
    @classmethod
    async def on_init(cls):
        pass

    @classmethod
    async def prior_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        return False

    @classmethod
    async def idle_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        return False

    @classmethod
    async def all_state_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        return False

    @classmethod
    def state_function_mapping(cls, base_priority):
        return {}

    @classmethod
    def prior_function_list(cls, base_priority):
        if cls.prior_intercept != BotModule.prior_intercept:
            return [
                Interceptor(base_priority, cls.prior_intercept, const.TYPE_RULE_MSG_ONLY, {}, {}, None)
            ]
        return []

    @classmethod
    def idle_function_list(cls, base_priority):
        if cls.idle_intercept != BotModule.idle_intercept:
            return [
                Interceptor(base_priority, cls.idle_intercept, const.TYPE_RULE_MSG_ONLY, {}, {}, None)
            ]
        return []

    @classmethod
    def all_state_function_list(cls, base_priority):
        if cls.all_state_intercept != BotModule.all_state_intercept:
            return [
                Interceptor(base_priority, cls.all_state_intercept, const.TYPE_RULE_MSG_ONLY, {}, {}, None)
            ]
        return []