from datetime import datetime, timedelta, timezone

from core import add_percentages, get_cached, make_session, to_flag

ID = "motogp"
NAME = "MotoGP"
SHORT = "MGP"
FIRST_SEASON = 2020
PARTICIPANT = "rider"
PARTICIPANTS = "riders"

BASE_URL = "https://api.motogp.pulselive.com/motogp/v1"
WORLD_STANDINGS_URL = "https://api.pulselive.motogp.com/motogp/v2/results/world-standings"

TEAM_COLORS = {
    "ducati": "#E2231A",
    "aprilia": "#9B5DE5",
    "ktm": "#FF6600",
    "honda": "#E8E8E8",
    "yamaha": "#2F6BFF",
}

SESSION_NAMES = {
    "FP": "Free Practice",
    "PR": "Practice",
    "Q": "Qualifying",
    "SPR": "Sprint",
    "WUP": "Warm Up",
    "RAC": "Race",
}

COUNTRY_TIMEZONES = {
    "AR": "America/Argentina/Buenos_Aires",
    "AT": "Europe/Vienna",
    "AU": "Australia/Melbourne",
    "BR": "America/Sao_Paulo",
    "CZ": "Europe/Prague",
    "DE": "Europe/Berlin",
    "ES": "Europe/Madrid",
    "FR": "Europe/Paris",
    "GB": "Europe/London",
    "HU": "Europe/Budapest",
    "ID": "Asia/Makassar",
    "IN": "Asia/Kolkata",
    "IT": "Europe/Rome",
    "JP": "Asia/Tokyo",
    "KZ": "Asia/Almaty",
    "MY": "Asia/Kuala_Lumpur",
    "NL": "Europe/Amsterdam",
    "PT": "Europe/Lisbon",
    "QA": "Asia/Qatar",
    "SM": "Europe/San_Marino",
    "TH": "Asia/Bangkok",
    "TR": "Europe/Istanbul",
    "US": "America/Chicago",
}


def max_age_for(season):
    if season < datetime.now().year:
        return timedelta(hours=24)
    return timedelta(minutes=30)


def team_color(constructor_name):
    return TEAM_COLORS.get(constructor_name.lower(), "#9a9aa8")


def season_id(season):
    seasons = get_cached(f"{BASE_URL}/results/seasons", timedelta(hours=24))
    for item in seasons:
        if item["year"] == season:
            return item["id"]
    return None


def category_id(season_uuid):
    url = f"{BASE_URL}/results/categories?seasonUuid={season_uuid}"
    for category in get_cached(url, timedelta(hours=24)):
        if "MotoGP" in category["name"]:
            return category["id"]
    return None


def pretty_name(name):
    return name.title().replace(" Of ", " of ").replace(" The ", " the ")


def grand_prix_events(season):
    season_uuid = season_id(season)
    if season_uuid is None:
        return []
    events = get_cached(f"{BASE_URL}/results/events?seasonUuid={season_uuid}", timedelta(hours=1))
    grand_prix = []
    for event in events:
        if not event.get("test"):
            grand_prix.append(event)
    grand_prix.sort(key=lambda e: e["date_start"])
    return grand_prix


# ---------- Calendar ----------

def race_session_time(season, event):
    season_uuid = season_id(season)
    category_uuid = category_id(season_uuid)
    url = f"{BASE_URL}/results/sessions?eventUuid={event['id']}&categoryUuid={category_uuid}"
    for session in get_cached(url, max_age_for(season)):
        if session.get("type") == "RAC" and session.get("date"):
            return session["date"]
    return None

def get_races(season):
    today = datetime.now(timezone.utc).date().isoformat()
    next_found = False
    races = []
    for number, event in enumerate(grand_prix_events(season), start=1):
        country = event["country"]
        main = make_session("Race", event["date_end"])

        if not next_found and event["date_end"] >= today:
            try:
                race_date = race_session_time(season, event)
            except Exception:
                race_date = None
            if race_date:
                main = make_session("Race", race_date[:10], race_date[11:])
            if main["when"] > datetime.now(timezone.utc):
                next_found = True

        races.append({
            "round": str(number),
            "name": pretty_name(event["name"]),
            "country": country["name"],
            "flag": to_flag(country["iso"]),
            "main": main,
            "tz": COUNTRY_TIMEZONES.get(country["iso"], ""),
            "sessions": [],
            "lazy": True,
        })
    return races


# ---------- Sessions and results ----------

def session_label(session):
    name = SESSION_NAMES.get(session.get("type"), session.get("type", ""))
    if session.get("number"):
        name += f" {session['number']}"
    return name


def classification(session_id, season):
    if session_id is None:
        return []
    url = f"{BASE_URL}/results/session/{session_id}/classification?test=false"
    return get_cached(url, max_age_for(season)).get("classification", [])


