import asyncio
import time
from utility.command import Command
from utility.flightradar import normalize_flight_number, get_flight_list, pick_flight, get_delay_minutes
from utility.flight_tracker import get_live_position, build_summary

async def _track(message, args, _globals):
    collection = _globals['currdb']['flight_tracking']

    if not args:
        query = {"guild_id": message.guild.id} if message.guild else {"channel_id": message.channel.id}
        trackings = await asyncio.to_thread(lambda: list(collection.find(query)))
        tracked = "\n".join(f"- **{t['flight']}** in <#{t['channel_id']}>" for t in trackings) or "Nothing is being tracked."
        await message.reply(f"Usage: $track <flight number> [#channel]\n\n{tracked}")
        return

    flight_number = normalize_flight_number(args[0])
    if not flight_number:
        await message.reply(f"`{args[0]}` doesn't look like a flight number (e.g. `SK1415`).")
        return

    channel = message.channel
    if len(args) > 1:
        if not message.channel_mentions:
            await message.reply("Please mention the channel to post updates in, e.g. `#flights`.")
            return
        channel = message.channel_mentions[0]
        if not message.guild or channel.guild.id != message.guild.id:
            await message.reply("That channel isn't in this server.")
            return
        if not channel.permissions_for(message.guild.me).send_messages:
            await message.reply(f"I can't send messages in <#{channel.id}>.")
            return

    try:
        entries = await asyncio.to_thread(get_flight_list, flight_number)
    except Exception as e:
        await message.reply(f"Couldn't reach Flightradar24. ({e})")
        return

    entry = pick_flight(entries)
    if entry is None:
        await message.reply(f"Couldn't find an upcoming or active flight **{flight_number}**.")
        return

    scheduled_departure = entry["time"]["scheduled"]["departure"]
    existing = await asyncio.to_thread(collection.find_one, {
        "flight": flight_number, "channel_id": channel.id, "scheduled_departure": scheduled_departure
    })
    departed = bool(entry["time"]["real"]["departure"]) or entry["status"]["live"]
    if existing:
        position = await asyncio.to_thread(get_live_position, entry) if departed else None
        summary = await asyncio.to_thread(build_summary, entry, flight_number, position)
        await message.reply(f"**{flight_number}** is already being tracked in <#{channel.id}>.\n\n{summary}")
        return

    await asyncio.to_thread(collection.insert_one, {
        "flight": flight_number,
        "scheduled_departure": scheduled_departure,
        "channel_id": channel.id,
        "guild_id": message.guild.id if message.guild else None,
        "creator_id": message.author.id,
        "created_at": int(time.time()),
        "departed": departed,
        "last_progress": int(time.time()),
        "last_delay": get_delay_minutes(entry),
    })

    position = await asyncio.to_thread(get_live_position, entry) if departed else None
    summary = await asyncio.to_thread(build_summary, entry, flight_number, position)
    where = "" if channel.id == message.channel.id else f" in <#{channel.id}>"
    await message.reply(f"Now tracking **{flight_number}**{where}. Untrack with `$untrack {flight_number}`.\n\n{summary}")

command = Command(["track"], _track)
