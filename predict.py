import math
import threading
from datetime import datetime, timedelta, timezone

import f1
import motogp
import season_results
import tracks
import weather
import wsbk

# Kerbline's prediction: who wins the next race?
#
# Every driver gets a score between 0 and 1 from several factors. A factor we have no data for
# (say, a track the series has never visited) is simply left out and the others count more.
#
#   driver form    22%  the driver's points in the last 5 rounds (the latest counts most)
#   season         13%  the driver's points compared to the leader's
#   wins           10%  how often they won the race this season
#   car form       20%  points of the car (F1 team / MotoGP manufacturer / WorldSBK team) in the last 5 rounds
#   car and track  15%  F1: how the car did on tracks of the same kind (fast, street, ...) this year and last
#                       bikes: how the bike did at this very circuit last year
#   driver here    10%  how the driver finished at this circuit before (F1: last 3 years, bikes: last year)
#
# Then two things that are only known close to the race:
#   rain           if rain is forecast, how the driver does in wet races counts in (more rain, more weight)
#   grid           once qualifying is done, the starting position is half of the score
#
# Scores become chances with a "softmax": a higher score gets a bigger share and all chances add up to 100%.
#
# To be honest about how good it is, the same model also runs for every race that's already over,
# with only what was known before that race (without weather), and we count how often its favourite won.

WEIGHTS = {"form": 0.22, "season": 0.13, "wins": 0.10, "car_form": 0.20, "car_track": 0.15, "driver_track": 0.10}
SHARPNESS = 5.5
FORM_WEIGHTS = [1.0, 0.8, 0.6, 0.45, 0.3]
HISTORY_SEASONS = {"f1": 3}      # bikes: 1 (loading old MotoGP seasons is slow)
RAIN_FROM = 0.3                  # below 30% chance of rain the weather is ignored
TOP = 5

# The most points one driver can score in one round: race + sprint (WorldSBK: three races).
MAX_PER_ROUND = {"f1": 33, "motogp": 37, "moto2": 25, "moto3": 25, "wsbk": 62}

REASONS = {
    "en": {
        "pole": "Starts from pole",
        "grid": "Starts P{n}",
        "wins": "{w} wins in the last {k} races",
        "win": "1 win in the last {k} races",
        "podiums": "{p} podiums in the last {k} races",
        "leader": "Leads the championship",
        "track": "Averaged P{avg} here over the last {years} years",
        "here": "Finished P{pos} here last year",
        "car_best": "The fastest car right now",
        "car_top": "One of the fastest cars right now",
        "car_type_street": "The car suits street circuits",
        "car_type_fast": "The car suits fast tracks",
        "car_type_technical": "The car suits twisty tracks",
        "car_type_balanced": "The car suits all-round tracks",
        "car_here": "The bike was strong here last year",
        "bike_best": "The fastest bike right now",
        "bike_top": "One of the fastest bikes right now",
        "wet": "Strong in the wet",
        "form": "In good form lately",
    },
    "tr": {
        "pole": "Pole pozisyonundan başlıyor",
        "grid": "{n}. sıradan başlıyor",
        "wins": "Son {k} yarışta {w} galibiyet",
        "win": "Son {k} yarışta 1 galibiyet",
        "podiums": "Son {k} yarışta {p} podyum",
        "leader": "Şampiyona lideri",
        "track": "Bu pistte son {years} yılda ortalama {avg}. bitirdi",
        "here": "Geçen yıl burada {pos}. bitirdi",
        "car_best": "Şu an en hızlı araç onda",
        "car_top": "Şu an en hızlı araçlardan biri onda",
        "car_type_street": "Aracı sokak pistlerinde güçlü",
        "car_type_fast": "Aracı hızlı pistlerde güçlü",
        "car_type_technical": "Aracı virajlı pistlerde güçlü",
        "car_type_balanced": "Aracı dengeli pistlerde güçlü",
        "car_here": "Motosikleti geçen yıl bu pistte güçlüydü",
        "bike_best": "Şu an en hızlı motosiklet onda",
        "bike_top": "Şu an en hızlı motosikletlerden biri onda",
        "wet": "Islak zeminde güçlü",
        "form": "Son yarışlarda formda",
    },
}


