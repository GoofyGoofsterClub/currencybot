import numexpr

async def math(message, args, _globals):
    if len(args) >= 1:
        try:
            result = numexpr.evaluate(''.join(args)).item()
        except:
            await message.reply("Wrong equation.")
            return
        await message.reply(f"`{''.join(args)} = {result}`")
    else:
        await message.reply('Invalid arguments')