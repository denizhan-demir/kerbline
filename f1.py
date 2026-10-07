import json
from datetime import datetime, timedelta
from pathlib import Path

from core import (
    add_percentages,
    flag_for_country,
    flag_for_nationality,
    get_cached,
    make_session,
    timezone_at,
)

ID = "f1"
NAME = "Formula 1"
SHORT = "F1"
FIRST_SEASON = 2020
PARTICIPANT = "driver"
PARTICIPANTS = "drivers"
BASE_URL = "https://api.jolpi.ca/ergast/f1"

SESSIONS = [
    ("FirstPractice", "Practice 1"),
    ("SecondPractice", "Practice 2"),
    ("ThirdPractice", "Practice 3"),
    ("SprintQualifying", "Sprint Qualifying"),
    ("SprintShootout", "Sprint Shootout"),
    ("Sprint", "Sprint"),
    ("Qualifying", "Qualifying"),
]

TEAM_COLORS = {
    "mercedes": "#27F4D2",
    "red_bull": "#3671C6",
    "ferrari": "#E8002D",
    "mclaren": "#FF8000",
    "aston_martin": "#229971",
    "racing_point": "#F596C8",
    "alpine": "#0093CC",
    "renault": "#FFF500",
    "williams": "#64C4FF",
    "alphatauri": "#5E8FAA",
    "rb": "#6692FF",
    "alfa": "#C92D4B",
    "sauber": "#52E252",
    "haas": "#B6BABD",
}

POSITION_LABELS = {"R": "DNF", "D": "DSQ", "E": "EX", "W": "DNS", "F": "DNQ", "N": "NC"}


def max_age_for(season):
    if season < datetime.now().year:
        return timedelta(hours=24)
    return timedelta(minutes=30)


def team_color(team_id):
    return TEAM_COLORS.get(team_id, "#9a9aa8")


# ---------- Calendar ----------

def load_fallback(season):
    path = Path(__file__).parent / "data" / f"calendar_{season}.json"
    if not path.exists():
        return []
    races = []
    for item in json.loads(path.read_text(encoding="utf-8")):
        races.append({
            "round": item["round"],
            "raceName": item["raceName"],
            "date": item["date"],
            "Circuit": {"Location": {"country": item["country"]}},
        })
    return races


def fetch_races(season):
    data = get_cached(f"{BASE_URL}/{season}.json", timedelta(hours=1))
    races = data["MRData"]["RaceTable"]["Races"]
    if not races:
        races = load_fallback(season)
    return races


def track_timezone(race):
    location = race["Circuit"]["Location"]
    if "lat" not in location or "long" not in location:
        return ""
    return timezone_at(float(location["lat"]), float(location["long"]))


def to_session(name, session):
    return make_session(name, session["date"], session.get("time"))


def get_races(season):
    races = []
    for race in fetch_races(season):
        country = race["Circuit"]["Location"]["country"]
        sessions = []
        for key, label in SESSIONS:
            if key in race:
                sessions.append(to_session(label, race[key]))
        sessions.append(to_session("Race", race))
        sessions.sort(key=lambda s: s["utc"])
        races.append({
            "round": race["round"],
            "name": race["raceName"],
            "country": country,
            "flag": flag_for_country(country),
            "main": to_session("Race", race),
            "tz": track_timezone(race),
            "sessions": sessions,
        })
    return races


# ---------- Race results ----------

def fetch_round(season, round_number, endpoint, key):
    url = f"{BASE_URL}/{season}/{round_number}/{endpoint}.json?limit=100"
    data = get_cached(url, max_age_for(season))
    races = data["MRData"]["RaceTable"]["Races"]
    if races:
        return races[0][key]
    return []


def make_driver(result):
    driver = result["Driver"]
    return {
        "name": driver["givenName"] + " " + driver["familyName"],
        "code": driver.get("code", driver["familyName"][:3].upper()),
        "flag": flag_for_nationality(driver.get("nationality", "")),
        "team": result["Constructor"]["name"],
        "color": team_color(result["Constructor"]["constructorId"]),
    }


def make_result_row(result):
    row = make_driver(result)
    position = result.get("positionText", result.get("position", ""))
    row["position"] = POSITION_LABELS.get(position, position)
    row["points"] = result.get("points", "0")
    if "Time" in result:
        row["time"] = result["Time"]["time"]
    else:
        row["time"] = result.get("status", "")
    return row


def top3(results):
    drivers = []
    for result in results[:3]:
        drivers.append(make_driver(result))
    return drivers


def full_results(results):
    rows = []
    for result in results:
        rows.append(make_result_row(result))
    return rows


def sprint_grid_top3(sprint_results):
    starters = []
    for result in sprint_results:
        if result.get("grid", "0") != "0":
            starters.append(result)
    starters.sort(key=lambda r: int(r["grid"]))
    return top3(starters)


def has_sprint(season, round_number):
    for race in fetch_races(season):
        if race["round"] == str(round_number):
            if "FirstPractice" not in race:
                return True
            return "Sprint" in race
    return False


def get_race_results(season, round_number):
    race_list = fetch_round(season, round_number, "results", "Results")
    quali_list = fetch_round(season, round_number, "qualifying", "QualifyingResults")
    sprint_list = []
    if has_sprint(season, round_number):
        sprint_list = fetch_round(season, round_number, "sprint", "SprintResults")
    return {
        "race_top3": top3(race_list),
        "full_results": full_results(race_list),
        "sprint_winner": make_driver(sprint_list[0]) if sprint_list else None,
        "sprint_grid": sprint_grid_top3(sprint_list),
        "quali": top3(quali_list),
    }


# ---------- Standings ----------

def standings_list(data, key):
    lists = data["MRData"]["StandingsTable"]["StandingsLists"]
    if lists:
        return lists[0][key]
    return []


def get_standings(season):
    max_age = max_age_for(season)
    driver_data = get_cached(f"{BASE_URL}/{season}/driverStandings.json?limit=100", max_age)
    team_data = get_cached(f"{BASE_URL}/{season}/constructorStandings.json?limit=100", max_age)

    drivers = []
    for row in standings_list(driver_data, "DriverStandings"):
        driver = row["Driver"]
        teams = row.get("Constructors", [])
        team = teams[-1] if teams else {"name": "", "constructorId": ""}
        drivers.append({
            "position": row.get("positionText", row.get("position", "")),
            "name": driver["givenName"] + " " + driver["familyName"],
            "flag": flag_for_nationality(driver.get("nationality", "")),
            "team": team["name"],
            "color": team_color(team["constructorId"]),
            "points": row.get("points", "0"),
            "wins": row.get("wins", "0"),
        })

    teams = []
    for row in standings_list(team_data, "ConstructorStandings"):
        team = row["Constructor"]
        teams.append({
            "position": row.get("positionText", row.get("position", "")),
            "name": team["name"],
            "color": team_color(team["constructorId"]),
            "points": row.get("points", "0"),
            "wins": row.get("wins", "0"),
        })

    return {
        "drivers": add_percentages(drivers),
        "groups": [
            {"title": "teams", "column": "team", "rows": add_percentages(teams)},
        ],
    }