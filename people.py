import re
import threading
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import quote

import requests

# Driver and rider info (short bio + free-licensed photo) from Wikipedia.
# Official team photos are copyrighted, Wikimedia Commons photos are free to use with credit.

# Wikimedia asks every app to say who it is. Change the link to your own site if you like.
HEADERS = {"User-Agent": "Kerbline/1.0 (unofficial motorsport calendar; https://github.com/denizhan-demir)"}

SEARCH_WORDS = {"f1": "Formula One racing driver", "motogp": "motorcycle racer", "wsbk": "motorcycle racer"}
GOOD_FOR = timedelta(days=7)
RETRY_AFTER = timedelta(minutes=10)

# Anyone can call /driver-info with any name, so we set limits:
# at most this many names are kept in memory...
MAX_CACHE = 1000
# ...and at most this many Wikipedia lookups run at the same time.
# The site has 4 threads; the other ones stay free for the normal pages.
lookup_slots = threading.BoundedSemaphore(2)

cache = {}
cache_lock = threading.Lock()


def valid_name(name):
    # Real names only: letters, spaces, dots, hyphens and apostrophes
    # ("Pato O'Ward", "Jean-Éric Vergne", "Toprak Razgatlıoğlu").
    if not any(c.isalpha() for c in name):
        return False
    return all(c.isalpha() or c.isspace() or c in ".'-’" for c in name)


def remember(key, info, good_for):
    with cache_lock:
        cache.pop(key, None)
        if len(cache) >= MAX_CACHE:
            # Full: forget the oldest name to make room.
            cache.pop(next(iter(cache)))
        cache[key] = {"info": info, "until": datetime.now() + good_for}


def plain(text):
    # "Nicolò" -> "nicolo", so names match with or without accents.
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def wiki_query(lang, params):
    params = {**params, "action": "query", "format": "json", "formatversion": "2"}
    response = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params=params, headers=HEADERS, timeout=8)
    response.raise_for_status()
    return response.json().get("query", {})


def find_page(name, series_id):
    query = wiki_query("en", {
        "generator": "search",
        "gsrsearch": f"{name} {SEARCH_WORDS.get(series_id, '')}",
        "gsrlimit": 3,
        "prop": "extracts|pageimages|description|info|langlinks|pageprops",
        "ppprop": "wikibase_item",
        "exintro": 1,
        "explaintext": 1,
        "exsentences": 3,
        "piprop": "thumbnail|name",
        "pithumbsize": 500,
        "inprop": "url",
        "lllang": "tr",
        "redirects": 1,
    })
    pages = sorted(query.get("pages", []), key=lambda page: page.get("index", 99))
    surname = plain(name.split()[-1])
    for page in pages:
        # Only accept a page whose title contains the surname, so we never show the wrong person.
        if surname and surname in plain(page.get("title")):
            return page
    return None


def turkish_page(title):
    query = wiki_query("tr", {
        "titles": title,
        "prop": "extracts|description|info",
        "exintro": 1,
        "explaintext": 1,
        "exsentences": 3,
        "inprop": "url",
        "redirects": 1,
    })
    pages = query.get("pages", [])
    if pages and not pages[0].get("missing"):
        return pages[0]
    return None


def wikidata(params):
    params = {**params, "format": "json"}
    response = requests.get("https://www.wikidata.org/w/api.php", params=params, headers=HEADERS, timeout=8)
    response.raise_for_status()
    return response.json().get("entities", {})


def claim_value(claims, prop):
    for claim in claims.get(prop, []):
        snak = claim.get("mainsnak", {})
        if snak.get("snaktype") == "value":
            return snak.get("datavalue", {}).get("value")
    return None


