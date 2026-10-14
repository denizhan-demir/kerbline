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

cache = {}
cache_lock = threading.Lock()


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
        "prop": "extracts|pageimages|description|info|langlinks",
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
    key = (plain(name), series_id, lang)
    with cache_lock:
        cached = cache.get(key)
    if cached and datetime.now() < cached["until"]:
        return cached["info"]

    info = {"found": False, "description": "", "extract": "", "url": "", "photo": "", "credit": None}
    good_for = GOOD_FOR
    try:
        page = find_page(name, series_id)
        if page:
            info["found"] = True
            info["description"] = page.get("description", "")
            info["extract"] = page.get("extract", "")
            info["url"] = page.get("fullurl", "")

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
                    info["description"] = turkish.get("description") or info["description"]
                    info["url"] = turkish.get("fullurl") or info["url"]
    except (requests.RequestException, ValueError):
        # Wikipedia did not answer: show what we have and try again a bit later.
        good_for = RETRY_AFTER

    with cache_lock:
        cache[key] = {"info": info, "until": datetime.now() + good_for}
    return info
