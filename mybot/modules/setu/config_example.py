import socks
import re

PROXY_GFW = "http://localhost:1082" # http proxy to access ascii2d
TELEGRAM_PROXY_GFW = (socks.SOCKS5, "localhost", 1080) # socks5 or mtproto proxy to access telegram
TELEGRAM_API_ID = 12345 # telegram api id
TELEGRAM_API_HASH = "ffffffffffffffffffff" # telegram api hash

BANNED_SETU_TYPE = re.compile(r'.*(pedo).*', re.I)

TELEGRAM_CHANNEL_NAME = 'moeisland' # telegram channel to fetch setu

FETCH_INTERVAL = 30 # interval between fetch, in seconds
SEARCH_INTERVAL = 30 # interval between search, in seconds