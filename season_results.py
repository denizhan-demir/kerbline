import re
import unicodedata
from datetime import datetime, timedelta, timezone

import f1
import motogp
import wsbk
from core import flag_for_country, get_cached, to_flag

# Every race of a season, driver by driver: where they finished and how many points they scored.
# The championship chart and the driver pages are built from this.
#
# The result looks like this for every series:
# {
#     "rounds": [{"round": 1, "name": "Australian Grand Prix", "flag": "🇦🇺"}, ...],   # finished rounds only
#     "drivers": {
#         "Max Verstappen": {
#             "name": ..., "slug": "max-verstappen", "flag": ..., "team": ..., "color": ..., "id": ...,
#             "rounds": {1: {"races": [{"label": "Sprint", "position": 2, "main": False}, ...], "points": 33}},
#         },
#     },
# }

# Results of rounds that finished a few days ago don't change any more, so they're kept longer.
SETTLED_AFTER = timedelta(days=2)
KEEP_SETTLED = timedelta(days=3)

# Columns on the driver page, in the order the races happen on a weekend.
RACE_ORDER = ["Sprint", "Race", "Race 1", "Superpole Race", "Race 2"]

# When three or more drivers in the chart share a team colour (lots of Ducatis, lots of Kalex in Moto2),
# the extra ones get one of these instead.
SPARE_COLORS = ["#4dd4ac", "#ff7aa2", "#9ad0ff", "#c9a7ff", "#ffb36b", "#f5c84c"]

