import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
import requests

TRACK17_API_KEY = os.getenv("TRACK17_API_KEY")
RUSSIANPOST_LOGIN = os.getenv("RUSSIANPOST_LOGIN")
RUSSIANPOST_PASSWORD = os.getenv("RUSSIANPOST_PASSWORD")

TRACK17_URL = "https://api.17track.net/track/v2.4"
RUSSIANPOST_URL = "https://tracking.russianpost.ru/rtm34"

TRACK17_ALREADY_REGISTERED = -18019901
TRACK17_LOOKUP_ATTEMPTS = 4  # 17TRACK fetches carrier data asynchronously after registration
TRACK17_LOOKUP_DELAY = 5  # seconds between attempts

RUSSIANPOST_DELIVERED_OPER_TYPE = "2"  # "Вручение"

PARCEL_NUMBER_REGEX = r"^[A-Z0-9]{8,30}$"

SOURCE_NAMES = {"17track": "17TRACK", "russianpost": "Russian Post"}


def normalize_parcel_number(text):
    number = re.sub(r"[\s\-]", "", text).upper()
    return number if re.match(PARCEL_NUMBER_REGEX, number) else None


def parse_time(value):
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(value).timestamp())
    except ValueError:
        return None


def make_parcel(source, status, delivered, events):
    """Common shape for both services. Events are newest first."""
    events.sort(key=lambda e: e["time"] or 0, reverse=True)
    return {"source": source, "status": status, "delivered": delivered, "events": events}


def event_key(event):
    return f"{event['time']}|{event['description']}"


# 17TRACK

