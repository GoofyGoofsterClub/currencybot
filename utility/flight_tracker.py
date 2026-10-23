import asyncio
import time

from utility.flightradar import (
    get_flight_list, get_flight_details, pick_flight, is_landed, status_kind,
    get_delay_minutes, format_delay, format_duration, airport_name, airport_coords,
    haversine_km, reverse_geocode,
)

PROGRESS_UPDATE_INTERVAL = 15 * 60  # seconds between "here's where the plane is" posts
DELAY_CHANGE_THRESHOLD = 10  # minutes of delay change before we bother announcing it
LOST_FLIGHT_TIMEOUT = 60 * 60  # stop tracking if the flight vanishes from FR24 for this long
MAX_TRACKING_AGE = 48 * 3600  # stop tracking this long after scheduled departure


def get_live_position(entry):
    """Latest trail point for a live flight, or None."""
    fr24_id = entry["identification"].get("id")
    if not fr24_id:
        return None
    try:
        details = get_flight_details(fr24_id)
    except Exception:
        return None
    trail = details.get("trail") or []
    return trail[0] if trail else None


def describe_position(entry, position, with_place=True):
    lines = []
    destination = entry["airport"]["destination"]
    dest_coords = airport_coords(destination)
    origin_coords = airport_coords(entry["airport"]["origin"])

    if position:
        if with_place:
            place = reverse_geocode(position["lat"], position["lng"])
            lines.append(f"📍 Flying over **{place}**" if place else "🌊 Flying over open water")

        altitude = position.get("alt") or 0
        speed_kmh = round((position.get("spd") or 0) * 1.852)
        lines.append(f"🛩️ Altitude **{altitude:,} ft**, speed **{speed_kmh} km/h**")

        if dest_coords:
            remaining = haversine_km((position["lat"], position["lng"]), dest_coords)
            distance_line = f"📏 **{round(remaining):,} km** to {airport_name(destination)}"
            if origin_coords:
                total = haversine_km(origin_coords, dest_coords)
                if total > 0:
                    done = max(0, min(100, round(100 * (1 - remaining / total))))
                    distance_line += f" ({done}% of the way)"
            lines.append(distance_line)

    return lines


def describe_times(entry):
    t = entry["time"]
    lines = []

    if t["real"]["departure"]:
        lines.append(f"🛫 Departed <t:{t['real']['departure']}:t>")
    elif t["estimated"]["departure"]:
        lines.append(f"🛫 Expected departure <t:{t['estimated']['departure']}:t> (<t:{t['estimated']['departure']}:R>)")
    elif t["scheduled"]["departure"]:
        lines.append(f"🛫 Scheduled departure <t:{t['scheduled']['departure']}:t> (<t:{t['scheduled']['departure']}:R>)")

    arrival = t["real"]["arrival"] or t["estimated"]["arrival"] or t["other"].get("eta")
    if t["real"]["arrival"]:
        lines[0] += f" 🛬 Landed <t:{arrival}:t>"
    elif arrival:
        lines[0] +=  (f" 🛬 Expected arrival <t:{arrival}:t> (<t:{arrival}:R>)")
    elif t["scheduled"]["arrival"]:
        lines[0] +=  (f" 🛬 Scheduled arrival <t:{t['scheduled']['arrival']}:t>")

    lines.append(f"⏱️ {format_delay(get_delay_minutes(entry))}")
    return lines


def flight_header(entry, flight_number):
    origin = airport_name(entry["airport"]["origin"])
    destination = airport_name(entry["airport"]["destination"])
    return f"✈️ **{flight_number}** {origin} → {destination} — *{entry['status']['text']}*"


def build_summary(entry, flight_number, position=None):
    lines = [flight_header(entry, flight_number)]
    lines += describe_position(entry, position)
    lines += describe_times(entry)
    return "\n".join(lines)


async def send(client, tracking, text):
    channel = client.get_channel(tracking["channel_id"])
    if channel is None:
        return False
    await channel.send(text)
    return True


