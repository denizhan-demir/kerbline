import unicodedata

import wsbk

# What we know about the circuits, for the prediction (predict.py).

# ---------- F1: what kind of track it is ----------
# A car that's quick at Monza is usually quick at Spa too, so we compare tracks of the same kind.
#   street     walls close by, slow corners, often bumpy
#   fast       long straights and fast corners: engine power and low drag matter
#   technical  lots of slow and medium corners: downforce matters
#   balanced   a bit of everything
F1_TRACK_TYPES = {
    "monaco": "street", "marina_bay": "street", "baku": "street", "jeddah": "street",
    "vegas": "street", "miami": "street", "madring": "street",
    "monza": "fast", "spa": "fast", "silverstone": "fast", "red_bull_ring": "fast",
    "suzuka": "fast", "losail": "fast", "interlagos": "fast", "mugello": "fast",
    "hungaroring": "technical", "zandvoort": "technical", "catalunya": "technical",
    "imola": "technical", "rodriguez": "technical",
    "albert_park": "balanced", "shanghai": "balanced", "bahrain": "balanced", "americas": "balanced",
    "villeneuve": "balanced", "yas_marina": "balanced", "ricard": "balanced", "portimao": "balanced",
    "istanbul": "balanced", "nurburgring": "balanced", "sochi": "balanced",
}

# ---------- Motorcycles: which circuit a round is at ----------
# The APIs only give a country and a name, and some countries have several tracks
# (Spain has four), so words in the name decide. Each entry:
#   key, country (2 letters), words to look for, latitude, longitude, series that race there
MOTO_CIRCUITS = [
    ("lusail", "QA", [], 25.49, 51.45, "all"),
    ("portimao", "PT", ["portimao", "algarve", "portug"], 37.23, -8.63, "all"),
    ("estoril", "PT", ["estoril"], 38.75, -9.39, "all"),
    ("americas", "US", [], 30.13, -97.64, "all"),
    ("termas", "AR", ["termas", "republica argentina", "argentina"], -27.51, -64.91, "gp"),
    ("san_juan", "AR", ["san juan", "villicum", "argentinian"], -31.62, -68.56, "wsbk"),
    ("jerez", "ES", ["jerez", "espana", "spain", "spanish", "andalucia"], 36.71, -6.03, "all"),
    ("aragon", "ES", ["aragon", "alcaniz", "motorland"], 41.08, -0.20, "all"),
    ("catalunya", "ES", ["catalunya", "catalan", "barcelona"], 41.57, 2.26, "all"),
    ("valencia", "ES", ["valencia", "valenciana", "ricardo tormo"], 39.49, -0.63, "all"),
    ("le_mans", "FR", ["le mans", "france", "french"], 47.95, 0.21, "gp"),
    ("magny_cours", "FR", ["magny", "nevers", "french", "france"], 46.86, 3.16, "wsbk"),
    ("silverstone", "GB", [], 52.07, -1.02, "gp"),
    ("donington", "GB", [], 52.83, -1.38, "wsbk"),
    ("assen", "NL", [], 52.96, 6.52, "all"),
    ("mugello", "IT", ["mugello", "italia", "italy", "italian"], 43.997, 11.37, "gp"),
    ("misano", "SM", [], 43.96, 12.68, "all"),
    ("misano", "IT", ["misano", "emilia", "romagna", "rimini", "san marino"], 43.96, 12.68, "all"),
    ("cremona", "IT", ["cremona"], 45.10, 10.08, "wsbk"),
    ("imola", "IT", ["imola"], 44.34, 11.71, "wsbk"),
    ("sachsenring", "DE", [], 50.79, 12.69, "gp"),
    ("brno", "CZ", [], 49.20, 16.44, "gp"),
    ("most", "CZ", [], 50.52, 13.61, "wsbk"),
    ("red_bull_ring", "AT", [], 47.22, 14.76, "gp"),
    ("balaton", "HU", [], 46.88, 17.60, "all"),
    ("motegi", "JP", [], 36.53, 140.23, "gp"),
    ("mandalika", "ID", [], -8.89, 116.30, "all"),
    ("phillip_island", "AU", [], -38.50, 145.23, "all"),
    ("buriram", "TH", [], 14.96, 103.08, "gp"),
    ("sepang", "MY", [], 2.76, 101.74, "gp"),
    ("buddh", "IN", [], 28.35, 77.53, "gp"),
    ("sokol", "KZ", [], 43.60, 76.70, "gp"),
]


def plain(text):
    text = unicodedata.normalize("NFKD", (text or "").replace("ı", "i"))
    return text.encode("ascii", "ignore").decode().lower()


def moto_circuit(series_id, country, name):
    # country: 2 letters (MotoGP) or 3 letters (WorldSBK). Returns (key, latitude, longitude) or None.
    if len(country or "") == 3:
        country = wsbk.COUNTRY_CODES.get(country, "")
    scope = "wsbk" if series_id == "wsbk" else "gp"
    candidates = [c for c in MOTO_CIRCUITS if c[1] == country and c[5] in ("all", scope)]
    if not candidates:
        return None
    words = plain(name)
    for key, _, keywords, lat, lon, _ in candidates:
        if any(word in words for word in keywords):
            return key, lat, lon
    # No word matched: the country's first track (for most countries there's only one).
    key, _, _, lat, lon, _ = candidates[0]
    return key, lat, lon