def wikidata_facts(item_id, lang):
    # Wikidata holds facts in every language: a short description, birth date and birthplace.
    facts = {"description": "", "born": "", "birthplace": ""}
    entity = wikidata({"action": "wbgetentities", "ids": item_id, "props": "descriptions|claims",
                       "languages": lang}).get(item_id, {})
    description = entity.get("descriptions", {}).get(lang)
    if description:
        facts["description"] = description.get("value", "")

    claims = entity.get("claims", {})
    birth = claim_value(claims, "P569")  # P569 = date of birth
    if birth and birth.get("precision", 0) >= 11:
        facts["born"] = birth.get("time", "").lstrip("+")[:10]

    place = claim_value(claims, "P19")  # P19 = place of birth
    if place and place.get("id"):
        labels = wikidata({"action": "wbgetentities", "ids": place["id"], "props": "labels",
                           "languages": lang + "|en"}).get(place["id"], {}).get("labels", {})
        label = labels.get(lang) or labels.get("en")
        if label:
            facts["birthplace"] = label.get("value", "")
    return facts


def photo_credit(file_name):
    response = requests.get("https://commons.wikimedia.org/w/api.php", params={
        "action": "query",
        "titles": "File:" + file_name,
        "prop": "imageinfo",
        "iiprop": "extmetadata",
        "format": "json",
        "formatversion": "2",
    }, headers=HEADERS, timeout=8)
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        # The file is not on Commons, so it may not be free to use: skip it.
        return None
    meta = (pages[0].get("imageinfo") or [{}])[0].get("extmetadata", {})
    license_name = strip_html(meta.get("LicenseShortName", {}).get("value", ""))
    if not license_name or "fair use" in license_name.lower():
        return None
    return {
        "artist": strip_html(meta.get("Artist", {}).get("value", ""))[:80],
        "license": license_name,
        "url": "https://commons.wikimedia.org/wiki/File:" + quote(file_name.replace(" ", "_")),
    }


def driver_info(name, series_id, lang):
    # Returns None when too many lookups are running; the page then simply shows "no info".
    key = (plain(name), series_id, lang)
    with cache_lock:
        cached = cache.get(key)
    if cached and datetime.now() < cached["until"]:
        return cached["info"]

    if not lookup_slots.acquire(blocking=False):
        return None
    try:
        return look_up(name, series_id, lang, key)
    finally:
        lookup_slots.release()


def look_up(name, series_id, lang, key):
    info = {"found": False, "description": "", "extract": "", "extract_lang": "", "url": "",
            "photo": "", "credit": None, "born": "", "birthplace": ""}
    good_for = GOOD_FOR
    try:
        page = find_page(name, series_id)
        if page:
            info["found"] = True
            info["url"] = page.get("fullurl", "")
            # The English text is only used when the site is in English.
            if lang == "en":
                info["description"] = page.get("description", "")
                info["extract"] = page.get("extract", "")
                info["extract_lang"] = "en"

            item_id = page.get("pageprops", {}).get("wikibase_item")
            if item_id:
                try:
                    facts = wikidata_facts(item_id, lang)
                    info["born"] = facts["born"]
                    info["birthplace"] = facts["birthplace"]
                    if lang != "en" and facts["description"]:
                        info["description"] = facts["description"]
                except (requests.RequestException, ValueError):
                    pass

            thumbnail = page.get("thumbnail", {}).get("source")
            if thumbnail and page.get("pageimage"):
                credit = photo_credit(page["pageimage"])
                if credit:
                    info["photo"] = thumbnail
                    info["credit"] = credit

            links = page.get("langlinks") or []
            if lang == "tr" and links:
                turkish = turkish_page(links[0].get("title", ""))
                if turkish and turkish.get("extract"):
                    info["extract"] = turkish["extract"]
                    info["extract_lang"] = "tr"
                    info["description"] = turkish.get("description") or info["description"]
                    info["url"] = turkish.get("fullurl") or info["url"]
    except (requests.RequestException, ValueError):
        # Wikipedia did not answer: show what we have and try again a bit later.
        good_for = RETRY_AFTER

    remember(key, info, good_for)
    return info
