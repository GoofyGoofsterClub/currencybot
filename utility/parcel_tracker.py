import asyncio
import re
import time

from utility import track17_web
from utility.parcels import build_parcel_summary, describe_event, event_key

LOST_PARCEL_TIMEOUT = 60 * 60         # stop tracking if 17TRACK returns no data for this long
MAX_TRACKING_AGE = 30 * 24 * 3600     # stop tracking 30 days after registration
CAPTCHA_RESEND_INTERVAL = 30 * 60     # don't re-post a captcha challenge to a channel more often than this
TERMINAL_STATUSES = {"Delivered", "Canceled", "Cancelled"}


def _format_status(status):
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", status or "Unknown")


def _update_summary(parcel, number, new_events, max_events=5):
    lines = [f"📦 **{number}** — *{_format_status(parcel['status'])}* (via 17TRACK)"]
    lines += [describe_event(e) for e in new_events[:max_events]]
    if len(new_events) > max_events:
        lines.append(f"-# …and {len(new_events) - max_events} earlier event(s)")
    return "\n".join(lines)


async def send(client, tracking, text):
    channel = client.get_channel(tracking["channel_id"])
    if channel is None:
        return False
    await channel.send(text)
    return True


async def _maybe_send_captcha(client, db, tracking, challenge):
    """Ask the tracking channel's owner's channel to solve the captcha. One
    challenge per channel per CAPTCHA_RESEND_INTERVAL; the answer clears the
    whole session, so subsequent parcels fetch normally."""
    now = time.time()
    last_sent = tracking.get("captcha_sent_at") or 0
    if now - last_sent < CAPTCHA_RESEND_INTERVAL:
        return
    from commands.track import PENDING_CAPTCHAS, CAPTCHA_TTL
    pending = PENDING_CAPTCHAS.get(tracking["channel_id"])
    if pending:
        if time.time() - pending["created_at"] > CAPTCHA_TTL:
            # The user never answered; the entry only expires on their next
            # message, so clear it here to allow a fresh challenge.
            del PENDING_CAPTCHAS[tracking["channel_id"]]
        else:
            # Another parcel in this channel already has a challenge out.
            await asyncio.to_thread(
                db["parcel_tracking"].update_one,
                {"_id": tracking["_id"]},
                {"$set": {"captcha_sent_at": now}},
            )
            return
    import io
    import discord
    files = []
    if challenge["prompt"]:
        files.append(discord.File(io.BytesIO(challenge["prompt"]), filename="prompt.jpg"))
    for option in challenge["options"]:
        files.append(discord.File(io.BytesIO(option["image"]), filename=f"option_{option['index'] + 1}.jpg"))
    numbered = "\n".join(f"{o['index'] + 1}. option_{o['index'] + 1}.jpg" for o in challenge["options"])
    channel = client.get_channel(tracking["channel_id"])
    if channel is None:
        return
    text = (
        f"📦 17TRACK wants a captcha before it will show **{tracking['number']}**.\n"
        f"The first image is the prompt — reply with the number(s) of the matching option(s), "
        f"e.g. `3` or `2,7`. The challenge expires in {CAPTCHA_TTL // 60} minutes.\n"
        f"{numbered}"
    )
    await channel.send(text, files=files)
    PENDING_CAPTCHAS[tracking["channel_id"]] = {
        "number": tracking["number"],
        "captcha_id": challenge["captcha_id"],
        "option_keys": [o["key"] for o in challenge["options"]],
        "author_id": tracking.get("creator_id") or 0,
        "created_at": challenge["created_at"],
    }
    await asyncio.to_thread(
        db["parcel_tracking"].update_one,
        {"_id": tracking["_id"]},
        {"$set": {"captcha_sent_at": now}},
    )


async def process_parcel_tracking(client, db, tracking, kind, payload):
    now = int(time.time())
    number = tracking["number"]
    collection = db["parcel_tracking"]

    async def stop(message=None):
        if message:
            await send(client, tracking, message)
        await asyncio.to_thread(collection.delete_one, {"_id": tracking["_id"]})

    if now - tracking["created_at"] > MAX_TRACKING_AGE:
        return await stop(f"📦 **{number}**: tracking expired after 30 days.")

    if kind == "captcha":
        return await _maybe_send_captcha(client, db, tracking, payload)

    if kind != "ok":
        # Network and other errors: retry silently next cycle. A missing number
        # counts as "lost" for LOST_PARCEL_TIMEOUT.
        if "no tracking data" in payload:
            lost_since = tracking.get("lost_since") or now
            if now - lost_since > LOST_PARCEL_TIMEOUT:
                return await stop(f"📦 **{number}**: 17TRACK stopped returning data, stopped tracking.")
            if lost_since != tracking.get("lost_since"):
                await asyncio.to_thread(
                    collection.update_one, {"_id": tracking["_id"]}, {"$set": {"lost_since": lost_since}}
                )
        return

    parcel = payload
    events = parcel.get("events") or []
    latest = events[0] if events else None
    latest_key = event_key(latest) if latest else None
    status = parcel["status"]

    if status in TERMINAL_STATUSES:
        lines = [f"📦 **{number}** has been **{_format_status(status)}**."]
        if latest:
            lines.append(describe_event(latest))
        return await stop("\n".join(lines))

    if not latest_key or latest_key == tracking.get("last_event_key"):
        if tracking.get("lost_since"):
            await asyncio.to_thread(
                collection.update_one, {"_id": tracking["_id"]}, {"$set": {"lost_since": None}}
            )
        return

    new_events = [e for e in events if event_key(e) != tracking.get("last_event_key")]
    await send(client, tracking, _update_summary(parcel, number, new_events))
    await asyncio.to_thread(
        collection.update_one,
        {"_id": tracking["_id"]},
        {"$set": {
            "last_event_key": latest_key,
            "last_status": status,
            "lost_since": None,
            "captcha_sent_at": None,
        }},
    )


async def process_parcel_trackings(client, db):
    trackings = await asyncio.to_thread(lambda: list(db["parcel_tracking"].find({})))

    # Several channels can track the same number; only ask 17TRACK once per number.
    by_number = {}
    for tracking in trackings:
        by_number.setdefault(tracking["number"], []).append(tracking)

    for number, parcel_trackings in by_number.items():
        try:
            kind, payload = await asyncio.to_thread(track17_web.track_parcel, number)
        except Exception as e:
            print(f"Parcel tracking: couldn't fetch {number}: {e}")
            continue

        for tracking in parcel_trackings:
            try:
                await process_parcel_tracking(client, db, tracking, kind, payload)
            except Exception as e:
                print(f"Parcel tracking: error processing {number}: {e}")


async def refresh_tracking_state(number, parcel):
    """After a captcha answer succeeds: record the latest event/status so the
    periodic loop doesn't re-post what the answer already showed."""
    from bot import currdb
    latest = (parcel.get("events") or [None])[0]
    last_event_key = event_key(latest) if latest else None
    await asyncio.to_thread(
        currdb["parcel_tracking"].update_many,
        {"number": number},
        {"$set": {
            "last_event_key": last_event_key,
            "last_status": parcel["status"],
            "lost_since": None,
            "captcha_sent_at": None,
        }},
    )
