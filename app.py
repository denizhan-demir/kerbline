import time
import requests
from datetime import datetime, timedelta, timezone
from timezonefinder import TimezoneFinder
from flask import Flask, render_template, abort, request, make_response

app = Flask(__name__)

BASE_URL = "https://api.jolpi.ca/ergast/f1"
FIRST_SEASON = 2020

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

NATIONALITY_CODES = {
    "British": "GB", "Dutch": "NL", "Monegasque": "MC", "Spanish": "ES",
    "Mexican": "MX", "Australian": "AU", "French": "FR", "German": "DE",
    "Finnish": "FI", "Canadian": "CA", "Thai": "TH", "Japanese": "JP",
    "Danish": "DK", "Chinese": "CN", "American": "US", "Italian": "IT",
    "New Zealander": "NZ", "Argentine": "AR", "Argentinian": "AR",
    "Brazilian": "BR", "Russian": "RU", "Polish": "PL",
}

TRANSLATIONS = {
    "en": {
        "title": "F1 Calendar",
        "your_time": "Your time",
        "track_time": "Track time",
        "tz_yours": "Times in your time zone",
        "tz_track": "Times in each circuit's local time",
        "not_available": "The {season} calendar isn't available yet.",
        "unavailable": "Calendar data is unavailable right now. Please try again later.",
        "next": "NEXT",
        "tbc": "TBC",
        "sprint_qualifying": "Sprint Qualifying",
        "sprint_winner": "Sprint winner",
        "qualifying": "Qualifying",
        "race_winner": "Race winner",
    },
    "tr": {
        "title": "F1 Takvimi",
        "your_time": "Senin saatin",
        "track_time": "Pist saati",
        "tz_yours": "Saatler senin saat dilimine göre",
        "tz_track": "Saatler her pistin yerel saatine göre",
        "not_available": "{season} takvimi henüz mevcut değil.",
        "unavailable": "Takvim verilerine şu anda ulaşılamıyor. Lütfen daha sonra tekrar dene.",
        "next": "SIRADAKİ",
        "tbc": "Açıklanacak",
        "sprint_qualifying": "Sprint Sıralama",
        "sprint_winner": "Sprint kazananı",
        "qualifying": "Sıralama",
        "race_winner": "Yarış kazananı",
        "Practice 1": "1. Antrenman",
        "Practice 2": "2. Antrenman",
        "Practice 3": "3. Antrenman",
        "Sprint Qualifying": "Sprint Sıralama",
        "Qualifying": "Sıralama",
        "Race": "Yarış",
    },
}


def get_lang():
    lang = request.args.get("lang") or request.cookies.get("lang")
    if lang not in TRANSLATIONS:
        lang = request.accept_languages.best_match(["en", "tr"]) or "en"
    return lang

def flag(nationality):
    code = NATIONALITY_CODES.get(nationality, "")
    result = ""
    for letter in code:
        result += chr(0x1F1E6 + ord(letter) - ord("A"))
    return result

cache = {}
tf = TimezoneFinder()


def get_cached(url, max_age):
    cached = cache.get(url)
    if cached is None or datetime.now() - cached["at"] > max_age:
        try:
            print(f"Fetching {url}")
            time.sleep(0.3)
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            cache[url] = {"data": response.json(), "at": datetime.now()}
        except requests.RequestException:
            print("API request failed")
            if cached is None:
                raise
    return cache[url]["data"]


def fetch_races(season):
    data = get_cached(f"{BASE_URL}/{season}.json", timedelta(hours=1))
    return data["MRData"]["RaceTable"]["Races"]


def fetch_all_pages(path, max_age, key):
    by_round = {}
    offset = 0
    while True:
        data = get_cached(f"{BASE_URL}/{path}.json?limit=100&offset={offset}", max_age)
        for race in data["MRData"]["RaceTable"]["Races"]:
            round_number = race["round"]
            if round_number not in by_round:
                by_round[round_number] = []
            by_round[round_number].extend(race[key])
        offset += 100
        if offset >= int(data["MRData"]["total"]):
            break
    return by_round


