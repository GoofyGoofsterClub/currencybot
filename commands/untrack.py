import asyncio
from utility.command import Command
from utility.flightradar import normalize_flight_number

async def _untrack(message, args, _globals):
    if not args:
        await message.reply("Usage: $untrack <flight number>")
        return

    flight_number = normalize_flight_number(args[0]) or args[0].upper()
    query = {"flight": flight_number}
    if message.guild:
        query["guild_id"] = message.guild.id
    else:
        query["channel_id"] = message.channel.id

    result = await asyncio.to_thread(_globals['currdb']['flight_tracking'].delete_many, query)
    if result.deleted_count:
        await message.reply(f"Stopped tracking **{flight_number}**.")
    else:
        await message.reply(f"**{flight_number}** isn't being tracked here.")

command = Command(["untrack"], _untrack)