def target_race(series):
    # WorldSBK has three races a weekend; we predict the first one.
    return "Race 1" if series.ID == "wsbk" else "Race"


def race_position(result, target):
    if not result:
        return None
    for race in result["races"]:
        if race["label"] == target:
            return race["position"]
    return None


def finish_score(position):
    # P1 = 1.0, P20 = 0.05, did not finish = 0.05
    if isinstance(position, int):
        return max(0.0, (21 - position) / 20)
    return 0.05


def average(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def parse_start(text):
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def track_type(series, circuit):
    return tracks.F1_TRACK_TYPES.get(circuit) if series.ID == "f1" else None


# ---------- Everything we know before a round ----------

class History:
    # This season plus earlier seasons, in one list of past races: [(season, round info, data)].
    def __init__(self, series, season):
        self.series = series
        self.season = season
        self.current = season_results.get_season(series, season)
        self.earlier = []
        for year in range(season - HISTORY_SEASONS.get(series.ID, 1), season):
            try:
                self.earlier.append((year, season_results.get_season(series, year)))
            except Exception:
                continue

    def past_races(self, before):
        # Every race before round `before` of this season, oldest first.
        races = []
        for year, data in self.earlier:
            for item in data["rounds"]:
                races.append((year, item, data))
        for item in self.current["rounds"]:
            if item["round"] < before:
                races.append((self.season, item, self.current))
        return races


def car_results(data, round_number, target):
    # {car: [finish scores of its drivers]} for one round
    cars = {}
    for driver in data["drivers"].values():
        result = driver["rounds"].get(round_number)
        if result and result.get("car"):
            cars.setdefault(result["car"], []).append(finish_score(race_position(result, target)))
    return cars


def driver_stats(history, before, circuit):
    series = history.series
    data = history.current
    rounds = [item["round"] for item in data["rounds"] if item["round"] < before]
    if len(rounds) < 2:
        return {}, rounds
    recent = list(reversed(rounds[-5:]))
    target = target_race(series)
    most = MAX_PER_ROUND.get(series.ID, 25) * sum(FORM_WEIGHTS[:len(recent)])

    # The car's form: points of all its drivers in the last rounds.
    car_points = {}
    for driver in data["drivers"].values():
        for weight, r in zip(FORM_WEIGHTS, recent):
            result = driver["rounds"].get(r)
            if result and result.get("car"):
                car_points[result["car"]] = car_points.get(result["car"], 0) + weight * result["points"]
    best_car = max(car_points.values(), default=0) or 1

    # The car on this kind of track (F1) or at this circuit (bikes), and every driver's record here.
    kind = track_type(series, circuit)
    car_track = {}
    driver_here = {}
    for year, item, source in history.past_races(before):
        same_kind = kind is not None and track_type(series, item.get("circuit")) == kind and year >= history.season - 1
        same_place = circuit is not None and item.get("circuit") == circuit
        if same_kind or (kind is None and same_place):
            for car, values in car_results(source, item["round"], target).items():
                car_track.setdefault(car, []).append(max(values))
        if same_place:
            for name, driver in source["drivers"].items():
                position = race_position(driver["rounds"].get(item["round"]), target)
                if position is not None:
                    driver_here.setdefault(name, []).append((year, position))
    car_track = {car: average(values) for car, values in car_track.items() if len(values) >= (2 if kind else 1)}
    best_track = max(car_track.values(), default=0) or 1

    stats = {}
    leader = 0
    for name, driver in data["drivers"].items():
        # Only drivers who raced in one of the last two rounds: the others have probably left.
        last = driver["rounds"].get(rounds[-1]) or driver["rounds"].get(rounds[-2])
        if last is None:
            continue
        car = last.get("car")
        points = sum(driver["rounds"].get(r, {}).get("points", 0) for r in rounds)
        form = sum(w * driver["rounds"].get(r, {}).get("points", 0) for w, r in zip(FORM_WEIGHTS, recent)) / most
        wins = recent_wins = recent_podiums = 0
        for r in rounds:
            position = race_position(driver["rounds"].get(r), target)
            if position == 1:
                wins += 1
            if r in recent and isinstance(position, int):
                recent_wins += position == 1
                recent_podiums += position <= 3
        here = driver_here.get(name, [])
        stats[name] = {
            "driver": driver, "car": car, "points": points, "wins": wins,
            "recent": len(recent), "recent_wins": recent_wins, "recent_podiums": recent_podiums,
            "form": min(1, form),
            "car_form": car_points.get(car, 0) / best_car if car in car_points else None,
            "car_track": car_track[car] / best_track if car in car_track else None,
            "driver_track": average([finish_score(p) for _, p in here]),
            "here": here,
        }
        leader = max(leader, points)
    for s in stats.values():
        s["season"] = s["points"] / leader if leader else 0
        s["wins_rate"] = s["wins"] / len(rounds)
    return stats, rounds


def wet_skill(history, before):
    # {driver: (wet score, dry score)} from earlier races, using the weather archive. Only asked when rain is forecast.
    target = target_race(history.series)
    races = {}
    for year, item, source in history.past_races(before):
        start = parse_start(item.get("start"))
        if start and item.get("lat") is not None:
            races[(year, item["round"])] = (item["lat"], item["lon"], start)
    wet = weather.wet_races(races)

    scores = {}
    for year, item, source in history.past_races(before):
        flag = wet.get((year, item["round"]))
        if flag is None:
            continue
        for name, driver in source["drivers"].items():
            position = race_position(driver["rounds"].get(item["round"]), target)
            if position is not None:
                scores.setdefault(name, {True: [], False: []})[flag].append(finish_score(position))
    skill = {}
    for name, values in scores.items():
        if len(values[True]) >= 2 and values[False]:
            skill[name] = (average(values[True]), average(values[False]))
    return skill


def score_of(stat, grid=None, rain=0, wet=None):
    total = 0
    weights = 0
    for factor, weight in WEIGHTS.items():
        value = stat["wins_rate"] if factor == "wins" else stat.get(factor)
        if value is not None:
            total += weight * value
            weights += weight
    score = total / weights if weights else 0
    if rain >= RAIN_FROM and wet:
        # More rain expected = the wet record counts more (at most 35%).
        share = 0.35 * rain
        score = (1 - share) * score + share * wet[0]
    if grid is not None:
        position = grid.get(stat["driver"]["name"])
        score = 0.5 * score + 0.5 * (max(0, (21 - position) / 20) if position else 0.1)
    return score


def to_chances(score_by_name, rounds_done):
    # Early in the season we know little, so the chances are kept closer together.
    sharpness = SHARPNESS * (0.5 + 0.5 * min(1, rounds_done / 6))
    exps = {name: math.exp(sharpness * score) for name, score in score_by_name.items()}
    total = sum(exps.values()) or 1
    return {name: value / total * 100 for name, value in exps.items()}


# ---------- The next race: where, when and the starting grid ----------

def next_race(series, season):
    now = datetime.now(timezone.utc)
    for race in series.get_races(season):
        if race["main"]["when"] > now:
            return race
    return None


def race_place(series, season, race):
    # (circuit key, latitude, longitude, start time) of an upcoming race; parts can be None.
    number = int(race["round"])
    start = race["main"]["when"] if not race["main"]["tbc"] else None
    if series.ID == "f1":
        for item in f1.fetch_races(season):
            if int(item["round"]) == number:
                circuit = item.get("Circuit") or {}
                location = circuit.get("Location") or {}
                lat = float(location["lat"]) if location.get("lat") else None
                lon = float(location["long"]) if location.get("long") else None
                return circuit.get("circuitId"), lat, lon, start
        return None, None, None, start
    if series.ID == "wsbk":
        for item in wsbk.fetch_rounds(season):
            attrs = item.get("attributes") or {}
            if attrs.get("sequence_order") == number:
                words = (attrs.get("brief_description") or "") + " " + (attrs.get("name") or "")
                place = tracks.moto_circuit("wsbk", attrs.get("country_iso"), words)
                for session in wsbk.fetch_sessions(season, attrs.get("source_id")):
                    if session["attributes"].get("short_name") == "RC1":
                        start = parse_start(session["attributes"].get("start_date_utc")) or start
                return (place or (None, None, None)) + (start,)
        return None, None, None, start
    events = motogp.grand_prix_events(season)
    if number > len(events):
        return None, None, None, start
    event = events[number - 1]
    place = tracks.moto_circuit(series.ID, event["country"]["iso"], event["name"])
    return (place or (None, None, None)) + (start,)


def upcoming_grid(series, season, round_number):
    if series.ID == "f1":
        rows = f1.fetch_round(season, round_number, "qualifying", "QualifyingResults")
        return {f1.make_driver(row)["name"]: int(row["position"]) for row in rows}

    if series.ID == "wsbk":
        for item in wsbk.fetch_rounds(season):
            attrs = item.get("attributes") or {}
            if attrs.get("sequence_order") != round_number:
                continue
            for session in wsbk.fetch_sessions(season, attrs["source_id"]):
                sattrs = session["attributes"]
                if sattrs.get("short_name") == "SP" and sattrs.get("status") == "FINISHED":
                    rows, index = wsbk.fetch_results(season, attrs["source_id"], sattrs["source_id"])
                    brands = wsbk.model_brands(rows, index)
                    return {wsbk.make_rider(row, index, brands)["name"]: (row.get("attributes") or {}).get("position")
                            for row in rows if (row.get("attributes") or {}).get("position")}
        return {}

    events = motogp.grand_prix_events(season)
    if round_number > len(events):
        return {}
    for session in series.event_sessions(season, events[round_number - 1]):
        if motogp.session_label(session) == "Qualifying 2" and session.get("status") == "FINISHED":
            return {motogp.make_rider(row)["name"]: row["position"]
                    for row in motogp.classification(session["id"], season) if row.get("position")}
    return {}


# ---------- Reasons ("why") ----------

def reasons_for(series, stat, kind, grid_position, rain, wet, leader_name):
    # A list of [code, values] pairs; app.py turns them into text in the page's language.
    reasons = []
    if grid_position == 1:
        reasons.append(["pole", {}])
    elif grid_position and grid_position <= 3:
        reasons.append(["grid", {"n": grid_position}])
    if rain >= RAIN_FROM and wet and wet[0] - wet[1] >= 0.08:
        reasons.append(["wet", {}])
    if stat["recent_wins"] == 1:
        reasons.append(["win", {"k": stat["recent"]}])
    elif stat["recent_wins"] > 1:
        reasons.append(["wins", {"w": stat["recent_wins"], "k": stat["recent"]}])
    elif stat["recent_podiums"] >= 2:
        reasons.append(["podiums", {"p": stat["recent_podiums"], "k": stat["recent"]}])
    # "Suits this track" only when the car does better here than it does in general.
    if stat["car_track"] is not None and stat["car_track"] >= 0.95 and stat["car_track"] > (stat["car_form"] or 0):
        reasons.append(["car_type_" + kind, {}] if kind else ["car_here", {}])
    machine = "car" if series.ID == "f1" else "bike"
    if stat["car_form"] == 1:
        reasons.append([machine + "_best", {}])
    elif stat["car_form"] is not None and stat["car_form"] >= 0.85:
        reasons.append([machine + "_top", {}])
    if stat["driver"]["name"] == leader_name:
        reasons.append(["leader", {}])
    if stat["here"]:
        if series.ID == "f1":
            avg = average([p if isinstance(p, int) else 20 for _, p in stat["here"]])
            if avg <= 6:
                reasons.append(["track", {"avg": round(avg), "years": HISTORY_SEASONS["f1"]}])
        else:
            year, position = stat["here"][-1]
            if isinstance(position, int) and position <= 3:
                reasons.append(["here", {"pos": position}])
    if not reasons and stat["form"] > 0.4:
        reasons.append(["form", {}])
    return reasons[:3]


def reason_text(reasons, lang):
    text = REASONS[lang]
    return [text[code].format(**values) for code, values in reasons]


# ---------- Putting it together ----------

def make_prediction(series, season):
    history = History(series, season)
    data = history.current
    target = target_race(series)

    # How the favourite did in every race that's already over (no weather, no grid: only what was known before).
    record = {"hits": 0, "races": 0}
    past = {}
    for item in data["rounds"]:
        stats, rounds = driver_stats(history, item["round"], item.get("circuit"))
        if not stats:
            continue
        winner = None
        for name, driver in data["drivers"].items():
            if race_position(driver["rounds"].get(item["round"]), target) == 1:
                winner = name
        if winner is None:
            continue
        chances = to_chances({name: score_of(s) for name, s in stats.items()}, len(rounds))
        favourite = max(chances, key=chances.get)
        record["races"] += 1
        record["hits"] += favourite == winner
        past[str(item["round"])] = {"favourite": favourite, "chance": round(chances[favourite]),
                                    "winner": winner, "hit": favourite == winner}

    result = {"race": None, "basis": "form", "drivers": [], "record": record, "past": past,
              "weather": None, "track_type": None}

    race = next_race(series, season)
    if race is None:
        return result
    number = int(race["round"])
    circuit, lat, lon, start = race_place(series, season, race)
    stats, rounds = driver_stats(history, number, circuit)
    if not stats:
        return result

    forecast = weather.forecast(lat, lon, start) if lat is not None and start else None
    rain = forecast["rain"] if forecast else 0
    wet = wet_skill(history, number) if rain >= RAIN_FROM else {}
    try:
        grid = upcoming_grid(series, season, number) or None
    except Exception:
        grid = None

    kind = track_type(series, circuit)
    chances = to_chances({name: score_of(s, grid, rain, wet.get(name)) for name, s in stats.items()}, len(rounds))
    leader_name = max(stats.values(), key=lambda s: s["points"])["driver"]["name"]

    result["race"] = {"round": number, "name": race["name"], "flag": race["flag"], "target": target}
    result["basis"] = "grid" if grid else "form"
    result["weather"] = forecast
    result["track_type"] = kind
    for name in sorted(chances, key=chances.get, reverse=True)[:TOP]:
        stat = stats[name]
        driver = stat["driver"]
        result["drivers"].append({
            "name": name,
            "short": name.split()[-1],
            "slug": driver["slug"],
            "team": driver["team"],
            "color": driver["color"],
            "flag": driver.get("flag", ""),
            "chance": round(chances[name], 1),
            "reasons": reasons_for(series, stat, kind, (grid or {}).get(name), rain, wet.get(name), leader_name),
        })
    return result


# ---------- Worked out in the background ----------
# The first time after a restart this can take a minute (old seasons, weather), longer than a web request
# may take. So the page asks, we start working in the background and answer "not ready yet";
# predict.js asks again every few seconds. Meanwhile an older answer is used if we have one.

FRESH_FOR = timedelta(minutes=15)
results = {}
running = set()
failed = {}
jobs_lock = threading.Lock()


def work(series, season, key):
    try:
        data = make_prediction(series, season)
        with jobs_lock:
            results[key] = {"data": data, "at": datetime.now()}
            failed.pop(key, None)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Prediction failed")
        with jobs_lock:
            failed[key] = datetime.now()
    finally:
        with jobs_lock:
            running.discard(key)


def get_prediction(series, season):
    # Returns (data or None, state): state is "ready", "pending" or "failed".
    key = (series.ID, season)
    with jobs_lock:
        hit = results.get(key)
        fresh = hit and datetime.now() - hit["at"] < FRESH_FOR
        if not fresh and key not in running:
            running.add(key)
            threading.Thread(target=work, args=(series, season, key), daemon=True).start()
        recently_failed = key in failed and datetime.now() - failed[key] < timedelta(minutes=2)
    if hit:
        return hit["data"], "ready"
    if recently_failed and key not in running:
        return None, "failed"
    return None, "pending"


def for_page(data, lang):
    # A copy of the prediction with the reasons written out in the page's language.
    copy = dict(data)
    copy["drivers"] = [dict(driver, reasons=reason_text(driver["reasons"], lang)) for driver in data["drivers"]]
    return copy
