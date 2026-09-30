import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template

app = Flask(__name__)

URL = "https://api.jolpi.ca/ergast/f1/current.json"
cached_races = None
cached_at = None

BUDAPEST = ZoneInfo("Europe/Budapest")

SESSIONS = [
    ("FirstPractice", "Practice 1"),
    ("SecondPractice", "Practice 2"),
    ("ThirdPractice", "Practice 3"),
    ("SprintQualifying", "Sprint Qualifying"),
    ("Sprint", "Sprint"),
    ("Qualifying", "Qualifying"),
]

def to_local(session):
    utc_time = datetime.fromisoformat(session["date"] + "T" + session["time"])
    return utc_time.astimezone(BUDAPEST)

def fetch_races():
    global cached_races, cached_at
    if cached_races is None or datetime.now() - cached_at > timedelta(hours=1):
        try:
            print("Fetching from API...")
            response = requests.get(URL, timeout=10)
            response.raise_for_status()
            cached_races = response.json()["MRData"]["RaceTable"]["Races"]
            cached_at = datetime.now()
        except requests.RequestException:
            print("API request failed")
            if cached_races is None:
                raise
    return cached_races

def get_races():
    races = fetch_races()
    now = datetime.now(BUDAPEST)
    next_found = False
    result = []

    for race in races:
        race_time = to_local(race)

        if race_time < now:
            status = "done"
        elif not next_found:
            status = "next"
            next_found = True
        else:
            status = "upcoming"

        sessions = []
        for key, label in SESSIONS:
            if key in race:
                sessions.append({"name": label, "time": to_local(race[key]).strftime("%a %d.%m %H:%M")})
        sessions.append({"name": "Race", "time": race_time.strftime("%a %d.%m %H:%M")})

        result.append({
            "status": status,
            "round": race["round"],
            "name": race["raceName"],
            "country": race["Circuit"]["Location"]["country"],
            "date": race_time.strftime("%d.%m.%Y"),
            "sessions": sessions,
        })

    return result

@app.route("/")
def home():
    try:
        races = get_races()
    except Exception:
        return "<h1>F1 Calendar</h1><p>Calendar data is unavailable right now. Please try again later.</p>", 503
    return render_template("index.html", races=races)

@app.route("/about")
def about():
    return "<h1>About</h1><p>Track every F1 race weekend in your local time.</p>"

if __name__ == "__main__":
    app.run(debug=True, port=8000)