def fetch_results(season):
    if season < datetime.now().year:
        max_age = timedelta(hours=24)
    else:
        max_age = timedelta(minutes=30)
    race_results = fetch_all_pages(f"{season}/results", max_age, "Results")
    sprint_results = fetch_all_pages(f"{season}/sprint", max_age, "SprintResults")
    quali_results = fetch_all_pages(f"{season}/qualifying", max_age, "QualifyingResults")
    return race_results, sprint_results, quali_results


def make_driver(result):
    driver = result["Driver"]
    team_id = result["Constructor"]["constructorId"]
    return {
        "name": driver["givenName"] + " " + driver["familyName"],
        "code": driver.get("code", driver["familyName"][:3].upper()),
        "flag": flag(driver.get("nationality", "")),
        "team": result["Constructor"]["name"],
        "color": TEAM_COLORS.get(team_id, "#9a9aa8"),
    }


def top3(results):
    drivers = []
    for result in results[:3]:
        drivers.append(make_driver(result))
    return drivers


def sprint_grid_top3(sprint_results):
    starters = []
    for result in sprint_results:
        if result.get("grid", "0") != "0":
            starters.append(result)
    starters.sort(key=lambda r: int(r["grid"]))
    return top3(starters)


def track_timezone(race):
    location = race["Circuit"]["Location"]
    return tf.timezone_at(lng=float(location["long"]), lat=float(location["lat"])) or ""


def parse_time(session):
    time_str = session.get("time", "00:00:00Z")
    return datetime.fromisoformat(session["date"] + "T" + time_str)


def make_session(name, session):
    return {
        "name": name,
        "utc": parse_time(session).isoformat(),
        "date": parse_time(session).strftime("%d/%m/%Y"),
        "tbc": "time" not in session,
    }


def get_races(season):
    races = fetch_races(season)
    try:
        race_results, sprint_results, quali_results = fetch_results(season)
    except Exception:
        app.logger.exception("Could not load results")
        race_results, sprint_results, quali_results = {}, {}, {}

    now = datetime.now(timezone.utc)
    mark_next = season == now.year
    next_found = False
    result = []

    for race in races:
        race_time = parse_time(race)
        round_number = race["round"]

        if race_time < now:
            status = "done" if mark_next else "past"
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
        sessions.sort(key=lambda s: s["utc"])

        race_list = race_results.get(round_number, [])
        sprint_list = sprint_results.get(round_number, [])
        quali_list = quali_results.get(round_number, [])

        result.append({
            "status": status,
            "round": round_number,
            "name": race["raceName"],
            "country": race["Circuit"]["Location"]["country"],
            "main": make_session("Race", race),
            "tz": track_timezone(race),
            "sessions": sessions,
            "winner": make_driver(race_list[0]) if race_list else None,
            "sprint_winner": make_driver(sprint_list[0]) if sprint_list else None,
            "sprint_grid": sprint_grid_top3(sprint_list),
            "quali": top3(quali_list),
        })

    return result


@app.route("/")
@app.route("/<int:season>")
def home(season=None):
    lang = get_lang()
    t = TRANSLATIONS[lang]
    this_year = datetime.now().year
    if season is None:
        season = this_year
    if season < FIRST_SEASON or season > this_year + 1:
        abort(404)
    try:
        races = get_races(season)
    except Exception:
        app.logger.exception("Could not load calendar")
        return f"<h1>{t['title']}</h1><p>{t['unavailable']}</p>", 503
    html = render_template(
        "index.html",
        races=races,
        season=season,
        seasons=list(range(FIRST_SEASON, this_year + 2)),
        lang=lang,
        t=t,
    )
    response = make_response(html)
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return response

@app.route("/about")
def about():
    return "<h1>About</h1><p>Track every F1 race weekend in your local time.</p>"


if __name__ == "__main__":
    app.run(debug=True, port=8000)