# WorldSBK doesn't send points with each race, so we count them ourselves.
WSBK_POINTS = {
    "RC1": [25, 20, 16, 13, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    "SPRC": [12, 9, 7, 6, 5, 4, 3, 2, 1],
    "RC2": [25, 20, 16, 13, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
}


def slugify(name):
    # "Fabio Di Giannantonio" -> "fabio-di-giannantonio", "Toprak Razgatlıoğlu" -> "toprak-razgatlioglu"
    text = unicodedata.normalize("NFKD", (name or "").replace("ı", "i"))
    text = text.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def max_age(season, finished_on):
    # finished_on: the last day of the round, like "2026-10-25".
    settled = (datetime.now(timezone.utc) - SETTLED_AFTER).date().isoformat()
    if finished_on and finished_on < settled:
        return KEEP_SETTLED
    if season < datetime.now().year:
        return timedelta(hours=24)
    return timedelta(minutes=30)


def add_result(drivers, info, round_number, label, position, points, main):
    driver = drivers.get(info["name"])
    if driver is None:
        driver = {**info, "slug": slugify(info["name"]), "rounds": {}}
        drivers[info["name"]] = driver
    # The team and colour of the latest race win, in case someone changed teams.
    driver["team"] = info["team"]
    driver["color"] = info["color"]
    result = driver["rounds"].setdefault(round_number, {"races": [], "points": 0})
    result["races"].append({"label": label, "position": position, "main": main})
    result["points"] += points


# ---------- Formula 1 ----------

def f1_pages(season, endpoint, key):
    # Jolpica sends at most 100 rows at a time, a season has about 500, so we ask page by page.
    races = {}
    offset = 0
    while True:
        url = f"{f1.BASE_URL}/{season}/{endpoint}.json?limit=100&offset={offset}"
        data = get_cached(url, f1.max_age_for(season))["MRData"]
        for race in data["RaceTable"]["Races"]:
            entry = races.setdefault(int(race["round"]), {"race": race, "rows": {}})
            for row in race.get(key, []):
                # Keyed by driver, so a row that shows up on two pages is only counted once.
                entry["rows"][row["Driver"]["driverId"]] = row
        offset += 100
        if offset >= int(data.get("total", 0)):
            return races


def f1_position(row):
    text = row.get("positionText", row.get("position", ""))
    if text.isdigit():
        return int(text)
    return f1.POSITION_LABELS.get(text, text)


def f1_season(season):
    races = f1_pages(season, "results", "Results")
    sprints = f1_pages(season, "sprint", "SprintResults")
    rounds = []
    drivers = {}
    for number in sorted(races):
        race = races[number]["race"]
        country = race["Circuit"]["Location"]["country"]
        rounds.append({"round": number, "name": race["raceName"], "flag": flag_for_country(country)})
        for label, source, main in (("Sprint", sprints, False), ("Race", races, True)):
            for row in (source.get(number) or {"rows": {}})["rows"].values():
                info = f1.make_driver(row)
                info["id"] = row["Driver"]["driverId"]
                add_result(drivers, info, number, label, f1_position(row), float(row.get("points", 0)), main)
    return {"rounds": rounds, "drivers": drivers}


def f1_career(driver_id):
    # Whole-career numbers, straight from Jolpica's counters ("total").
    def total(path):
        url = f"{f1.BASE_URL}/drivers/{driver_id}/{path}.json?limit=100"
        return get_cached(url, timedelta(hours=24))["MRData"]

    wins = int(total("results/1")["total"])
    titles = 0
    for item in total("driverStandings/1")["StandingsTable"]["StandingsLists"]:
        # Leading this year's standings isn't a title yet, so only past seasons count.
        if int(item["season"]) < datetime.now().year:
            titles += 1
    return {
        "starts": int(total("results")["total"]),
        "wins": wins,
        "podiums": wins + int(total("results/2")["total"]) + int(total("results/3")["total"]),
        "poles": int(total("qualifying/1")["total"]),
        "titles": titles,
    }


# ---------- MotoGP, Moto2 and Moto3 ----------

def moto_season(series, season):
    today = datetime.now(timezone.utc).date().isoformat()
    season_uuid = motogp.season_id(season)
    if season_uuid is None:
        return {"rounds": [], "drivers": {}}
    category_uuid = series.category_id(season_uuid)

    rounds = []
    drivers = {}
    for number, event in enumerate(motogp.grand_prix_events(season), start=1):
        if event["date_start"] > today:
            break
        age = max_age(season, event["date_end"])
        url = f"{motogp.BASE_URL}/results/sessions?eventUuid={event['id']}&categoryUuid={category_uuid}"
        finished = {}
        for session in get_cached(url, age):
            if session.get("status") == "FINISHED":
                finished[motogp.session_label(session)] = session["id"]

        found = False
        for label, main in (("Sprint", False), ("Race", True)):
            if label not in finished:
                continue
            url = f"{motogp.BASE_URL}/results/session/{finished[label]}/classification?test=false"
            for row in get_cached(url, age).get("classification", []):
                position = row.get("position") or "DNF"
                add_result(drivers, motogp.make_rider(row), number, label, position, row.get("points") or 0, main)
                found = True
        if found:
            rounds.append({"round": number, "name": motogp.pretty_name(event["name"]),
                           "flag": to_flag(event["country"]["iso"])})
    return {"rounds": rounds, "drivers": drivers}


# ---------- WorldSBK ----------

def wsbk_season(season):
    today = datetime.now(timezone.utc).date().isoformat()
    rounds = []
    drivers = {}
    for item in wsbk.fetch_rounds(season):
        attrs = item.get("attributes") or {}
        start = (attrs.get("start_date") or attrs.get("end_date") or "")[:10]
        if not start or start > today:
            break
        age = max_age(season, (attrs.get("end_date") or "")[:10])
        round_code = attrs.get("source_id")
        number = attrs.get("sequence_order")

        url = f"{wsbk.EVENTS_URL}/seasons/{season}/rounds/{round_code}/sessions"
        finished = {}
        for session in get_cached(url, age).get("data") or []:
            sattrs = session.get("attributes") or {}
            if wsbk.related_id(session, "category") == wsbk.CATEGORY and sattrs.get("status") == "FINISHED":
                finished[sattrs.get("short_name")] = sattrs.get("source_id")

        found = False
        for code, label in wsbk.RACES.items():
            if code not in finished:
                continue
            url = (f"{wsbk.RESULTS_URL}/seasons/{season}/categories/{wsbk.CATEGORY}"
                   f"/rounds/{round_code}/sessions/{finished[code]}/results")
            data = get_cached(url, age)
            rows = data.get("data") or []
            rows.sort(key=lambda r: (r.get("attributes") or {}).get("position") or 999)
            index = wsbk.index_included(data)
            brands = wsbk.model_brands(rows, index)
            table = WSBK_POINTS[code]
            for row in rows:
                rattrs = row.get("attributes") or {}
                if rattrs.get("status") == "Classified" and rattrs.get("position"):
                    position = rattrs["position"]
                    points = table[position - 1] if position <= len(table) else 0
                else:
                    position = wsbk.STATUS_LABELS.get(rattrs.get("status"), "NC")
                    points = 0
                add_result(drivers, wsbk.make_rider(row, index, brands), number, label, position, points, True)
                found = True
        if found:
            rounds.append({"round": number, "name": attrs.get("brief_description") or attrs.get("name", ""),
                           "flag": wsbk.flag_for(attrs.get("country_iso"))})
    return {"rounds": rounds, "drivers": drivers}


# ---------- For app.py ----------

def get_season(series, season):
    if series.ID == "f1":
        return f1_season(season)
    if series.ID == "wsbk":
        return wsbk_season(season)
    return moto_season(series, season)


def progress(series, season, standings, how_many=6):
    # Points after every round for the top drivers of the standings: the championship chart.
    data = get_season(series, season)
    lines = []
    used_colors = {}
    for row in standings["drivers"]:
        driver = data["drivers"].get(row["name"])
        if driver is None:
            continue
        total = 0
        points = []
        for item in data["rounds"]:
            total += driver["rounds"].get(item["round"], {}).get("points", 0)
            points.append(round(total, 1))
        # Teammates share a colour, so the second one gets a dashed line and a third one another colour.
        color = driver["color"]
        times_used = used_colors.get(color, 0)
        if times_used >= 2:
            for spare in SPARE_COLORS:
                if spare not in used_colors:
                    color = spare
                    times_used = 0
                    break
        used_colors[color] = times_used + 1
        lines.append({
            "name": driver["name"],
            "short": driver["name"].split()[-1],
            "slug": driver["slug"],
            "color": color,
            "dashed": times_used == 1,
            "points": points,
        })
        if len(lines) == how_many:
            break
    return {"rounds": data["rounds"], "lines": lines}


def driver_season(series, season, slug):
    # One driver's season, race by race, plus a few numbers worked out from it.
    data = get_season(series, season)
    driver = None
    for item in data["drivers"].values():
        if item["slug"] == slug:
            driver = item
    if driver is None:
        return None

    results = []
    labels = []
    stats = {"wins": 0, "podiums": 0, "best": None, "dnf": 0, "starts": 0}
    for item in data["rounds"]:
        result = driver["rounds"].get(item["round"])
        if result is None:
            continue
        for race in result["races"]:
            if race["label"] not in labels:
                labels.append(race["label"])
            position = race["position"]
            if not race["main"]:
                continue
            stats["starts"] += 1
            if isinstance(position, int):
                if position == 1:
                    stats["wins"] += 1
                if position <= 3:
                    stats["podiums"] += 1
                if stats["best"] is None or position < stats["best"]:
                    stats["best"] = position
            else:
                stats["dnf"] += 1
        results.append({**item, "races": result["races"], "points": round(result["points"], 1)})

    labels.sort(key=lambda label: RACE_ORDER.index(label) if label in RACE_ORDER else len(RACE_ORDER))
    return {"driver": driver, "results": results, "labels": labels, "stats": stats}
