from datetime import datetime, timedelta, timezone

import f1
import motogp
import wsbk
from core import get_cached

# Is the title decided? A championship is settled when the leader is further ahead
# than the most points the second-placed driver (or team) can still score.
#
# What one driver / one team can score at most in one race:
#   F1:      race 25 (a team: 25 + 18 with both cars), sprint 8 (team: 8 + 7)
#   MotoGP:  race 25, sprint 12; a team scores with both riders (25 + 20, 12 + 9),
#            a manufacturer only with its best rider (25, 12). Moto2 and Moto3 have no sprint.
#   WorldSBK: Race 1 25, Superpole Race 12, Race 2 25; a manufacturer only with its best rider.

# Results need a moment to reach the standings, so a race only counts as done a while after it starts.
RESULTS_DELAY = timedelta(hours=3)

# Colours for the confetti. Teams not listed get shades of their own colour.
TEAM_PALETTES = {
    # Formula 1
    "#27F4D2": ["#27F4D2", "#C8CCD2", "#111111", "#FFFFFF"],             # Mercedes
    "#3671C6": ["#3671C6", "#1B2A55", "#E8112D", "#FFCC00"],             # Red Bull
    "#E8002D": ["#E8002D", "#FFEB00", "#FFFFFF", "#8C0019"],             # Ferrari
    "#FF8000": ["#FF8000", "#47C7FC", "#FFFFFF", "#1A1A1A"],             # McLaren
    "#229971": ["#229971", "#CEDC00", "#FFFFFF", "#0B3D2C"],             # Aston Martin
    "#0093CC": ["#0093CC", "#FF87BC", "#FFFFFF"],                        # Alpine
    "#64C4FF": ["#64C4FF", "#041E42", "#FFFFFF"],                        # Williams
    "#6692FF": ["#6692FF", "#FFFFFF", "#E8112D"],                        # RB
    "#52E252": ["#52E252", "#111111", "#FFFFFF"],                        # Sauber
    "#B6BABD": ["#B6BABD", "#E6002B", "#FFFFFF", "#111111"],             # Haas
    # Motorcycles
    "#E2231A": ["#E2231A", "#FFFFFF", "#8A0F0A"],                        # Ducati
    "#9B5DE5": ["#9B5DE5", "#111111", "#E2231A"],                        # Aprilia
    "#FF6600": ["#FF6600", "#111111", "#FFFFFF"],                        # KTM
    "#E8E8E8": ["#FFFFFF", "#CC0000", "#0033A0"],                        # Honda
    "#2F6BFF": ["#2F6BFF", "#0A1E5C", "#FFFFFF"],                        # Yamaha
    "#7FC8F8": ["#7FC8F8", "#1C69D4", "#E22718", "#FFFFFF"],             # BMW
    "#6CC24A": ["#6CC24A", "#111111", "#FFFFFF"],                        # Kawasaki
    "#F2B705": ["#F2B705", "#E2231A", "#111111"],                        # bimota
}


def mix(color, other, amount):
    # mix("#FF8000", "#FFFFFF", 0.4) -> 40% of the way from orange to white
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02X}" for x, y in zip(a, b))


def palette(color):
    color = (color or "#9A9AA8").upper()
    if color in TEAM_PALETTES:
        return TEAM_PALETTES[color]
    if len(color) != 7:
        return ["#F5C84C", "#FFFFFF"]
    return [color, mix(color, "#FFFFFF", 0.45), mix(color, "#000000", 0.4), "#FFFFFF"]


# ---------- Points still to be won ----------

def f1_points_left(season):
    # The standings say which round they include, so races that are run but not counted yet still count as open.
    url = f"{f1.BASE_URL}/{season}/driverStandings.json?limit=100"
    lists = get_cached(url, f1.max_age_for(season))["MRData"]["StandingsTable"]["StandingsLists"]
    counted = int(lists[0]["round"]) if lists else 0

    now = datetime.now(timezone.utc)
    left = {"drivers": 0, "teams": 0, "rounds_left": 0, "rounds": 0}
    for race in f1.get_races(season):
        left["rounds"] += 1
        number = int(race["round"])
        has_sprint = any(session["name"] == "Sprint" for session in race["sessions"])
        race_done = race["main"]["when"] + RESULTS_DELAY < now
        if not race_done:
            left["rounds_left"] += 1
        if number > counted:
            left["drivers"] += 25 + (8 if has_sprint else 0)
            left["teams"] += 43 + (15 if has_sprint else 0)
        elif number == counted and not race_done:
            # The sprint may already be in the standings, the race isn't.
            left["drivers"] += 25
            left["teams"] += 43
    return left


