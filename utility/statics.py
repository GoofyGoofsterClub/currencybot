import os

CURRENCYREGEX = r"(\d+\.?\d*)(k*)? ?(\w+)"
NUMBERREGEX = r"(\d+\.?\d*)(k*)?"
ENVRATE = os.getenv("DEFAULT_CURRENCY").split(',')
ENVTOKEN = os.getenv('DISCORD_TOKEN')
ENVPREFIX = os.getenv('BOT_PREFIX')
