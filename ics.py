from datetime import datetime, timedelta, timezone

# Builds .ics calendar files (the format Apple, Google and Outlook calendars read).


def escape(text):
    text = str(text)
    for old, new in (("\\", "\\\\"), (";", "\\;"), (",", "\\,"), ("\n", "\\n")):
        text = text.replace(old, new)
    return text


def fold(line):
    # A line may be at most 75 bytes long; longer lines continue
    # on the next line, which starts with a space.
    parts = []
    current = ""
    for char in line:
        limit = 75 if not parts else 74
        if len((current + char).encode("utf-8")) > limit:
            parts.append(current)
            current = char
        else:
            current += char
    parts.append(current)
    return "\r\n ".join(parts)


def utc_stamp(when):
    return when.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def make_event(uid, summary, when, all_day, duration, location="", description=""):
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{utc_stamp(datetime.now(timezone.utc))}",
        f"SUMMARY:{escape(summary)}",
    ]
    if all_day:
        day = when.date()
        lines.append(f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}")
        lines.append(f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}")
        lines.append("TRANSP:TRANSPARENT")
    else:
        lines.append(f"DTSTART:{utc_stamp(when)}")
        lines.append(f"DTEND:{utc_stamp(when + duration)}")
    if location:
        lines.append(f"LOCATION:{escape(location)}")
    if description:
        lines.append(f"DESCRIPTION:{escape(description)}")
    lines.append("END:VEVENT")
    return lines


def race_events(series, season, race, sessions, t, link):
    uid = f"{series.ID}-{season}-r{race['round']}"
    location = race["country"]
    description = f"{t['round']} {race['round']} · {link}"

    timed = []
    for session in sessions:
        if not session["tbc"]:
            timed.append(session)

    # No session times yet: one all-day event on the race day.
    if not timed:
        main = race["main"]
        summary = f"{series.NAME} – {race['name']}"
        return [make_event(f"{uid}@kerbline", summary, main["when"], main["tbc"],
                           timedelta(hours=2), location, description)]

    events = []
    for session in timed:
        name = t.get(session["name"], session["name"])
        slug = session["name"].lower().replace(" ", "-")
        if series.ID == "f1" and session["name"] == "Race":
            duration = timedelta(hours=2)
        else:
            duration = timedelta(hours=1)
        summary = f"{series.NAME} · {name} – {race['name']}"
        events.append(make_event(f"{uid}-{slug}@kerbline", summary, session["when"], False,
                                 duration, location, description))
    return events


def make_calendar(name, events):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Kerbline//Motorsport Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape(name)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for event in events:
        lines.extend(event)
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"
