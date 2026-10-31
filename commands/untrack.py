import asyncio
from utility.command import Command
from utility.flightradar import normalize_flight_number
from utility.parcels import normalize_parcel_number

async def _untrack(message, args, _globals):
    if not args:
        await message.reply("Usage: $untrack <flight number or tracking number>")
        return

    db = _globals['currdb']

    flight_number = normalize_flight_number(args[0])
    flight_query = None
    if flight_number:
        flight_query = {"flight": flight_number}
        if message.guild:
            flight_query["guild_id"] = message.guild.id
        else:
            flight_query["channel_id"] = message.channel.id

    parcel_number = normalize_parcel_number(args[0])
    parcel_query = None
    if parcel_number:
        parcel_query = {"number": parcel_number}
        if message.guild:
            parcel_query["guild_id"] = message.guild.id
        else:
            parcel_query["channel_id"] = message.channel.id

    deleted = 0
    matched_name = None
    if flight_query:
        result = await asyncio.to_thread(db['flight_tracking'].delete_many, flight_query)
        if result.deleted_count:
            deleted += result.deleted_count
            matched_name = flight_number
    if parcel_query:
        result = await asyncio.to_thread(db['parcel_tracking'].delete_many, parcel_query)
        if result.deleted_count:
            deleted += result.deleted_count
            matched_name = parcel_number

    if deleted:
        await message.reply(f"Stopped tracking **{matched_name}**.")
    else:
        await message.reply(f"**{args[0]}** isn't being tracked here.")

command = Command(["untrack"], _untrack)
