from datetime import datetime, timedelta

from core import add_percentages, get_cached, make_session, to_flag

ID = "motogp"
NAME = "MotoGP"
SHORT = "MGP"
FIRST_SEASON = 2020
PARTICIPANT = "rider"
PARTICIPANTS = "riders"

BASE_URL = "https://api.motogp.pulselive.com/motogp/v1"

TEAM_COLORS = {
    "ducati": "#E2231A",
    "aprilia": "#9B5DE5",
    "ktm": "#FF6600",
    "honda": "#E8E8E8",
    "yamaha": "#2F6BFF",
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


# ---------- Calendar ----------

def get_races(season):
    season_uuid = season_id(season)
    if season_uuid is None:
        return []

    events = get_cached(f"{BASE_URL}/results/events?seasonUuid={season_uuid}", timedelta(hours=1))
    grand_prix = []
    for event in events:
        if not event.get("test"):
            grand_prix.append(event)
    grand_prix.sort(key=lambda e: e["date_start"])

    races = []
    for number, event in enumerate(grand_prix, start=1):
        country = event["country"]
        races.append({
            "round": str(number),
            "name": pretty_name(event["name"]),
            "country": country["name"],
            "flag": to_flag(country["iso"]),
            "main": make_session("Race", event["date_end"]),
            "tz": "",
            "sessions": [],
        })
    return races


# ---------- Race results (next step) ----------

def get_race_results(season, round_number):
    return {
        "race_top3": [],
        "full_results": [],
        "sprint_winner": None,
        "sprint_grid": [],
        "quali": [],
    }


# ---------- Standings ----------

def get_standings(season):
    season_uuid = season_id(season)
    if season_uuid is None:
        return {"drivers": [], "teams": []}

    category_uuid = category_id(season_uuid)
    url = f"{BASE_URL}/results/standings?seasonUuid={season_uuid}&categoryUuid={category_uuid}"
    data = get_cached(url, max_age_for(season))

    riders = []
    for row in data.get("classification", []):
        rider = row["rider"]
        riders.append({
            "position": row.get("position", ""),
            "name": rider["full_name"],
            "flag": to_flag(rider.get("country", {}).get("iso", "")),
            "team": row.get("team", {}).get("name", ""),
            "color": team_color(row.get("constructor", {}).get("name", "")),
            "points": row.get("points", 0),
            "wins": row.get("race_wins", 0),
        })

    return {"drivers": add_percentages(riders), "teams": []}