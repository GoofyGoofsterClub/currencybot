import math
import re
import time
import requests

FR24_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "application/json",
}
NOMINATIM_HEADERS = {
    "User-Agent": "currencybot-flighttracker (+https://github.com/GoofyGoofsterClub/currencybot)",
}

FLIGHT_LIST_URL = "https://api.flightradar24.com/common/v1/flight/list.json"
FLIGHT_DETAILS_URL = "https://data-live.flightradar24.com/clickhandler/"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

FLIGHT_NUMBER_REGEX = r"^[A-Z0-9]{2,3}\d{1,5}[A-Z]?$"


def normalize_flight_number(text):
    flight = re.sub(r"[\s\-]", "", text).upper()
    return flight if re.match(FLIGHT_NUMBER_REGEX, flight) else None


def get_flight_list(flight_number):
    response = requests.get(
        FLIGHT_LIST_URL,
        params={"query": flight_number, "fetchBy": "flight", "page": 1, "limit": 25},
        headers=FR24_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["result"]["response"]["data"] or []


def get_flight_details(fr24_id):
    response = requests.get(
        FLIGHT_DETAILS_URL,
        params={"flight": fr24_id, "version": "1.5"},
        headers=FR24_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def is_landed(entry):
    return bool(entry["time"]["real"]["arrival"]) or status_kind(entry) == "landed"


def status_kind(entry):
    generic = (entry["status"].get("generic") or {}).get("status") or {}
    return (generic.get("text") or "").lower()


def pick_flight(entries, scheduled_departure=None):
    """Pick the leg we care about: a pinned one if given, otherwise live, otherwise the next one that hasn't landed."""
    if scheduled_departure:
        return next((e for e in entries if e["time"]["scheduled"]["departure"] == scheduled_departure), None)

    live = [e for e in entries if e["status"]["live"]]
    if live:
        return live[0]

    cutoff = time.time() - 6 * 3600
    upcoming = [
        e for e in entries
        if e["time"]["scheduled"]["departure"]
        and e["time"]["scheduled"]["departure"] >= cutoff
        and not is_landed(e)
        and status_kind(e) != "canceled"
    ]
    upcoming.sort(key=lambda e: e["time"]["scheduled"]["departure"])
    return upcoming[0] if upcoming else None


def get_delay_minutes(entry):
    """Positive = late, negative = early, None = unknown."""
    t = entry["time"]
    if t["real"]["arrival"] and t["scheduled"]["arrival"]:
        return round((t["real"]["arrival"] - t["scheduled"]["arrival"]) / 60)

    arrival_estimate = t["estimated"]["arrival"] or t["other"].get("eta")
    if (t["real"]["departure"] or entry["status"]["live"]) and arrival_estimate and t["scheduled"]["arrival"]:
        return round((arrival_estimate - t["scheduled"]["arrival"]) / 60)

    departure = t["real"]["departure"] or t["estimated"]["departure"]
    if departure and t["scheduled"]["departure"]:
        return round((departure - t["scheduled"]["departure"]) / 60)

    return None


def format_delay(delay):
    if delay is None:
        return "no delay info"
    if delay >= 15:
        return f"**delayed {format_duration(delay)}**"
    if delay <= -5:
        return f"{format_duration(-delay)} early"
    return "on time"


def format_duration(minutes):
    hours, mins = divmod(abs(int(minutes)), 60)
    return f"{hours}h {mins}m" if hours else f"{mins}m"


def airport_name(airport):
    if not airport:
        return "Unknown"
    city = (airport.get("position") or {}).get("region", {}).get("city")
    code = (airport.get("code") or {}).get("iata")
    name = city or airport.get("name") or "Unknown"
    return f"{name} ({code})" if code else name


def airport_coords(airport):
    position = (airport or {}).get("position") or {}
    if position.get("latitude") is None:
        return None
    return position["latitude"], position["longitude"]


def haversine_km(a, b):
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def reverse_geocode(lat, lon):
    """Human-readable place below the plane, or None when over water / unknown."""
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "accept-language": "en"},
            headers=NOMINATIM_HEADERS,
            timeout=10,
        )
        data = response.json()
    except Exception:
        return None

    address = data.get("address")
    if not address:
        return None

    place = (
        address.get("city") or address.get("town") or address.get("village")
        or address.get("municipality") or address.get("county")
    )
    parts = [p for p in (place, address.get("state"), address.get("country")) if p]
    # Drop repeats like "Berlin, Berlin, Germany"
    deduped = [p for i, p in enumerate(parts) if p not in parts[:i]]
    return ", ".join(deduped) or None
