import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template

app = Flask(__name__)

URL = "https://api.jolpi.ca/ergast/f1/current.json"
cached_races = None
cached_at = None

def fetch_races():
    global cached_races, cached_at
    if cached_races is None or datetime.now() - cached_at > timedelta(hours=1):
        print("Fetching from API...")
        response = requests.get(URL, timeout=10)
        cached_races = response.json()["MRData"]["RaceTable"]["Races"]
        cached_at = datetime.now()
    return cached_races

def get_races():
    races = fetch_races()
    budapest = ZoneInfo("Europe/Budapest")
    now = datetime.now(budapest)

    budapest = ZoneInfo("Europe/Budapest")
    now = datetime.now(budapest)
    next_found = False
    result = []

    for race in races:
        utc_time = datetime.fromisoformat(race["date"] + "T" + race["time"])
        local_time = utc_time.astimezone(budapest)
        quali_utc = datetime.fromisoformat(race["Qualifying"]["date"] + "T" + race["Qualifying"]["time"])
        quali_local = quali_utc.astimezone(budapest)

        if local_time < now:
            status = "✓"
        elif not next_found:
            status = "→"
            next_found = True
        else:
            status = ""

        result.append({
            "status": status,
            "round": race["round"],
            "name": race["raceName"],
            "country": race["Circuit"]["Location"]["country"],
            "quali": quali_local.strftime("%d.%m %H:%M"),
            "race": local_time.strftime("%d.%m.%Y %H:%M"),
        })

    return result

@app.route("/")
def home():
    races = get_races()
    return render_template("index.html", races=races)

@app.route("/about")
def about():
    return "<h1>About</h1><p>Track every F1 race weekend in your local time.</p>"

if __name__ == "__main__":
    app.run(debug=True, port=8000)