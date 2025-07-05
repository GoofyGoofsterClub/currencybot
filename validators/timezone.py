from zoneinfo import ZoneInfo

def is_valid_timezone(tz_str):
    parts = tz_str.split('/')
    region, city = parts
    region = region.capitalize()
    city = '_'.join(word.capitalize() for word in city.split('_'))
    normalized = f"{region}/{city}"
    ZoneInfo(normalized)
