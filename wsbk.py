from datetime import datetime, timedelta, timezone

from core import add_percentages, get_cached, make_session, to_flag

ID = "wsbk"
NAME = "WorldSBK"
SHORT = "SBK"
FIRST_SEASON = 2020
PARTICIPANT = "rider"
PARTICIPANTS = "riders"

EVENTS_URL = "https://api.wsbk.pulselive.com/wsbk-events/v1"
RESULTS_URL = "https://api.wsbk.pulselive.com/wsbk-results/v1"
CATEGORY = "SBK"

# Order matters: "bimota by Kawasaki" must match bimota before kawasaki.
BRANDS = ["bimota", "ducati", "bmw", "yamaha", "kawasaki", "honda", "aprilia", "ktm"]

BRAND_COLORS = {
    "ducati": "#E2231A",
    "bimota": "#F2B705",
    "bmw": "#7FC8F8",
    "yamaha": "#2F6BFF",
    "kawasaki": "#6CC24A",
    "honda": "#E8E8E8",
    "aprilia": "#9B5DE5",
    "ktm": "#FF6600",
}

MANUFACTURER_NAMES = {
    "DUCAT": "Ducati",
    "BIMOT": "bimota",
    "BMW": "BMW",
    "YAMAH": "Yamaha",
    "KAWAS": "Kawasaki",
    "HONDA": "Honda",
}

# WorldSBK uses three-letter country codes, some of them in the sports style (POR, NED).
COUNTRY_CODES = {
    "ARG": "AR", "AUS": "AU", "AUT": "AT", "BEL": "BE", "BRA": "BR",
    "CAN": "CA", "CHE": "CH", "SUI": "CH", "CZE": "CZ", "DEU": "DE",
    "GER": "DE", "DNK": "DK", "DEN": "DK", "ESP": "ES", "FIN": "FI",
    "FRA": "FR", "GBR": "GB", "HUN": "HU", "IDN": "ID", "INA": "ID",
    "IND": "IN", "IRL": "IE", "ITA": "IT", "JPN": "JP", "MYS": "MY",
    "MAL": "MY", "NLD": "NL", "NED": "NL", "NZL": "NZ", "POL": "PL",
    "PRT": "PT", "POR": "PT", "QAT": "QA", "RSA": "ZA", "ZAF": "ZA",
    "SMR": "SM", "SWE": "SE", "THA": "TH", "TUR": "TR", "USA": "US",
}

COUNTRY_TIMEZONES = {
    "ARG": "America/Argentina/Buenos_Aires",
    "AUS": "Australia/Melbourne",
    "CZE": "Europe/Prague",
    "DEU": "Europe/Berlin",
    "GER": "Europe/Berlin",
    "ESP": "Europe/Madrid",
    "FRA": "Europe/Paris",
    "GBR": "Europe/London",
    "HUN": "Europe/Budapest",
    "IDN": "Asia/Makassar",
    "INA": "Asia/Makassar",
    "ITA": "Europe/Rome",
    "JPN": "Asia/Tokyo",
    "NED": "Europe/Amsterdam",
    "NLD": "Europe/Amsterdam",
    "POR": "Europe/Lisbon",
    "PRT": "Europe/Lisbon",
    "QAT": "Asia/Qatar",
    "TUR": "Europe/Istanbul",
    "USA": "America/Los_Angeles",
}

STATUS_LABELS = {"Retired": "DNF", "Disqualified": "DSQ", "Not Started": "DNS"}

RACES = {"RC1": "Race 1", "SPRC": "Superpole Race", "RC2": "Race 2"}

