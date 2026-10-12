from datetime import datetime

from flask import Flask, abort, make_response, redirect, render_template, request, url_for

import f1
import motogp
import wsbk
from core import add_statuses

app = Flask(__name__)

SERIES = {f1.ID: f1, motogp.ID: motogp, wsbk.ID: wsbk}
DEFAULT_SERIES = f1.ID

TRANSLATIONS = {
    "en": {
        "site_name": "Kerbline",
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
    },
    "tr": {
        "site_name": "Kerbline",
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
        **context,
    )
    response = make_response(html)
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return response


@app.route("/")
def index():
    return redirect(url_for("series_home", series_id=DEFAULT_SERIES))


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


@app.route("/about")
def about():
    return "<h1>About</h1><p>Calendars, results and standings for motorsport series.</p>"


@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(debug=True, port=8000)