def short_name(full_name):
    parts = full_name.split()
    if len(parts) < 2:
        return full_name
    return parts[0][0] + ". " + parts[-1]


def make_rider(row):
    rider = row.get("rider", {})
    full_name = rider.get("full_name", "")
    return {
        "name": full_name,
        "code": short_name(full_name),
        "flag": to_flag(rider.get("country", {}).get("iso", "")),
        "team": row.get("team", {}).get("name", ""),
        "color": team_color(row.get("constructor", {}).get("name", "")),
    }


def make_result_row(row):
    result = make_rider(row)
    position = row.get("position")
    gap = row.get("gap") or {}
    result["position"] = position if position else "DNF"
    result["points"] = row.get("points", 0)
    if position == 1:
        result["time"] = row.get("time", "")
    elif position and str(gap.get("lap", "0")) not in ("0", ""):
        result["time"] = f"+{gap['lap']} lap"
    elif position and gap.get("first"):
        result["time"] = "+" + gap["first"]
    else:
        result["time"] = row.get("status", "")
    return result


def top3(rows):
    riders = []
    for row in rows[:3]:
        riders.append(make_rider(row))
    return riders


def full_results(rows):
    result = []
    for row in rows:
        result.append(make_result_row(row))
    return result


def get_race_results(season, round_number):
    empty = {"sessions": [], "tz": "", "race_top3": [], "full_results": [],
             "sprint_winner": None, "sprint_grid": [], "quali": []}

    events = grand_prix_events(season)
    if round_number > len(events):
        return empty
    event = events[round_number - 1]

    season_uuid = season_id(season)
    category_uuid = category_id(season_uuid)
    url = f"{BASE_URL}/results/sessions?eventUuid={event['id']}&categoryUuid={category_uuid}"
    sessions = get_cached(url, max_age_for(season))

    session_list = []
    finished = {}
    for session in sessions:
        if not session.get("date"):
            continue
        label = session_label(session)
        session_list.append(make_session(label, session["date"][:10], session["date"][11:]))
        if session.get("status") == "FINISHED":
            finished[label] = session["id"]
    session_list.sort(key=lambda s: s["utc"])

    race = classification(finished.get("Race"), season)
    sprint = classification(finished.get("Sprint"), season)
    quali = classification(finished.get("Qualifying 2"), season)

    return {
        "sessions": session_list,
        "tz": COUNTRY_TIMEZONES.get(event["country"]["iso"], ""),
        "race_top3": top3(race),
        "full_results": full_results(race),
        "sprint_winner": make_rider(sprint[0]) if sprint else None,
        "sprint_grid": [],
        "quali": top3(quali),
    }


# ---------- Standings ----------

def color_from_name(name):
    lower = name.lower()
    for brand, color in TEAM_COLORS.items():
        if brand in lower:
            return color
    return "#9a9aa8"


def world_standings(kind, season_uuid, category_uuid, max_age):
    url = f"{WORLD_STANDINGS_URL}?type={kind}&season={season_uuid}&category={category_uuid}"
    try:
        data = get_cached(url, max_age)
    except Exception:
        return []
    return (data.get("classification") or {}).get(kind) or []


def get_standings(season):
    season_uuid = season_id(season)
    if season_uuid is None:
        return {"drivers": [], "groups": []}

    category_uuid = category_id(season_uuid)
    max_age = max_age_for(season)

    url = f"{BASE_URL}/results/standings?seasonUuid={season_uuid}&categoryUuid={category_uuid}"
    data = get_cached(url, max_age)
    riders = []
    for row in data.get("classification", []):
        rider = make_rider(row)
        rider["position"] = row.get("position", "")
        rider["points"] = row.get("points", 0)
        rider["wins"] = row.get("race_wins", 0)
        riders.append(rider)

    manufacturers = []
    for row in world_standings("constructor", season_uuid, category_uuid, max_age):
        name = (row.get("constructor") or {}).get("name", "")
        manufacturers.append({
            "position": row.get("position", ""),
            "name": name,
            "color": team_color(name),
            "points": row.get("points", 0),
            "wins": None,
        })

    teams = []
    for row in world_standings("team", season_uuid, category_uuid, max_age):
        team = row.get("team")
        name = team.get("name", "") if isinstance(team, dict) else (team or "")
        constructor = (row.get("constructor") or {}).get("name", "")
        teams.append({
            "position": row.get("position", ""),
            "name": name,
            "color": team_color(constructor) if constructor else color_from_name(name),
            "points": row.get("points", 0),
            "wins": None,
        })

    return {
        "drivers": add_percentages(riders),
        "groups": [
            {"title": "manufacturers", "column": "manufacturer", "rows": add_percentages(manufacturers)},
            {"title": "teams", "column": "team", "rows": add_percentages(teams)},
        ],
    }