# The API gives no points per race, so they are calculated from the official scale.
FULL_RACE_POINTS = [25, 20, 16, 13, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
RACE_POINTS = {
    "RC1": FULL_RACE_POINTS,
    "SPRC": [12, 9, 7, 6, 5, 4, 3, 2, 1],
    "RC2": FULL_RACE_POINTS,
}
PODIUM_ORDER = [("SP", "Superpole"), ("RC1", "Race 1"), ("SPRC", "Superpole Race"), ("RC2", "Race 2")]


def max_age_for(season):
    if season < datetime.now().year:
        return timedelta(hours=24)
    return timedelta(minutes=30)


def flag_for(iso3):
    return to_flag(COUNTRY_CODES.get(iso3 or "", ""))


def brand_from_name(name):
    lower = (name or "").lower()
    for brand in BRANDS:
        if brand in lower:
            return brand
    return None


def color_for(brand):
    return BRAND_COLORS.get(brand, "#9a9aa8")


# ---------- JSON:API helpers ----------

def index_included(data):
    index = {}
    for item in data.get("included") or []:
        index[(item["type"].rstrip("s"), item["id"])] = item.get("attributes") or {}
    return index


def related_id(row, name):
    link = ((row.get("relationships") or {}).get(name) or {}).get("data") or {}
    return link.get("id")


def related(row, name, index):
    link = ((row.get("relationships") or {}).get(name) or {}).get("data") or {}
    return index.get((link.get("type", "").rstrip("s"), link.get("id")), {})


def model_brands(rows, index):
    brands = {}
    for row in rows:
        brand = brand_from_name(related(row, "team", index).get("name"))
        model = related_id(row, "motorbike_model")
        if brand and model and model not in brands:
            brands[model] = brand
    return brands


def make_rider(row, index, brands):
    rider = related(row, "rider", index)
    team = related(row, "team", index).get("name", "")
    first = rider.get("name", "")
    last = rider.get("surname", "")
    brand = brands.get(related_id(row, "motorbike_model")) or brand_from_name(team)
    return {
        "name": f"{first} {last}".strip(),
        "code": f"{first[:1]}. {last}" if first else last,
        "flag": flag_for(rider.get("country_iso")),
        "team": team,
        "color": color_for(brand),
    }


# ---------- Data fetching ----------

def season_exists(season):
    data = get_cached(f"{EVENTS_URL}/seasons", timedelta(hours=24))
    for item in data.get("data") or []:
        if item.get("id") == str(season):
            return True
    return False


def fetch_rounds(season):
    if not season_exists(season):
        return []
    data = get_cached(f"{EVENTS_URL}/seasons/{season}/rounds", timedelta(hours=1))
    rounds = data.get("data") or []
    return sorted(rounds, key=lambda r: (r.get("attributes") or {}).get("sequence_order") or 0)


def fetch_sessions(season, round_code):
    url = f"{EVENTS_URL}/seasons/{season}/rounds/{round_code}/sessions"
    sessions = []
    for session in get_cached(url, max_age_for(season)).get("data") or []:
        attrs = session.get("attributes") or {}
        if related_id(session, "category") == CATEGORY and attrs.get("start_date_utc"):
            sessions.append(session)
    return sorted(sessions, key=lambda s: s["attributes"]["start_date_utc"])


def fetch_results(season, round_code, session_code):
    url = (f"{RESULTS_URL}/seasons/{season}/categories/{CATEGORY}"
           f"/rounds/{round_code}/sessions/{session_code}/results")
    data = get_cached(url, max_age_for(season))
    rows = sorted(data.get("data") or [], key=lambda r: (r.get("attributes") or {}).get("position") or 999)
    return rows, index_included(data)


def main_race_time(season, round_code):
    last_race = None
    for session in fetch_sessions(season, round_code):
        attrs = session["attributes"]
        if attrs.get("short_name") in RACES:
            last_race = attrs["start_date_utc"]
    return last_race


# ---------- Calendar ----------

def get_races(season):
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    next_found = False
    races = []
    for item in fetch_rounds(season):
        attrs = item.get("attributes") or {}
        iso3 = attrs.get("country_iso", "")
        end = (attrs.get("end_date") or "")[:10]
        main = make_session("Race", end)

        if not next_found and end >= today:
            try:
                race_date = main_race_time(season, attrs.get("source_id"))
            except Exception:
                race_date = None
            if race_date:
                main = make_session("Race", race_date[:10], race_date[11:])
            if main["when"] > now:
                next_found = True

        races.append({
            "round": str(attrs.get("sequence_order", "")),
            "name": (attrs.get("brief_description") or attrs.get("name") or "").strip(),
            "country": attrs.get("name", ""),
            "flag": flag_for(iso3),
            "main": main,
            "tz": COUNTRY_TIMEZONES.get(iso3, ""),
            "sessions": [],
            "lazy": True,
        })
    return races


# ---------- Race results ----------

def format_ms(ms):
    hours, rest = divmod(ms, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, millis = divmod(rest, 1000)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}.{millis:03}"
    if minutes:
        return f"{minutes}:{seconds:02}.{millis:03}"
    return f"{seconds}.{millis:03}"


def make_result_row(row, winner, index, brands, scale):
    result = make_rider(row, index, brands)
    attrs = row.get("attributes") or {}
    first = winner.get("attributes") or {}
    status = attrs.get("status")
    race_time = attrs.get("time")
    laps = attrs.get("laps") or 0
    position = attrs.get("position") or 0
    result["points"] = 0

    if status != "Classified":
        result["position"] = STATUS_LABELS.get(status, "NC")
        result["time"] = status or ""
    else:
        result["position"] = position
        if 0 < position <= len(scale):
            result["points"] = scale[position - 1]
        if row is winner:
            result["time"] = format_ms(race_time) if race_time else ""
        elif laps < (first.get("laps") or 0):
            behind = first["laps"] - laps
            result["time"] = f"+{behind} lap" if behind == 1 else f"+{behind} laps"
        elif race_time and first.get("time"):
            result["time"] = "+" + format_ms(race_time - first["time"])
        else:
            result["time"] = ""
    return result


def get_race_results(season, round_number):
    result = {"sessions": [], "tz": "", "race_top3": [], "full_results": [],
              "sprint_winner": None, "sprint_grid": [], "quali": [],
              "podiums": [], "tables": []}

    round_item = None
    for item in fetch_rounds(season):
        if (item.get("attributes") or {}).get("sequence_order") == round_number:
            round_item = item
    if round_item is None:
        return result

    attrs = round_item["attributes"]
    round_code = attrs["source_id"]
    result["tz"] = COUNTRY_TIMEZONES.get(attrs.get("country_iso", ""), "")

    finished = {}
    for session in fetch_sessions(season, round_code):
        sattrs = session["attributes"]
        label = (sattrs.get("brief_description") or sattrs.get("short_name") or "").strip()
        start = sattrs["start_date_utc"]
        result["sessions"].append(make_session(label, start[:10], start[11:]))
        if sattrs.get("status") == "FINISHED":
            finished[sattrs.get("short_name")] = sattrs.get("source_id")

    for code, label in PODIUM_ORDER:
        if code not in finished:
            continue
        try:
            rows, index = fetch_results(season, round_code, finished[code])
        except Exception:
            continue
        if not rows:
            continue
        brands = model_brands(rows, index)
        classified = []
        for row in rows:
            if (row.get("attributes") or {}).get("status") == "Classified":
                classified.append(row)
        result["podiums"].append({
            "label": label,
            "trophy": code in RACES,
            "rows": [make_rider(row, index, brands) for row in classified[:3]],
        })
        if code in RACES:
            result["tables"].append({
                "label": label,
                "rows": [make_result_row(row, rows[0], index, brands, RACE_POINTS[code]) for row in rows],
            })
    return result


# ---------- Standings ----------

def get_standings(season):
    if not season_exists(season):
        return {"drivers": [], "groups": []}
    max_age = max_age_for(season)

    url = f"{RESULTS_URL}/seasons/{season}/categories/{CATEGORY}/riders/standings"
    data = get_cached(url, max_age)
    rows = data.get("data") or []
    index = index_included(data)
    brands = model_brands(rows, index)
    riders = []
    for row in rows:
        rider = make_rider(row, index, brands)
        attrs = row.get("attributes") or {}
        rider["position"] = attrs.get("position", "")
        rider["points"] = attrs.get("points", 0)
        rider["wins"] = None
        riders.append(rider)

    manufacturers = []
    try:
        url = f"{RESULTS_URL}/seasons/{season}/categories/{CATEGORY}/manufacturers/standings"
        data = get_cached(url, max_age)
        index = index_included(data)
        for row in data.get("data") or []:
            code = related_id(row, "manufacturer") or ""
            name = related(row, "manufacturer", index).get("name") or MANUFACTURER_NAMES.get(code, code)
            attrs = row.get("attributes") or {}
            manufacturers.append({
                "position": attrs.get("position", ""),
                "name": name,
                "color": color_for(brand_from_name(name)),
                "points": attrs.get("points", 0),
                "wins": None,
            })
    except Exception:
        manufacturers = []

    return {
        "drivers": add_percentages(riders),
        "groups": [
            {"title": "manufacturers", "column": "manufacturer", "rows": add_percentages(manufacturers)},
        ],
    }
