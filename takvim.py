import requests

url = "https://api.jolpi.ca/ergast/f1/current.json"
response = requests.get(url)
data = response.json()

races = data["MRData"]["RaceTable"]["Races"]

for race in races:
    print(race["round"], race["raceName"], race["date"])