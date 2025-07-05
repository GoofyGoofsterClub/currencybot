import asyncio

SUPPORTED_VARIABLES={
    "timezone": str,
    #"currency": str
}

def validate_type(value, type):
    try:
        type(value)
        return True
    except:
        return False

async def _set(message, args, _globals):
    if len(args) == 1 and args[0].lower() == "list":
        await message.reply(", ".join(SUPPORTED_VARIABLES.keys()))
        return
    if len(args) == 2:
        var = args[0].lower()
        if var in SUPPORTED_VARIABLES:
            if args[1].lower() == "-reset":
                try:
                    await asyncio.to_thread(_globals['currdb']['user_preferences'].update_one,
                        {"user_id": message.author.id},
                        {"$unset": {var: ""}},
                        upsert=True
                    )
                    await message.reply(f"Removed `{var}` for {message.author.mention}")
                except Exception as e:
                    await message.reply(f"An error occurred while processing this request. ({e})")
            elif validate_type(args[1], SUPPORTED_VARIABLES[var]):
                try:
                    await asyncio.to_thread(_globals['currdb']['user_preferences'].update_one,
                        {"user_id": message.author.id},
                        {"$set": {var: args[1]}},
                        upsert=True
                    )
                    await message.reply(f"Set `{var}` for {message.author.mention} to `{args[1]}`")
                except Exception as e:
                    await message.reply(f"An error occurred while processing this request. ({e})")
            else:
                await message.reply(f"Invalid value for `{var}`. Supported values: {', '.join([str(t) for t in SUPPORTED_VARIABLES[var].__args__])}")
        else:
            await message.reply(f"Invalid variable. Supported variables: {', '.join(SUPPORTED_VARIABLES.keys())}")
    else:
        await message.reply('Invalid arguments. Example: $set <variable> <value>')
