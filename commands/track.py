import asyncio
import io
import re
import time

import discord
from utility.command import Command
from utility.flightradar import normalize_flight_number, get_flight_list, pick_flight, get_delay_minutes
from utility.flight_tracker import get_live_position, build_summary
from utility import track17_web
from utility.parcels import event_key

# Pending 17TRACK captcha challenges: channel_id -> entry.
PENDING_CAPTCHAS = {}
CAPTCHA_TTL = 600  # seconds the challenge stays answerable


async def _track(message, args, _globals):
    if not args:
        collection = _globals["currdb"]["flight_tracking"]
        query = {"guild_id": message.guild.id} if message.guild else {"channel_id": message.channel.id}
        trackings = await asyncio.to_thread(lambda: list(collection.find(query)))
        tracked = "\n".join(f"- **{t['flight']}** in <#{t['channel_id']}>" for t in trackings) or "Nothing is being tracked."
        parcel_query = {"guild_id": message.guild.id} if message.guild else {"channel_id": message.channel.id}
        parcels = await asyncio.to_thread(
            lambda: list(_globals["currdb"]["parcel_tracking"].find(parcel_query))
        )
        tracked_parcels = "\n".join(f"- 📦 **{t['number']}** in <#{t['channel_id']}>" for t in parcels)
        await message.reply(
            "Usage:\n"
            "$track flight <flight number> [#channel] — start following a flight\n"
            "$track parcel <tracking number> — follow a parcel on 17TRACK until it's delivered\n\n"
            f"{tracked}"
            + (f"\n{tracked_parcels}" if parcels else "")
        )
        return

    sub, rest = args[0], args[1:]
    if sub == "flight":
        await _track_flight(message, rest, _globals)
    elif sub == "parcel":
        await _track_parcel(message, rest, _globals)
    else:
        # Backwards compatible: a bare argument is treated as a flight number.
        await _track_flight(message, args, _globals)


async def _track_flight(message, args, _globals):
    collection = _globals["currdb"]["flight_tracking"]

    if not args:
        await message.reply("Usage: $track flight <flight number> [#channel]")
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
        await message.reply(f"**{flight_number}** is already being tracked in <#{channel.id}>\n\n{summary}")
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


# ---- parcels (17TRACK public web, no account) ----

async def _send_captcha_challenge(message, number, challenge):
    files = []
    if challenge["prompt"]:
        files.append(discord.File(io.BytesIO(challenge["prompt"]), filename="prompt.jpg"))
    for option in challenge["options"]:
        files.append(discord.File(io.BytesIO(option["image"]), filename=f"option_{option['index'] + 1}.jpg"))
    numbered = "\n".join(f"{o['index'] + 1}. option_{o['index'] + 1}.jpg" for o in challenge["options"])
    text = (
        f"📦 17TRACK wants a captcha before it will show **{number}**.\n"
        f"The first image is the prompt — reply with the number(s) of the matching option(s), "
        f"e.g. `3` or `2,7`. The challenge expires in {CAPTCHA_TTL // 60} minutes.\n"
        f"{numbered}"
    )
    await message.reply(text, files=files)
    PENDING_CAPTCHAS[message.channel.id] = {
        "number": number,
        "captcha_id": challenge["captcha_id"],
        "option_keys": [o["key"] for o in challenge["options"]],
        "author_id": message.author.id,
        "created_at": challenge["created_at"],
    }


async def _track_parcel(message, args, _globals):
    number = " ".join(args)
    if not number:
        await message.reply("Usage: $track parcel <tracking number>")
        return
    normalized = track17_web.normalize_parcel_number(number)
    if not normalized:
        await message.reply(f"`{args[0]}` doesn't look like a tracking number (e.g. `EE251189354SE`).")
        return

    collection = _globals["currdb"]["parcel_tracking"]
    existing = await asyncio.to_thread(collection.find_one, {
        "number": normalized,
        "channel_id": message.channel.id,
    })
    if existing:
        kind, payload = await asyncio.to_thread(track17_web.track_parcel, normalized)
        if kind == "ok":
            await message.reply(
                f"📦 **{normalized}** is already being tracked here.\n\n"
                + track17_web.build_parcel_summary(payload, normalized)
            )
        else:
            await message.reply(f"📦 **{normalized}** is already being tracked here ({payload})")
        return

    PENDING_CAPTCHAS.pop(message.channel.id, None)
    kind, payload = await asyncio.to_thread(track17_web.track_parcel, normalized)
    if kind == "ok":
        await message.reply(
            f"Now tracking 📦 **{normalized}** — I'll post here when 17TRACK has new events, "
            f"until it's delivered. Untrack with `$untrack {normalized}`.\n\n"
            + track17_web.build_parcel_summary(payload, normalized)
        )
        latest = (payload.get("events") or [None])[0]
        last_event_key = event_key(latest) if latest else None
        await asyncio.to_thread(collection.insert_one, {
            "number": normalized,
            "channel_id": message.channel.id,
            "guild_id": message.guild.id if message.guild else None,
            "creator_id": message.author.id,
            "created_at": int(time.time()),
            "last_event_key": last_event_key,
            "last_status": payload["status"],
            "lost_since": None,
            "captcha_sent_at": None,
        })
    elif kind == "captcha":
        await _send_captcha_challenge(message, normalized, payload)
        await asyncio.to_thread(collection.insert_one, {
            "number": normalized,
            "channel_id": message.channel.id,
            "guild_id": message.guild.id if message.guild else None,
            "creator_id": message.author.id,
            "created_at": int(time.time()),
            "last_event_key": None,
            "last_status": None,
            "lost_since": None,
            "captcha_sent_at": None,
        })
    else:
        await message.reply(payload)


def _parse_selection(content):
    """Numbers 1-9 from a message like '3', '2,7', '2 and 7'."""
    return sorted({int(n) for n in re.findall(r"\b[1-9]\b", content)})


async def check_pending_captcha(message):
    """Call from on_message for non-command messages. Handles the user's answer
    to a pending 17TRACK captcha; True when the message was consumed."""
    entry = PENDING_CAPTCHAS.get(message.channel.id)
    if not entry:
        return False
    if entry["author_id"] != message.author.id or time.time() - entry["created_at"] > CAPTCHA_TTL:
        PENDING_CAPTCHAS.pop(message.channel.id, None)
        return False

    selected = _parse_selection(message.content)
    if not selected or any(i > 9 for i in selected):
        await message.reply(f"Reply with the number(s) of the matching option(s), e.g. `3` or `2,7`.")
        return True

    keys = _pending_option_keys(message.channel.id, selected)
    kind, payload = await asyncio.to_thread(
        track17_web.track_parcel_after_captcha, entry["number"], entry["captcha_id"], keys
    )
    if kind == "ok":
        PENDING_CAPTCHAS.pop(message.channel.id, None)
        await message.reply(track17_web.build_parcel_summary(payload, entry["number"]))
        try:
            from utility.parcel_tracker import refresh_tracking_state
            await refresh_tracking_state(entry["number"], payload)
        except Exception:
            pass
    elif kind == "captcha":
        await _send_captcha_challenge(message, entry["number"], payload)
    else:
        if "wasn't accepted" in payload:
            # Offer a fresh challenge rather than dropping the state.
            PENDING_CAPTCHAS.pop(message.channel.id, None)
        await message.reply(payload)
    return True


def _pending_option_keys(channel_id, selected):
    entry = PENDING_CAPTCHAS.get(channel_id) or {}
    keys = entry.get("option_keys") or []
    return [keys[i - 1] for i in selected if 1 <= i <= len(keys)]


command = Command(["track"], _track)
