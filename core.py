import threading
import time
from datetime import datetime, timedelta, timezone

import requests
from timezonefinder import TimezoneFinder

NATIONALITY_CODES = {
    "British": "GB", "Dutch": "NL", "Monegasque": "MC", "Spanish": "ES",
    "Mexican": "MX", "Australian": "AU", "French": "FR", "German": "DE",
    "Finnish": "FI", "Canadian": "CA", "Thai": "TH", "Japanese": "JP",
    "Danish": "DK", "Chinese": "CN", "American": "US", "Italian": "IT",
    "New Zealander": "NZ", "Argentine": "AR", "Argentinian": "AR",
    "Brazilian": "BR", "Russian": "RU", "Polish": "PL",
    "Austrian": "AT", "Swiss": "CH", "Belgian": "BE", "Indian": "IN",
}

COUNTRY_CODES = {
    "Australia": "AU", "Austria": "AT", "Azerbaijan": "AZ", "Bahrain": "BH",
    "Belgium": "BE", "Brazil": "BR", "Canada": "CA", "China": "CN",
    "France": "FR", "Germany": "DE", "Hungary": "HU", "Italy": "IT",
    "Japan": "JP", "Malaysia": "MY", "Mexico": "MX", "Monaco": "MC",
    "Netherlands": "NL", "Portugal": "PT", "Qatar": "QA", "Russia": "RU",
    "Saudi Arabia": "SA", "Singapore": "SG", "Spain": "ES", "Turkey": "TR",
    "Türkiye": "TR", "UAE": "AE", "UK": "GB", "United Kingdom": "GB",
    "USA": "US", "United States": "US",
}

cache = {}
tf = TimezoneFinder()
rate_lock = threading.Lock()
last_request_at = 0.0
blocked_until = datetime.min


def to_flag(code):
    result = ""
    for letter in code:
        result += chr(0x1F1E6 + ord(letter) - ord("A"))
    return result


def flag_for_nationality(nationality):
    return to_flag(NATIONALITY_CODES.get(nationality, ""))


def flag_for_country(country):
    return to_flag(COUNTRY_CODES.get(country, ""))


def timezone_at(lat, lng):
    return tf.timezone_at(lng=lng, lat=lat) or ""


def wait_for_rate_limit():
    global last_request_at
    with rate_lock:
        elapsed = time.monotonic() - last_request_at
        if elapsed < 0.25:
            time.sleep(0.25 - elapsed)
        last_request_at = time.monotonic()


def get_cached(url, max_age):
    global blocked_until
    cached = cache.get(url)
    if cached is None or datetime.now() - cached["at"] > max_age:
        if datetime.now() < blocked_until:
            if cached is None:
                raise RuntimeError("API rate limit reached, waiting")
            return cached["data"]
        try:
            print(f"Fetching {url}")
            wait_for_rate_limit()
            response = requests.get(url, timeout=10)
            if response.status_code == 429:
                blocked_until = datetime.now() + timedelta(minutes=1)
            response.raise_for_status()
            cache[url] = {"data": response.json(), "at": datetime.now()}
        except requests.RequestException:
            print("API request failed")
            if cached is None:
                raise
    return cache[url]["data"]


def make_session(name, date, time_str=None):
    when = datetime.fromisoformat(date + "T" + (time_str or "23:59:59Z"))
    return {
        "name": name,
        "when": when,
        "utc": when.isoformat(),
        "date": when.strftime("%d/%m/%Y"),
        "tbc": time_str is None,
    }


def add_statuses(races, season):
    now = datetime.now(timezone.utc)
    mark_next = season == now.year
    next_found = False
    for race in races:
        if race["main"]["when"] < now:
            race["status"] = "done" if mark_next else "past"
        elif mark_next and not next_found:
            race["status"] = "next"
            next_found = True
        else:
            race["status"] = "upcoming"
    return races


def add_percentages(rows):
    if not rows:
        return rows
    leader = max(float(row["points"]) for row in rows)
    for row in rows:
        row["pct"] = round(float(row["points"]) / leader * 100, 1) if leader > 0 else 0
    return rows