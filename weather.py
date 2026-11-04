import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

# Weather for the prediction, from Open-Meteo (free for non-commercial use, no key, credit required).
# - forecast(): will it rain during the next race? (up to 16 days ahead)
# - wet_races(): which earlier races were wet, so we know who is strong in the rain.
#
# This file keeps its own small cache instead of core.get_cached, so a problem with the
# weather service can never block the F1 or MotoGP data.

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HEADERS = {"User-Agent": "Kerbline/1.0 (unofficial motorsport calendar)"}

FORECAST_DAYS = 16
# The archive needs a few days to catch up, so very recent races are skipped.
ARCHIVE_DELAY = timedelta(days=6)
# A race counts as wet when at least this much rain falls during it (mm).
WET_MM = 1.0

cache = {}
cache_lock = threading.Lock()


def fetch(url, params, max_age):
    key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    with cache_lock:
        hit = cache.get(key)
    if hit and datetime.now() - hit["at"] < max_age:
        return hit["data"]
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=8)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        # No weather is fine: the prediction just leaves it out.
        return hit["data"] if hit else None
    with cache_lock:
        cache[key] = {"data": data, "at": datetime.now()}
    return data


def race_hours(data, start):
    # The hours from just before the start until two hours after it.
    hourly = (data or {}).get("hourly") or {}
    times = hourly.get("time") or []
    first = (start - timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")
    last = (start + timedelta(hours=2)).strftime("%Y-%m-%dT%H:00")
    return [i for i, time in enumerate(times) if first <= time <= last], hourly


def forecast(lat, lon, start):
    # {"rain": chance 0..1, "mm": expected rain, "temp": °C} for a race starting at `start` (UTC), or None.
    now = datetime.now(timezone.utc)
    if start < now - timedelta(hours=3) or start > now + timedelta(days=FORECAST_DAYS - 1):
        return None
    day = start.strftime("%Y-%m-%d")
    data = fetch(FORECAST_URL, {
        "latitude": round(lat, 3), "longitude": round(lon, 3), "timezone": "GMT",
        "hourly": "precipitation_probability,precipitation,temperature_2m",
        "start_date": day, "end_date": day,
    }, timedelta(hours=1))
    hours, hourly = race_hours(data, start)
    if not hours:
        return None
    chances = [hourly.get("precipitation_probability", [None] * 99)[i] for i in hours]
    chances = [c for c in chances if c is not None]
    rain = [hourly.get("precipitation", [0] * 99)[i] or 0 for i in hours]
    temps = [hourly.get("temperature_2m", [None] * 99)[i] for i in hours]
    temps = [t for t in temps if t is not None]
    return {
        "rain": (max(chances) / 100) if chances else 0,
        "mm": round(sum(rain), 1),
        "temp": round(sum(temps) / len(temps)) if temps else None,
    }


def was_wet(lat, lon, start):
    # True / False for a race that's over, None if we can't tell.
    if start > datetime.now(timezone.utc) - ARCHIVE_DELAY:
        return None
    day = start.strftime("%Y-%m-%d")
    data = fetch(ARCHIVE_URL, {
        "latitude": round(lat, 3), "longitude": round(lon, 3), "timezone": "GMT",
        "hourly": "precipitation", "start_date": day, "end_date": day,
    }, timedelta(days=30))
    hours, hourly = race_hours(data, start)
    if not hours:
        return None
    return sum(hourly.get("precipitation", [0] * 99)[i] or 0 for i in hours) >= WET_MM


def wet_races(races):
    # races: {key: (lat, lon, start)} -> {key: True/False/None}. Asked 8 at a time, it's much faster.
    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = pool.map(lambda item: (item[0], was_wet(*item[1])), races.items())
        return dict(answers)
