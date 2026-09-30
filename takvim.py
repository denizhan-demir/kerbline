import requests
from datetime import datetime
from zoneinfo import ZoneInfo

url = "https://api.jolpi.ca/ergast/f1/current.json"
response = requests.get(url)
data = response.json()

races = data["MRData"]["RaceTable"]["Races"]
budapest = ZoneInfo("Europe/Budapest")
now = datetime.now(budapest)
next_found = False

for race in races:
    utc_time = datetime.fromisoformat(race["date"] + "T" + race["time"])
    local_time = utc_time.astimezone(budapest)

    quali_utc = datetime.fromisoformat(race["Qualifying"]["date"] + "T" + race["Qualifying"]["time"])
    quali_local = quali_utc.astimezone(budapest)

    country = race["Circuit"]["Location"]["country"]
    if local_time < now:
        status = "✓"
    elif not next_found:
        status = "→"
        next_found = True
    else:
        status = " "
    print(status, race["round"], race["raceName"], country,
          "| Quali:", quali_local.strftime("%d.%m %H:%M"),
          "| Race:", local_time.strftime("%d.%m.%Y %H:%M"))