def moto_points_left(series, season):
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    long_ago = (now - timedelta(days=2)).date().isoformat()
    has_sprint = series.ID == "motogp" and season >= 2023
    race = {"drivers": 25, "manufacturers": 25, "teams": 45}
    sprint = {"drivers": 12, "manufacturers": 12, "teams": 21}

    left = {"drivers": 0, "manufacturers": 0, "teams": 0, "rounds_left": 0, "rounds": 0}
    for event in motogp.grand_prix_events(season):
        left["rounds"] += 1
        if event["date_end"] < long_ago:
            continue
        if event["date_start"] > today:
            open_races = ["Race", "Sprint"] if has_sprint else ["Race"]
        else:
            # This weekend: look at which races are already finished.
            open_races = []
            for session in series.event_sessions(season, event):
                label = motogp.session_label(session)
                if label in ("Race", "Sprint") and session.get("status") != "FINISHED":
                    open_races.append(label)
        if "Race" in open_races:
            left["rounds_left"] += 1
        for label in open_races:
            table = race if label == "Race" else sprint
            for key in table:
                left[key] += table[key]
    return left


def wsbk_points_left(season):
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    long_ago = (now - timedelta(days=2)).date().isoformat()
    points = {"RC1": 25, "SPRC": 12, "RC2": 25}

    left = {"drivers": 0, "manufacturers": 0, "rounds_left": 0, "rounds": 0}
    for item in wsbk.fetch_rounds(season):
        left["rounds"] += 1
        attrs = item.get("attributes") or {}
        end = (attrs.get("end_date") or "")[:10]
        start = (attrs.get("start_date") or "")[:10]
        if not start and end:
            start = (datetime.fromisoformat(end) - timedelta(days=2)).date().isoformat()
        if not end or end < long_ago:
            continue
        if start > today:
            open_races = list(points)
        else:
            open_races = []
            for session in wsbk.fetch_sessions(season, attrs.get("source_id")):
                sattrs = session["attributes"]
                if sattrs.get("short_name") in points and sattrs.get("status") != "FINISHED":
                    open_races.append(sattrs["short_name"])
        if open_races:
            left["rounds_left"] += 1
        for code in open_races:
            left["drivers"] += points[code]
            left["manufacturers"] += points[code]
    return left


def points_left(series, season):
    if series.ID == "f1":
        return f1_points_left(season)
    if series.ID == "wsbk":
        return wsbk_points_left(season)
    return moto_points_left(series, season)


# ---------- Who is champion ----------

def decided(rows, left):
    if not rows or float(rows[0]["points"]) <= 0:
        return None
    leader = float(rows[0]["points"])
    second = float(rows[1]["points"]) if len(rows) > 1 else 0
    # Strictly more than what's left: at a tie the tie-break (most wins) would decide.
    if left == 0 or leader - second > left:
        return rows[0]
    return None


def find(series, season, standings):
    # Marks champions with row["champion"] = True and returns who they are.
    result = {"drivers": None, "groups": {}, "rounds_left": 0}
    if season > datetime.now().year:
        return result
    left = points_left(series, season)
    # No calendar means we can't know what's left, so we don't crown anybody.
    if left["rounds"] == 0 or left["rounds_left"] == left["rounds"]:
        return result
    result["rounds_left"] = left["rounds_left"]

    champion = decided(standings["drivers"], left["drivers"])
    if champion:
        champion["champion"] = True
        result["drivers"] = champion
    for group in standings["groups"]:
        if group["title"] not in left:
            continue
        champion = decided(group["rows"], left[group["title"]])
        if champion:
            champion["champion"] = True
            result["groups"][group["title"]] = champion
    return result
