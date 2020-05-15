# hello 模块是一个非常简单的模块，它会记住所有和它对话的用户的名字，并且会回复用户的问好。
# 其中用到了：每个模块的 config、全状态的拦截器、变量的读取和写入

# 我们根据当前的目录结构 import 框架内的工具包
from ... import log
from ... import bot_module
from ...bot_module import Interceptor, InputVarAttribute
from ... import const

# 加载当前模块的 config.py 文件作为配置，这个文件需要用户手动创建和配置
# 如果 config.py 不存在，加载 config_example.py。这个文件你现在就可以找到，里面含有默认的配置
# 我们会使用 HELLO_MESSAGE 这个配置项作为打招呼的内容。它的默认值为 "你好"，你可以把它修改为别的值如 "Hello"
try:
    from . import config as priv_config
except ImportError:
    from . import config_example as priv_config

class HelloBotModule(bot_module.BotModule):
    @classmethod
    async def on_init(cls):
        pass

    @classmethod
    async def all_state_intercept(cls, bot, context, msg, input_vars, update_vars, extras, **kwargs):
        # 这个机器人模块会处理这样的消息：
        # - “你好”
        # - “请叫我某某名字”
        # 并给出相应回答。

        # 一般我们用 msg 就够了
        # 你也可以用 extras["_msg_strip"] 得到这句话切除前后空白字符后的字符串
        # 你也可以用 extras["_msg_filter"] 得到这句话去除图片、表情等等富文本元素后的纯文本
        if msg == "你好":
            # 此时用 input_vars["hello_username"] 可以得知对方的名字
            # 在日志里面输出一条 info 级别的日志
            await log.info("I received hello from " + input_vars["hello_username"])
            # 为 extras 字典的 _return 键指定这样格式的值作为返回值
            extras["_return"] = {
                "reply": priv_config.HELLO_MESSAGE  + "，" + input_vars["hello_username"]
            }
            # 使拦截函数返回 True，告诉框架本拦截器的拦截函数已经成功对消息进行了识别和处理，不需要再将消息传给下游的拦截器了
            return True

        if msg.startswith("请叫我"):
            # 将 msg 的前三个字截去，作为对对方的称呼
            new_username = msg[3:]
            # 将对方告知的名字记录到 update_vars 中，稍后框架会将它们更新到数据库里
            update_vars["hello_username", const.INDIVIDUAL] = new_username
            # 输出一条日志。注意我们是怎么从 context 参数中拿到对方的 QQ 号的
            await log.info("I have set " + str(context.get("user_id")) + "'s name to" + new_username)
            # 为 extras 字典的 _return 键指定这样格式的值作为返回值
            extras["_return"] = {
                "reply": "好的，以后我会叫你 " + new_username
            }
            return True

        # 如果消息不符合“你好”和“请叫我”的格式，那么本拦截器的拦截函数没有成功识别和拦截，向框架返回 False
        return False



    # all_state_function_list 是定义“处于任何状态下的拦截器列表”的类方法
    # 它必须返回一个拦截器（Interceptor）列表
    # all_state 的意思是，当前对方处于任何状态（state）的时候，框架都会使用这个模块的拦截器去尝试识别和拦截消息
    # base_priority 是用户在框架的 config.py 中加载本模块时为本模块指定的 state_priority。传进来之后，各个拦截器之间仍可能需要区分优先级，所以各拦截器的 priority 可能会是 base_priority 加上少许偏移后的结果，如 base_priority + 1、base_priority + 2。
    @classmethod
    def all_state_function_list(cls, base_priority):
        return [
            # 我们目前只需要一个拦截器
            Interceptor(
                base_priority, # 拦截器的第一个参数是拦截器的优先级，这里我们直接让它等于 base_priority 就好了。如果我们需要定义第二个优先级稍高于第一个的拦截器，那么它的优先级就可能是 base_priority + 1
                cls.all_state_intercept, # 拦截器函数，实际上就是上面那个。实现了本模块的全部功能。
                const.TYPE_RULE_MSG_ONLY, # 拦截器的消息类型过滤规则。你可以去 const.py 看看 TYPE_RULE_MSG_ONLY 的值：只允许 post_type 为 message（只允许拦截 QQ 消息）、只允许 message_type 为 group 或者 private（只允许群聊或私聊消息）、只允许非 notice 的 sub_type（即不允许拦截系统通知）。不允许拦截的消息类型，不会被本拦截器处理。关于各个 type 的含义，请参考酷Q HTTP 插件的上报事件定义：https://cqhttp.cc/docs/4.15/#/Post
                { # 接下来我们会定义一系列这个拦截器需要从数据库中读取的变量
                    "hello_username": InputVarAttribute("无名氏", const.INDIVIDUAL), # 显然我们只用到 hello_username 这个变量。这个变量的生效范围是“INDIVIDUAL”，即永远跟随某个用户；当对方用户的 hello_username 变量还不存在于数据库中时，我们会为它新建一个变量，设为默认值“无名氏”。
                },
                {}, # 需要传递给拦截器函数的额外 kwargs，我们暂时用不到，直接置为一个空字典
                None, # 自定义拦截器函数发生异常时的异常处理函数，在这里我们暂时用不到，置为 None
            )
        ]

# 注意每一个模块都要将顶层变量 module_class 设为这个模块的相应类 HelloBotModule
module_class = HelloBotModule