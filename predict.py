import math
from datetime import datetime, timezone

import f1
import motogp
import season_results
import wsbk

# Kerbline's prediction: who wins the next race?
#
# Every driver gets a score between 0 and 1 from what they did earlier this season:
#   form    45%  points in the last 5 rounds, the latest counts most
#   season  30%  their points compared to the leader's
#   wins    25%  how often they won the race this season
# F1 also looks at the circuit: the average finish there in the last 3 years (20% of the score).
# Once qualifying is done, the starting position counts for half of the score.
#
# Scores become chances with a "softmax": the higher the score, the bigger the share,
# and all chances add up to 100%. SHARPNESS decides how much the favourite stands out.
#
# To be honest about how good it is, the same model is also run for every race that's
# already over (with only the data from before that race) and we count how often its favourite won.

SHARPNESS = 5.5
FORM_WEIGHTS = [1.0, 0.8, 0.6, 0.45, 0.3]
TRACK_YEARS = 3
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


# ---------- What every driver did before a round ----------

def driver_stats(series, data, before):
    rounds = [item["round"] for item in data["rounds"] if item["round"] < before]
    if len(rounds) < 2:
        return {}, rounds
    recent = list(reversed(rounds[-5:]))
    target = target_race(series)
    most = MAX_PER_ROUND.get(series.ID, 25) * sum(FORM_WEIGHTS[:len(recent)])

    stats = {}
    for name, driver in data["drivers"].items():
        # Only drivers who raced in one of the last two rounds: the others have probably left.
        if rounds[-1] not in driver["rounds"] and rounds[-2] not in driver["rounds"]:
            continue
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
        stats[name] = {"driver": driver, "points": points, "form": min(1, form), "wins": wins,
                       "recent_wins": recent_wins, "recent_podiums": recent_podiums, "recent": len(recent)}
    return stats, rounds


def scores(stats, rounds, track=None, grid=None):
    leader = max((s["points"] for s in stats.values()), default=0)
    result = {}
    for name, s in stats.items():
        score = 0.45 * s["form"] + 0.30 * (s["points"] / leader if leader else 0) + 0.25 * (s["wins"] / len(rounds))
        if track and name in track:
            score = 0.8 * score + 0.2 * track[name]["score"]
        if grid is not None:
            position = grid.get(name)
            grid_score = max(0, (21 - position) / 20) if position else 0.1
            score = 0.5 * score + 0.5 * grid_score
        result[name] = score
    return result


def to_chances(score_by_name, rounds_done):
    # Early in the season we know little, so the chances are kept closer together.
    sharpness = SHARPNESS * (0.5 + 0.5 * min(1, rounds_done / 6))
    exps = {name: math.exp(sharpness * score) for name, score in score_by_name.items()}
    total = sum(exps.values()) or 1
    return {name: value / total * 100 for name, value in exps.items()}


# ---------- F1 extras: circuit history and qualifying ----------

def f1_circuits(season):
    circuits = {}
    for race in f1.fetch_races(season):
        circuit = (race.get("Circuit") or {}).get("circuitId")
        if circuit:
            circuits[int(race["round"])] = circuit
    return circuits


def f1_track_history(season):
    # circuitId -> {driver: [finishing positions]} from the last few seasons
    history = {}
    for year in range(season - TRACK_YEARS, season):
        try:
            races = season_results.f1_pages(year, "results", "Results")
        except Exception:
            continue
        for entry in races.values():
            circuit = entry["race"]["Circuit"]["circuitId"]
            for row in entry["rows"].values():
                position = season_results.f1_position(row)
                name = row["Driver"]["givenName"] + " " + row["Driver"]["familyName"]
                history.setdefault(circuit, {}).setdefault(name, []).append(position if isinstance(position, int) else 20)
    return history


def track_for(history, circuit):
    track = {}
    for name, positions in history.get(circuit, {}).items():
        average = sum(positions) / len(positions)
        track[name] = {"score": max(0, (21 - average) / 20), "average": average}
    return track


# ---------- Starting grid (once qualifying is over) ----------

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


# ---------- Putting it together ----------

def reasons_for(stat, track, grid_position, leader_name, lang):
    text = REASONS[lang]
    reasons = []
    if grid_position == 1:
        reasons.append(text["pole"])
    elif grid_position and grid_position <= 3:
        reasons.append(text["grid"].format(n=grid_position))
    if stat["recent_wins"] == 1:
        reasons.append(text["win"].format(k=stat["recent"]))
    elif stat["recent_wins"] > 1:
        reasons.append(text["wins"].format(w=stat["recent_wins"], k=stat["recent"]))
    elif stat["recent_podiums"] >= 2:
        reasons.append(text["podiums"].format(p=stat["recent_podiums"], k=stat["recent"]))
    if stat["driver"]["name"] == leader_name:
        reasons.append(text["leader"])
    if track and track["average"] <= 6:
        reasons.append(text["track"].format(avg=round(track["average"]), years=TRACK_YEARS))
    if not reasons and stat["form"] > 0.4:
        reasons.append(text["form"])
    return reasons[:2]


def predict(series, season, lang):
    data = season_results.get_season(series, season)
    target = target_race(series)
    circuits = f1_circuits(season) if series.ID == "f1" else {}
    history = f1_track_history(season) if circuits else {}

    # How the favourite did in every race that's already over.
    record = {"hits": 0, "races": 0}
    past = {}
    for item in data["rounds"]:
        stats, rounds = driver_stats(series, data, item["round"])
        if not stats:
            continue
        winner = None
        for name, driver in data["drivers"].items():
            if race_position(driver["rounds"].get(item["round"]), target) == 1:
                winner = name
        if winner is None:
            continue
        chances = to_chances(scores(stats, rounds, track_for(history, circuits.get(item["round"]))), len(rounds))
        favourite = max(chances, key=chances.get)
        hit = favourite == winner
        record["races"] += 1
        record["hits"] += hit
        past[str(item["round"])] = {"favourite": favourite, "chance": round(chances[favourite]),
                                    "winner": winner, "hit": hit}

    result = {"race": None, "basis": "form", "drivers": [], "record": record, "past": past}

    # The next race of this season.
    now = datetime.now(timezone.utc)
    upcoming = None
    for race in series.get_races(season):
        if race["main"]["when"] > now:
            upcoming = race
            break
    if upcoming is None:
        return result
    number = int(upcoming["round"])
    stats, rounds = driver_stats(series, data, number)
    if not stats:
        return result

    try:
        grid = upcoming_grid(series, season, number) or None
    except Exception:
        grid = None
    track = track_for(history, circuits.get(number))
    chances = to_chances(scores(stats, rounds, track, grid), len(rounds))
    leader_name = max(stats.values(), key=lambda s: s["points"])["driver"]["name"]

    result["race"] = {"round": number, "name": upcoming["name"], "flag": upcoming["flag"], "target": target}
    result["basis"] = "grid" if grid else "form"
    for name in sorted(chances, key=chances.get, reverse=True)[:TOP]:
        driver = stats[name]["driver"]
        result["drivers"].append({
            "name": name,
            "short": name.split()[-1],
            "slug": driver["slug"],
            "team": driver["team"],
            "color": driver["color"],
            "flag": driver.get("flag", ""),
            "chance": round(chances[name], 1),
            "reasons": reasons_for(stats[name], track.get(name), (grid or {}).get(name), leader_name, lang),
        })
    return result
