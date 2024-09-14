import numexpr

async def math(message, args, _globals):
    if len(args) == 1:
        try:
            result = numexpr.evaluate(args[0]).item()
        except:
            await message.reply("Wrong equation.")
            return
        await message.reply(f"`{args[0]} = {result}`")
    else:
        await message.reply('Invalid arguments')