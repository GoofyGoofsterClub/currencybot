import asyncio

async def unremind(message, args, _globals):
    if not args:
        await message.reply(f"Usage: $unremind <reminder_id>")
        return
    
    try:
        await asyncio.to_thread(_globals['currdb']['reminders'].delete_one, {"reminder_id": args[0].upper()})
        await message.reply(f"Deleted reminder with id `{args[0].upper()}`.")
    except:
        await message.reply(f"Couldn't find a reminder with id `{args[0].upper()}`.")