from telethon import TelegramClient

from ... import log
from ... import bot_module

try:
    from . import config as priv_config
except ImportError:
    from . import config_example as priv_config

client: TelegramClient = None

class TelegramBotModule(bot_module.BotModule):
    @classmethod
    async def on_init(cls):
        global client
        await log.info("initializing Telegram client...")
        client = TelegramClient('bot_tg_bot', priv_config.TELEGRAM_API_ID, priv_config.TELEGRAM_API_HASH, proxy=priv_config.TELEGRAM_PROXY_GFW, timeout=3)
        await client.start()
        await log.info("initializing Telegram client done.")

module_class = TelegramBotModule