async def process_tracking(client, db, tracking, entries):
    now = int(time.time())
    flight_number = tracking["flight"]
    collection = db["flight_tracking"]
    entry = pick_flight(entries, tracking["scheduled_departure"])

    async def stop(message=None):
        if message:
            await send(client, tracking, message)
        await asyncio.to_thread(collection.delete_one, {"_id": tracking["_id"]})

    if now - tracking["scheduled_departure"] > MAX_TRACKING_AGE:
        return await stop(f"✈️ **{flight_number}**: tracking expired, the flight was scheduled over 48 hours ago.")

    if entry is None:
        lost_since = tracking.get("lost_since") or now
        if now - lost_since > LOST_FLIGHT_TIMEOUT:
            return await stop(f"✈️ **{flight_number}**: lost track of this flight on Flightradar24, stopped tracking.")
        await asyncio.to_thread(collection.update_one, {"_id": tracking["_id"]}, {"$set": {"lost_since": lost_since}})
        return

    updates = {"lost_since": None}
    kind = status_kind(entry)
    delay = get_delay_minutes(entry)

    if kind == "canceled":
        return await stop(f"❌ **{flight_number}** to {airport_name(entry['airport']['destination'])} has been **canceled**.")

    if is_landed(entry):
        arrival = entry["time"]["real"]["arrival"]
        landed_at = f" at <t:{arrival}:t>" if arrival else ""
        destination = entry["airport"]["real"] or entry["airport"]["destination"]
        return await stop(
            f"🛬 **{flight_number}** has landed in {airport_name(destination)}{landed_at} — {format_delay(delay)}.\n"
            f"-# Stopped tracking."
        )

    departed = bool(entry["time"]["real"]["departure"]) or entry["status"]["live"]
    if departed and not tracking.get("departed"):
        updates["departed"] = True
        updates["last_progress"] = now
        updates["last_delay"] = delay
        position = await asyncio.to_thread(get_live_position, entry)
        await send(client, tracking, "\n".join(
            [f"🛫 **{flight_number}** has departed {airport_name(entry['airport']['origin'])}!"]
            + describe_position(entry, position, with_place=False)
            + describe_times(entry)
        ))
    elif departed and now - tracking.get("last_progress", 0) >= PROGRESS_UPDATE_INTERVAL:
        updates["last_progress"] = now
        updates["last_delay"] = delay
        position = await asyncio.to_thread(get_live_position, entry)
        await send(client, tracking, await asyncio.to_thread(build_summary, entry, flight_number, position))
    else:
        last_delay = tracking.get("last_delay")
        if delay is not None and (last_delay is None or abs(delay - last_delay) >= DELAY_CHANGE_THRESHOLD):
            if last_delay is not None or delay >= 15:
                await send(client, tracking, f"⏰ **{flight_number}** is now {format_delay(delay)}.\n" + "\n".join(describe_times(entry)))
            updates["last_delay"] = delay

    if kind == "diverted" and not tracking.get("diverted"):
        updates["diverted"] = True
        await send(client, tracking, f"⚠️ **{flight_number}** has been **diverted**! ({entry['status']['text']})")

    await asyncio.to_thread(collection.update_one, {"_id": tracking["_id"]}, {"$set": updates})


async def process_trackings(client, db):
    trackings = await asyncio.to_thread(lambda: list(db["flight_tracking"].find({})))

    # Several channels can track the same flight, only ask FR24 once per flight
    by_flight = {}
    for tracking in trackings:
        by_flight.setdefault(tracking["flight"], []).append(tracking)

    for flight_number, flight_trackings in by_flight.items():
        try:
            entries = await asyncio.to_thread(get_flight_list, flight_number)
        except Exception as e:
            print(f"Flight tracking: couldn't fetch {flight_number}: {e}")
            continue

        for tracking in flight_trackings:
            try:
                await process_tracking(client, db, tracking, entries)
            except Exception as e:
                print(f"Flight tracking: error processing {flight_number}: {e}")
