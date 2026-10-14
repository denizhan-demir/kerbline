from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from flask import Flask, abort, jsonify, make_response, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

import f1
import ics
import motogp
import people
import wsbk
from core import add_statuses

app = Flask(__name__)
# Render sits in front of the app; this makes links use https:// on the live site.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

SERIES = {f1.ID: f1, motogp.ID: motogp, wsbk.ID: wsbk}
DEFAULT_SERIES = f1.ID

# How far ahead the calendar feed loads every session of MotoGP and WorldSBK rounds.
FEED_DETAIL_WINDOW = timedelta(days=45)
FEED_DETAIL_ROUNDS = 3

MANIFEST = {
    "name": "Kerbline",
    "short_name": "Kerbline",
    "description": "F1, MotoGP and WorldSBK calendars, results and standings",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#0e0f14",
    "theme_color": "#0e0f14",
    "icons": [
        {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}

TRANSLATIONS = {
    "en": {
        "site_name": "Kerbline",
        "home": "Home",
        "up_next": "Up next",
        "this_weekend": "This weekend",
        "no_next": "The next season's calendar isn't out yet.",
        "open_calendar": "Full calendar",
        "calendar": "Calendar",
        "standings": "Standings",
        "drivers": "Drivers",
        "teams": "Teams",
        "wins": "Wins",
        "series": "Series",
        "next_race": "Next race",
        "round": "Round",
        "days": "days",
        "hours": "hrs",
        "minutes": "min",
        "seconds": "sec",
        "rider": "Rider",
        "riders": "Riders",
        "disclaimer": "Unofficial fan project, not affiliated with Formula 1, MotoGP, WorldSBK or their rights holders. F1 data: Jolpica-F1. MotoGP data: motogp.com. WorldSBK data: worldsbk.com.",
        "your_time": "Your time",
        "track_time": "Track time",
        "tz_yours": "Times in your time zone",
        "tz_track": "Times in each circuit's local time",
        "add_to_calendar": "Add to calendar",
        "apple_calendar": "Apple Calendar (iPhone, Mac)",
        "google_calendar": "Google Calendar",
        "copy_link": "Copy calendar link",
        "copied": "Link copied!",
        "calendar_help": "Every session goes into your calendar and updates by itself when times change.",
        "not_available": "The {season} calendar isn't available yet.",
        "no_standings": "Standings for {season} aren't available yet.",
        "unavailable": "Data is unavailable right now. Please try again later.",
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
        "manufacturer": "Manufacturer",
        "manufacturers": "Manufacturers",
        "season": "Season",
        "completed": "Completed races",
        "schedule": "Schedule",
        "results": "Results",
        "close": "Close",
        "results_later": "Results show up here once the sessions are done.",
        "next_session": "Next session",
        "leader": "Leader",
        "read_more": "Read more on Wikipedia",
        "photo": "Photo",
        "no_info": "No extra info found for this driver.",
    },
    "tr": {
        "site_name": "Kerbline",
        "home": "Ana sayfa",
        "up_next": "Sıradaki yarışlar",
        "this_weekend": "Bu hafta sonu",
        "no_next": "Gelecek sezonun takvimi henüz açıklanmadı.",
        "open_calendar": "Tüm takvim",
        "calendar": "Takvim",
        "standings": "Puan Durumu",
        "drivers": "Pilotlar",
        "teams": "Takımlar",
        "wins": "Galibiyet",
        "series": "Seriler",
        "next_race": "Sıradaki yarış",
        "round": "Tur",
        "days": "gün",
        "hours": "saat",
        "minutes": "dk",
        "seconds": "sn",
        "rider": "Pilot",
        "riders": "Pilotlar",
        "disclaimer": "Resmi olmayan bir hayran projesidir; Formula 1, MotoGP, WorldSBK veya hak sahipleriyle bağlantısı yoktur. F1 verisi: Jolpica-F1. MotoGP verisi: motogp.com. WorldSBK verisi: worldsbk.com.",
        "your_time": "Senin saatin",
        "track_time": "Pist saati",
        "tz_yours": "Saatler senin saat dilimine göre",
        "tz_track": "Saatler her pistin yerel saatine göre",
        "add_to_calendar": "Takvime ekle",
        "apple_calendar": "Apple Takvim (iPhone, Mac)",
        "google_calendar": "Google Takvim",
        "copy_link": "Takvim linkini kopyala",
        "copied": "Link kopyalandı!",
        "calendar_help": "Bütün seanslar takvimine eklenir, saatler değişirse kendiliğinden güncellenir.",
        "not_available": "{season} takvimi henüz mevcut değil.",
        "no_standings": "{season} puan durumu henüz mevcut değil.",
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
        "Free Practice 1": "1. Serbest Antrenman",
        "Free Practice 2": "2. Serbest Antrenman",
        "Practice": "Antrenman",
        "Qualifying 1": "Sıralama 1",
        "Qualifying 2": "Sıralama 2",
        "Warm Up": "Isınma",
        "Free Practice 3": "3. Serbest Antrenman",
        "Race 1": "1. Yarış",
        "Race 2": "2. Yarış",
        "Superpole Race": "Superpole Yarışı",
        "manufacturer": "Marka",
        "manufacturers": "Markalar",
        "season": "Sezon",
        "completed": "Tamamlanan yarışlar",
        "schedule": "Program",
        "results": "Sonuçlar",
        "close": "Kapat",
        "results_later": "Sonuçlar seanslar bitince burada görünecek.",
        "next_session": "Sıradaki seans",
        "leader": "Lider",
        "read_more": "Wikipedia'da devamını oku",
        "photo": "Fotoğraf",
        "no_info": "Bu pilot hakkında ek bilgi bulunamadı.",
    },
}


def get_lang():
    lang = request.args.get("lang") or request.cookies.get("lang")
    if lang not in TRANSLATIONS:
        lang = request.accept_languages.best_match(["en", "tr"]) or "en"
    return lang


def get_series(series_id):
    series = SERIES.get(series_id)
    if series is None:
        abort(404)
    return series


def get_seasons(series, season):
    this_year = datetime.now().year
    if season < series.FIRST_SEASON or season > this_year + 1:
        abort(404)
    return list(range(series.FIRST_SEASON, this_year + 2))


def error_page(lang):
    t = TRANSLATIONS[lang]
    return f"<h1>{t['site_name']}</h1><p>{t['unavailable']}</p>", 503


def render_page(template, lang, **context):
    html = render_template(
        template,
        lang=lang,
        t=TRANSLATIONS[lang],
        series_list=list(SERIES.values()),
        default_series=SERIES[DEFAULT_SERIES],
        this_year=datetime.now().year,
        **context,
    )
    response = make_response(html)
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return response


def race_sessions(series, season, race):
    # F1 sends every session with the calendar; MotoGP and WorldSBK need one extra request per race.
    if race["sessions"] or not race.get("lazy"):
        return race["sessions"]
    try:
        return series.get_race_results(season, int(race["round"]))["sessions"]
    except Exception:
        app.logger.exception("Could not load sessions")
        return []


def feed_links(series_id, lang):
    url = url_for("calendar_feed", series_id=series_id, lang=lang, _external=True)
    webcal = "webcal://" + url.split("://", 1)[1]
    google = "https://calendar.google.com/calendar/render?cid=" + quote(webcal, safe="")
    return {"url": url, "webcal": webcal, "google": google}


# ---------- Home page ----------

def next_race_for(series, now):
    item = {"series": series, "race": None, "season": now.year, "sessions": [],
            "this_weekend": False, "ok": True}
    try:
        for season in (now.year, now.year + 1):
            upcoming = []
            for race in series.get_races(season):
                if race["main"]["when"] > now:
                    upcoming.append(race)
            if upcoming:
                item["race"] = upcoming[0]
                item["season"] = season
                break
    except Exception:
        app.logger.exception("Could not load next race")
        item["ok"] = False
        return item

    race = item["race"]
    if race is None:
        return item
    for session in race_sessions(series, item["season"], race):
        if not session["tbc"]:
            item["sessions"].append({**session, "past": session["when"] < now})
    if not race["main"]["tbc"]:
        item["this_weekend"] = race["main"]["when"].isocalendar()[:2] == now.isocalendar()[:2]
    return item


@app.route("/")
def index():
    lang = get_lang()
    now = datetime.now(timezone.utc)
    upcoming = []
    for series in SERIES.values():
        upcoming.append(next_race_for(series, now))
    # Soonest race first; series without a next race go last.
    upcoming.sort(key=lambda item: item["race"]["main"]["when"] if item["race"] else datetime.max.replace(tzinfo=timezone.utc))
    return render_page("home.html", lang, page="home", series=None, upcoming=upcoming)


@app.route("/<series_id>")
def series_home(series_id):
    get_series(series_id)
    return redirect(url_for("calendar", series_id=series_id, season=datetime.now().year))


@app.route("/<series_id>/<int:season>")
def calendar(series_id, season):
    lang = get_lang()
    series = get_series(series_id)
    seasons = get_seasons(series, season)
    try:
        races = add_statuses(series.get_races(season), season)
    except Exception:
        app.logger.exception("Could not load calendar")
        return error_page(lang)
    return render_page(
        "calendar.html", lang,
        page="calendar", series=series, season=season, seasons=seasons, races=races,
        feed=feed_links(series.ID, lang),
    )


@app.route("/<series_id>/<int:season>/standings")
def standings(series_id, season):
    lang = get_lang()
    series = get_series(series_id)
    seasons = get_seasons(series, season)
    try:
        table = series.get_standings(season)
    except Exception:
        app.logger.exception("Could not load standings")
        return error_page(lang)
    return render_page(
        "standings.html", lang,
        page="standings", series=series, season=season, seasons=seasons, standings=table,
    )


@app.route("/results/<series_id>/<int:season>/<int:round_number>")
def race_results(series_id, season, round_number):
    t = TRANSLATIONS[get_lang()]
    series = get_series(series_id)
    get_seasons(series, season)
    if round_number < 1 or round_number > 30:
        abort(404)
    try:
        results = series.get_race_results(season, round_number)
    except Exception:
        app.logger.exception("Could not load results")
        return f"<p class='note'>{t['unavailable']}</p>", 503
    response = make_response(render_template("results.html", r=results, t=t))
    if season < datetime.now().year:
        response.headers["Cache-Control"] = "public, max-age=86400"
    else:
        response.headers["Cache-Control"] = "public, max-age=300"
    return response


# ---------- Driver info (photo + short bio) ----------

@app.route("/driver-info")
def driver_info():
    series = get_series(request.args.get("series", ""))
    name = (request.args.get("name") or "").strip()[:80]
    if not name:
        abort(404)
    info = people.driver_info(name, series.ID, get_lang())
    response = jsonify(info)
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


# ---------- Calendar subscription (.ics) ----------

@app.route("/<series_id>/calendar.ics")
def calendar_feed(series_id):
    t = TRANSLATIONS[get_lang()]
    series = get_series(series_id)
    now = datetime.now(timezone.utc)
    events = []
    for season in (now.year, now.year + 1):
        try:
            races = series.get_races(season)
        except Exception:
            app.logger.exception("Could not load calendar feed")
            if season == now.year:
                # Better to fail than to send an empty calendar that wipes people's events.
                return t["unavailable"], 503
            continue

        detailed = 0
        for race in races:
            sessions = race["sessions"]
            soon = now < race["main"]["when"] < now + FEED_DETAIL_WINDOW
            if race.get("lazy") and soon and detailed < FEED_DETAIL_ROUNDS:
                sessions = race_sessions(series, season, race)
                detailed += 1
            link = url_for("calendar", series_id=series.ID, season=season, _external=True) + f"#round-{race['round']}"
            events.extend(ics.race_events(series, season, race, sessions, t, link))

    body = ics.make_calendar(f"{series.NAME} · {t['site_name']}", events)
    response = make_response(body)
    response.headers["Content-Type"] = "text/calendar; charset=utf-8"
    response.headers["Cache-Control"] = "public, max-age=1800"
    return response


# ---------- App install (home screen) ----------

@app.route("/manifest.webmanifest")
def manifest():
    response = make_response(MANIFEST)
    response.mimetype = "application/manifest+json"
    return response


@app.route("/about")
def about():
    return "<h1>About</h1><p>Calendars, results and standings for motorsport series.</p>"


@app.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="icons/icon-192.png"))


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, port=8000)
