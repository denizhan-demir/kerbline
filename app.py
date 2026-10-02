import requests
from datetime import datetime, timedelta, timezone
from timezonefinder import TimezoneFinder
from flask import Flask, render_template

app = Flask(__name__)

cache = {}

SESSIONS = [
    ("FirstPractice", "Practice 1"),
    ("SecondPractice", "Practice 2"),
    ("ThirdPractice", "Practice 3"),
    ("SprintQualifying", "Sprint Qualifying"),
    ("Sprint", "Sprint"),
    ("Qualifying", "Qualifying"),
]

tf = TimezoneFinder()
def track_timezone(race):
    location = race["Circuit"]["Location"]
    return tf.timezone_at(lng=float(location["long"]), lat=float(location["lat"])) or ""

def parse_time(session):
    time = session.get("time", "00:00:00Z")
    return datetime.fromisoformat(session["date"] + "T" + time)

def make_session(name, session):
    return {
        "name": name,
        "utc": parse_time(session).isoformat(),
        "date": session["date"],
        "tbc": "time" not in session,
    }

def fetch_races(season):
    cached = cache.get(season)
    if cached is None or datetime.now() - cached["at"] > timedelta(hours=1):
        try:
            print(f"Fetching {season} from API...")
            response = requests.get(f"https://api.jolpi.ca/ergast/f1/{season}.json", timeout=10)
            response.raise_for_status()
            races = response.json()["MRData"]["RaceTable"]["Races"]
            cache[season] = {"races": races, "at": datetime.now()}
        except requests.RequestException:
            print("API request failed")
            if cached is None:
                raise
    return cache[season]["races"]

def get_races(season):
    races = fetch_races(season)
    now = datetime.now(timezone.utc)
    mark_next = season == now.year
    next_found = False
    result = []

    for race in races:
        race_time = parse_time(race)

        if race_time < now:
            status = "done"
        elif mark_next and not next_found:
            status = "next"
            next_found = True
        else:
            status = "upcoming"

        sessions = []
        for key, label in SESSIONS:
            if key in race:
                sessions.append(make_session(label, race[key]))
        sessions.append(make_session("Race", race))

        result.append({
            "status": status,
            "round": race["round"],
            "name": race["raceName"],
            "country": race["Circuit"]["Location"]["country"],
            "main": make_session("Race", race),
            "tz": track_timezone(race),
            "sessions": sessions,
        })

    return result

@app.route("/")
@app.route("/<int:season>")
def home(season=None):
    this_year = datetime.now().year
    if season is None:
        season = this_year
    try:
        races = get_races(season)
    except Exception:
        app.logger.exception("Could not load calendar")
        return "<h1>F1 Calendar</h1><p>Calendar data is unavailable right now. Please try again later.</p>", 503
    return render_template("index.html", races=races, season=season, seasons=[this_year, this_year + 1])

@app.route("/about")
def about():
    return "<h1>About</h1><p>Track every F1 race weekend in your local time.</p>"

if __name__ == "__main__":
    app.run(debug=True, port=8000)