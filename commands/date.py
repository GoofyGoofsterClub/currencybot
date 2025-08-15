import dateparser
from datetime import datetime
from utility.command import Command

async def date(message, args, _globals):
    if len(args) >= 1:
        try:
            arg = dateparser.parse(''.join(args))
        except:
            await message.reply("Wrong date.")
            return
        await message.reply(f"`{arg.strftime('%m/%d/%Y, %H:%M:%S')}` (<t:{int(arg.timestamp())}:R>)")
    else:
        await message.reply('Invalid arguments')

command = Command(["date", "d"], date)