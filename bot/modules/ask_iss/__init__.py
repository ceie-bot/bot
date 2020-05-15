# 这个模块会记录与对方的提问，并根据对方的提问查询国际空间站（ISS）的 API，将结果返回给用户。

# 一个典型的对话：
# 最开始，user 处在 idle （空闲）状态
# user > 查询空间站信息
# bot  > 请选择要查询的信息：
#        1. 当前空间站的位置
#        2. 当前空间站内宇航员的名字 
#        （此时，bot 将 user 的状态置为 ask_iss_choice，表示 user 正在选择查询何种信息，这样本模块就不会再识别“查询空间站信息”了，而是会识别“1”和“2”。状态也是作为一个用户变量持久化存储在数据库里的，这样即使机器人发生错误重启，用户还是能从当前状态中继续）
# user > 1
# bot  > 当前空间站位置为：[经度],[纬度]
#        （此时 bot 会将 user 的状态重设为 idle，允许用户进行后续的提问）
# 因此我们可以发现，在 hello 里的 all_state（任何状态）的拦截器，在这里就不能再使用了。我们将要使用基于状态的拦截器，会通过 state_function_mapping 和 idle_function_list 这两个类方法去定义。
#
# 我们根据当前的目录结构 import 框架内的工具包
import json

from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const
from ... import util

class AskIssModule(bot_module.BotModule):
    @classmethod
    async def on_init(cls):
        pass

    # 这里我们定义一个方法名为 ask_intercept，用来拦截 idle 状态下用户的询问消息
    @classmethod
    async def ask_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        # 我们会在这里拦截“查询空间站信息”这句话
        # 一般我们用 msg 就够了
        # 你也可以用 extras["_msg_strip"] 得到这句话切除前后空白字符后的字符串
        # 你也可以用 extras["_msg_filter"] 得到这句话去除图片、表情等等富文本元素后的纯文本
        if msg == "查询空间站信息":
            # 设置回复消息
            extras["_return"] = {
                "reply": "请选择要查询的信息：\n1. 当前空间站的位置\n2. 当前空间站内宇航员的名字"
            }

            # 状态转换，将用户的 INDIVIDUAL 状态设置为 ask_iss_choice
            update_vars["state", const.INDIVIDUAL] = "ask_iss_choice"

            # 我们成功识别并处理了用户消息，返回 True
            return True

        # 如果并不符合，返回 False
        return False

    #  定义一个方法名为 choice_intercept，用来拦截 ask_iss_choice 状态下用户的选择数字，并根据选择来进行异步 API 查询，向用户返回结果。
    @classmethod
    async def choice_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        # 我们会在这里拦截“1”或者“2”
        if extras["_msg_strip"] == "1":
            # 进行异步的网络请求，用的也是我在 util 里写的便捷函数
            # 你需要会 python 的 asyncio 才能理解这里的 await 的含义
            data = await util.http_get("http://api.open-notify.org/iss-now.json")
            data = json.loads(data)
            return_msg = f'当前空间站经度{data["iss_position"]["longitude"]}，纬度{data["iss_position"]["latitude"]}'

            # 获取到数据后，赋给 extras["_return"]
            extras["_return"] = {
                "reply": return_msg
            }

            # 状态转换，将用户的 INDIVIDUAL 状态重置为 idle
            update_vars["state", const.INDIVIDUAL] = "idle"

            return True

        elif extras["_msg_strip"] == "2":
            data = await util.http_get("http://api.open-notify.org/astros.json")
            data = json.loads(data)
            return_msg = f'当前空间站人员有 {",".join([x["name"] for x in data["people"]])}'

            extras["_return"] = {
                "reply": return_msg
            }

            update_vars["state", const.INDIVIDUAL] = "idle"
            return True

        return False

        

    # all_state_function_list 是定义“处于任何状态下的拦截器列表”的类方法
    # 它必须返回一个拦截器（Interceptor）列表
    # all_state 的意思是，当前对方处于任何状态（state）的时候，框架都会使用这个模块的拦截器去尝试识别和拦截消息
    # 在这里，我们不会在任何状态下都去识别用户的消息；因此我们不定义它


    # idle_function_list 是定义“处于 idle 状态下的拦截器列表”的类方法
    # 它必须返回一个拦截器（Interceptor）列表
    # 只有用户处于 idle（空闲）状态时，才会用这里的拦截器去拦截用户的消息
    # base_priority 是用户在框架的 config.py 中加载本模块时为本模块指定的 state_priority。传进来之后，各个拦截器之间仍可能需要区分优先级，所以各拦截器的 priority 可能会是 base_priority 加上少许偏移后的结果，如 base_priority + 1、base_priority + 2。
    @classmethod
    def idle_function_list(cls, base_priority):
        return [
            Interceptor(
                base_priority, # 拦截器的第一个参数是拦截器的优先级，这里我们直接让它等于 base_priority 就好了。如果我们需要定义第二个优先级稍高于第一个的拦截器，那么它的优先级就可能是 base_priority + 1
                cls.ask_intercept, # 将拦截器的拦截函数设为我们之前写的 ask_intercept
                const.TYPE_RULE_MSG_ONLY, # 拦截器的消息类型过滤规则。你可以去 const.py 看看 TYPE_RULE_MSG_ONLY 的值：只允许 post_type 为 message（只允许拦截 QQ 消息）、只允许 message_type 为 group 或者 private（只允许群聊或私聊消息）、只允许非 notice 的 sub_type（即不允许拦截系统通知）。不允许拦截的消息类型，不会被本拦截器处理。关于各个 type 的含义，请参考酷Q HTTP 插件的上报事件定义：https://cqhttp.cc/docs/4.15/#/Post
                {}, # 在这里，我们除了用户状态以外不会需要读写其他用户变量，所以 input_Vars 直接置为空字典
                {}, # 需要传递给拦截器函数的额外 kwargs，我们暂时用不到，直接置为一个空字典
                None, # 自定义拦截器函数发生异常时的异常处理函数，在这里我们暂时用不到，置为 None
            )
        ]

    # state_function_mapping 是定义“处于哪种状态下时使用哪些拦截器”的类方法
    # 它必须返回一个字典，字典的键是一个字符串，表示“哪种状态”，值是一个拦截器列表。表示“哪些拦截器”
    # base_priority 是用户在框架的 config.py 中加载本模块时为本模块指定的 state_priority。传进来之后，各个拦截器之间仍可能需要区分优先级，所以各拦截器的 priority 可能会是 base_priority 加上少许偏移后的结果，如 base_priority + 1、base_priority + 2。
    @classmethod
    def state_function_mapping(cls, base_priority):
        return { # 注意状态的命名要全局唯一，所以最好在状态命名的开头附上当前模块的名字
            "ask_iss_choice": [
                Interceptor(
                    base_priority,
                    cls.choice_intercept, # 处于ask_iss_choice 状态时，就要用 choice_intercept 方法去拦截用户消息
                    const.TYPE_RULE_MSG_ONLY, # 我们同样只允许“群聊或私聊消息”
                    {},
                    {},
                    None, # 我们同样没有除了用户状态之外的用户变量、kwargs、自定义异常处理函数，这样设置即可
                )
            ],
        }

# 注意每一个模块都要将顶层变量 module_class 设为这个模块的相应类 AskIssModule
module_class = AskIssModule