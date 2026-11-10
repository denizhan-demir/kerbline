# Kerbline: checks the MotoGP times of the Qatar GP (6–8 November 2026).
# Run it in the project folder, with the .venv on:   python3 check_qatar.py
# It changes nothing; it only prints what the MotoGP API says and what Kerbline makes of it.

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import motogp

SEASON = 2026

# The official schedule in UTC (GMT), from crash.net.
OFFICIAL_UTC = {
    "Free Practice 1": "06.11 11:45",
    "Practice": "06.11 16:00",
    "Free Practice 2": "07.11 11:00",
    "Qualifying 1": "07.11 11:40",
    "Qualifying 2": "07.11 12:05",
    "Sprint": "07.11 16:00",
    "Warm Up": "08.11 11:40",
    "Race": "08.11 16:00",
}

budapest = ZoneInfo("Europe/Budapest")
found = False
for number, event in enumerate(motogp.grand_prix_events(SEASON), start=1):
    if event["country"]["iso"] != "QA":
        continue
    found = True
    print(f"Round {number}: {event['name']}  ({event['date_start']} – {event['date_end']})")
    print()
    race_session = None
    for series in (motogp.MOTOGP, motogp.MOTO2, motogp.MOTO3):
        print(f"--- {series.NAME} ---")
        for session in series.event_sessions(SEASON, event):
            label = motogp.session_label(session)
            raw = session.get("date")
            if not raw:
                print(f"  {label:16} no time in the API")
                continue
            # Exactly what core.make_session does:
            parsed = datetime.fromisoformat(raw[:10] + "T" + raw[11:])
            if parsed.tzinfo is None:
                print(f"  {label:16} API: {raw:30}  -> NO TIME ZONE in this time!")
                continue
            utc = parsed.astimezone(timezone.utc)
            line = f"  {label:16} API: {raw:30}  -> UTC {utc:%d.%m %H:%M}  Budapest {utc.astimezone(budapest):%H:%M}"
            if series is motogp.MOTOGP and label in OFFICIAL_UTC:
                line += f"   official UTC {OFFICIAL_UTC[label]}"
            print(line)
            if series is motogp.MOTOGP and label == "Race":
                race_session = session
        print()
    if race_session:
        print("Everything the API says about the MotoGP race session:")
        print(json.dumps(race_session, indent=2, ensure_ascii=False)[:3000])

if not found:
    print("No Qatar round in the 2026 MotoGP calendar from the API.")

# Every round of the season: the MotoGP race time as the API sends it. A wrong time zone
# shows up as an odd "+hh:mm" or a strange UTC hour (races usually start between 11:00 and 19:00 UTC).
# Portugal and Valencia were moved too, so they matter most.
print()
print("=== MotoGP race of every 2026 round ===")
for number, event in enumerate(motogp.grand_prix_events(SEASON), start=1):
    raw = None
    try:
        for session in motogp.MOTOGP.event_sessions(SEASON, event):
            if session.get("type") == "RAC" and session.get("date"):
                raw = session["date"]
    except Exception as error:
        raw = f"error: {error}"
    utc = ""
    if raw and not raw.startswith("error"):
        parsed = datetime.fromisoformat(raw[:10] + "T" + raw[11:])
        utc = f"UTC {parsed.astimezone(timezone.utc):%d.%m %H:%M}" if parsed.tzinfo else "NO TIME ZONE"
    print(f"  {number:2}. {event['country']['iso']}  {event['date_end']}  {str(raw):30}  {utc}  {event['name']}")
