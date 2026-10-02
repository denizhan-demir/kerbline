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

POSITION_LABELS = {"R": "DNF", "D": "DSQ", "E": "EX", "W": "DNS", "F": "DNQ", "N": "NC"}

TRANSLATIONS = {
    "en": {
        "title": "F1 Calendar",
        "your_time": "Your time",
        "track_time": "Track time",
        "tz_yours": "Times in your time zone",
        "tz_track": "Times in each circuit's local time",
        "not_available": "The {season} calendar isn't available yet.",
        "unavailable": "Calendar data is unavailable right now. Please try again later.",
        "loading": "Loading results…",
        "next": "NEXT",
        "tbc": "TBC",
        "sprint_qualifying": "Sprint Qualifying",
        "sprint_winner": "Sprint winner",
        "qualifying": "Qualifying",
        "race": "Race",
        "full_result": "Full race result",
        "pos": "Pos",
        "driver": "Driver",
        "team": "Team",
        "time": "Time / Status",
        "points": "Pts",
    },
    "tr": {
        "title": "F1 Takvimi",
        "your_time": "Senin saatin",
        "track_time": "Pist saati",
        "tz_yours": "Saatler senin saat dilimine göre",
        "tz_track": "Saatler her pistin yerel saatine göre",
        "not_available": "{season} takvimi henüz mevcut değil.",
        "unavailable": "Verilere şu anda ulaşılamıyor. Lütfen daha sonra tekrar dene.",
        "loading": "Sonuçlar yükleniyor…",
        "next": "SIRADAKİ",
        "tbc": "Açıklanacak",
        "sprint_qualifying": "Sprint Sıralama",
        "sprint_winner": "Sprint kazananı",
        "qualifying": "Sıralama",
        "race": "Yarış",
        "full_result": "Tüm yarış sonucu",
        "pos": "Sıra",
        "driver": "Pilot",
        "team": "Takım",
        "time": "Süre / Durum",
        "points": "Puan",
        "Practice 1": "1. Antrenman",
        "Practice 2": "2. Antrenman",
        "Practice 3": "3. Antrenman",
        "Sprint Qualifying": "Sprint Sıralama",
        "Qualifying": "Sıralama",
        "Race": "Yarış",
    },
}

cache = {}
tf = TimezoneFinder()


def get_lang():
    lang = request.args.get("lang") or request.cookies.get("lang")
    if lang not in TRANSLATIONS:
        lang = request.accept_languages.best_match(["en", "tr"]) or "en"
    return lang


def to_flag(code):
    result = ""
    for letter in code:
        result += chr(0x1F1E6 + ord(letter) - ord("A"))
    return result


blocked_until = datetime.min


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
            time.sleep(0.3)
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


def fetch_races(season):
    data = get_cached(f"{BASE_URL}/{season}.json", timedelta(hours=1))
    return data["MRData"]["RaceTable"]["Races"]


def fetch_round(season, round_number, endpoint, key, max_age):
    data = get_cached(f"{BASE_URL}/{season}/{round_number}/{endpoint}.json?limit=100", max_age)
    races = data["MRData"]["RaceTable"]["Races"]
    if races:
        return races[0][key]
    return []


def make_driver(result):
    driver = result["Driver"]
    team_id = result["Constructor"]["constructorId"]
    return {
        "name": driver["givenName"] + " " + driver["familyName"],
        "code": driver.get("code", driver["familyName"][:3].upper()),
        "flag": to_flag(NATIONALITY_CODES.get(driver.get("nationality", ""), "")),
        "team": result["Constructor"]["name"],
        "color": TEAM_COLORS.get(team_id, "#9a9aa8"),
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


def get_race_results(season, round_number):
    if season < datetime.now().year:
        max_age = timedelta(hours=24)
    else:
        max_age = timedelta(minutes=30)
    race_list = fetch_round(season, round_number, "results", "Results", max_age)
    sprint_list = fetch_round(season, round_number, "sprint", "SprintResults", max_age)
    quali_list = fetch_round(season, round_number, "qualifying", "QualifyingResults", max_age)
    return {
        "race_top3": top3(race_list),
        "full_results": full_results(race_list),
        "sprint_winner": make_driver(sprint_list[0]) if sprint_list else None,
        "sprint_grid": sprint_grid_top3(sprint_list),
        "quali": top3(quali_list),
    }


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
    now = datetime.now(timezone.utc)
    mark_next = season == now.year
    next_found = False
    result = []

    for race in races:
        race_time = parse_time(race)
        country = race["Circuit"]["Location"]["country"]

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

        result.append({
            "status": status,
            "round": race["round"],
            "name": race["raceName"],
            "country": country,
            "flag": to_flag(COUNTRY_CODES.get(country, "")),
            "main": make_session("Race", race),
            "tz": track_timezone(race),
            "sessions": sessions,
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


@app.route("/results/<int:season>/<int:round_number>")
def race_results(season, round_number):
    t = TRANSLATIONS[get_lang()]
    if season < FIRST_SEASON or season > datetime.now().year + 1:
        abort(404)
    if round_number < 1 or round_number > 30:
        abort(404)
    try:
        results = get_race_results(season, round_number)
    except Exception:
        app.logger.exception("Could not load results")
        return f"<p class='note'>{t['unavailable']}</p>", 503
    return render_template("results.html", r=results, t=t)


@app.route("/about")
def about():
    return "<h1>About</h1><p>Track every F1 race weekend in your local time.</p>"


if __name__ == "__main__":
    app.run(debug=True, port=8000)