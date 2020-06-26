import re

PROXY_GFW = "http://localhost:1082" # http proxy to access ascii2d

BANNED_SETU_TYPE = re.compile(r'.*(pedo).*', re.I)

TELEGRAM_CHANNEL_NAME = 'moeisland' # telegram channel to fetch setu

FETCH_INTERVAL = 30 # interval between fetch, in seconds
SEARCH_INTERVAL = 30 # interval between search, in seconds