def track17_request(endpoint, payload):
    response = requests.post(
        f"{TRACK17_URL}/{endpoint}",
        json=payload,
        headers={"17token": TRACK17_API_KEY, "Content-Type": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("code") != 0:
        raise RuntimeError(f"17TRACK error {data.get('code')}: {data.get('data')}")
    return data["data"]


def track17_register(numbers):
    data = track17_request("register", [{"number": n} for n in numbers])
    for rejected in data.get("rejected") or []:
        if (rejected.get("error") or {}).get("code") != TRACK17_ALREADY_REGISTERED:
            print(f"17TRACK: couldn't register {rejected.get('number')}: {rejected.get('error')}")


def track17_location(location):
    if isinstance(location, str):
        return location or None
    location = location or {}
    parts = [location.get("city"), location.get("state"), location.get("country")]
    return ", ".join(p for p in parts if p) or None


def track17_parse(item):
    track_info = item.get("track_info") or {}
    status = (track_info.get("latest_status") or {}).get("status") or "NotFound"

    events = []
    for provider in track_info.get("tracking", {}).get("providers") or track_info.get("providers") or []:
        for event in provider.get("events") or []:
            events.append({
                "time": parse_time(event.get("time_iso")),
                "description": event.get("description") or "No description",
                "location": track17_location(event.get("location")),
            })

    if status == "NotFound" and not events:
        return None
    return make_parcel("17track", status, status == "Delivered", events)


def track17_get(numbers):
    """{number: parcel or None} for already registered numbers, up to 40 at a time."""
    data = track17_request("gettrackinfo", [{"number": n} for n in numbers])
    result = {n: None for n in numbers}
    for item in data.get("accepted") or []:
        result[item["number"]] = track17_parse(item)
    return result


def track17_lookup(number):
    track17_register([number])
    for attempt in range(TRACK17_LOOKUP_ATTEMPTS):
        parcel = track17_get([number])[number]
        if parcel:
            return parcel
        if attempt < TRACK17_LOOKUP_ATTEMPTS - 1:
            time.sleep(TRACK17_LOOKUP_DELAY)
    return None


# Russian Post

RUSSIANPOST_REQUEST = """<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:oper="http://russianpost.org/operationhistory" xmlns:data="http://russianpost.org/operationhistory/data">
<soap:Header/>
<soap:Body>
<oper:getOperationHistory>
<data:OperationHistoryRequest>
<data:Barcode>{barcode}</data:Barcode>
<data:MessageType>0</data:MessageType>
<data:Language>ENG</data:Language>
</data:OperationHistoryRequest>
<data:AuthorizationHeader soap:mustUnderstand="1">
<data:login>{login}</data:login>
<data:password>{password}</data:password>
</data:AuthorizationHeader>
</oper:getOperationHistory>
</soap:Body>
</soap:Envelope>"""


def xml_find(element, path):
    """Namespace-agnostic lookup of a slash-separated path of tag names."""
    for name in path.split("/"):
        if element is None:
            return None
        element = next((child for child in element if child.tag.rsplit("}", 1)[-1] == name), None)
    return element


def xml_text(element, path):
    found = xml_find(element, path)
    return found.text.strip() if found is not None and found.text else None


def russianpost_configured():
    return bool(RUSSIANPOST_LOGIN and RUSSIANPOST_PASSWORD)


def russianpost_get(number):
    body = RUSSIANPOST_REQUEST.format(barcode=number, login=RUSSIANPOST_LOGIN, password=RUSSIANPOST_PASSWORD)
    response = requests.post(
        RUSSIANPOST_URL,
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/soap+xml;charset=UTF-8"},
        timeout=20,
    )
    root = ET.fromstring(response.content)
    body = xml_find(root, "Body")

    fault = xml_find(body, "Fault")
    if fault is not None:
        reason = xml_text(fault, "Reason/Text")
        if xml_find(fault, "Detail/AuthorizationFaultReason") is not None:
            raise RuntimeError(f"Russian Post authorization failed: {reason}")
        # Unknown barcodes come back as an OperationHistoryFaultReason
        return None

    history = xml_find(body, "getOperationHistoryResponse/OperationHistoryData")
    records = [r for r in (history if history is not None else []) if r.tag.endswith("historyRecord")]
    if not records:
        return None

    events = []
    delivered = False
    for record in records:
        oper_type = xml_text(record, "OperationParameters/OperType/Id")
        delivered = delivered or oper_type == RUSSIANPOST_DELIVERED_OPER_TYPE
        type_name = xml_text(record, "OperationParameters/OperType/Name")
        attr_name = xml_text(record, "OperationParameters/OperAttr/Name")
        description = " — ".join(p for p in (type_name, attr_name) if p) or "No description"

        place = xml_text(record, "AddressParameters/OperationAddress/Description")
        index = xml_text(record, "AddressParameters/OperationAddress/Index")
        location = f"{place} ({index})" if place and index else place or index

        events.append({
            "time": parse_time(xml_text(record, "OperationParameters/OperDate")),
            "description": description,
            "location": location,
        })

    status = "Delivered" if delivered else events and max(events, key=lambda e: e["time"] or 0)["description"]
    return make_parcel("russianpost", status, delivered, events)


def lookup_parcel(number):
    """Find a parcel on 17TRACK, falling back to Russian Post. None if neither knows it."""
    errors = []
    if TRACK17_API_KEY:
        try:
            parcel = track17_lookup(number)
            if parcel:
                return parcel
        except Exception as e:
            errors.append(f"17TRACK: {e}")

    if russianpost_configured():
        try:
            parcel = russianpost_get(number)
            if parcel:
                return parcel
        except Exception as e:
            errors.append(f"Russian Post: {e}")

    if errors:
        raise RuntimeError("; ".join(errors))
    return None


def describe_event(event):
    when = f"<t:{event['time']}:f>" if event["time"] else "Unknown time"
    where = f" — {event['location']}" if event["location"] else ""
    return f"`{when}` {event['description']}{where}" if not event["time"] else f"{when}: {event['description']}{where}"


def build_parcel_summary(parcel, number, max_events=5):
    status = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", parcel["status"] or "Unknown")
    lines = [f"📦 **{number}** — *{status}* (via {SOURCE_NAMES[parcel['source']]})"]
    lines += [describe_event(e) for e in parcel["events"][:max_events]]
    if len(parcel["events"]) > max_events:
        lines.append(f"-# …and {len(parcel['events']) - max_events} earlier event(s)")
    return "\n".join(lines)
