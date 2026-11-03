# The intro tour for first-time visitors (shown by static/tour.js).
# Every step points at one part of the page with a CSS selector. Steps whose part isn't on the
# screen are skipped by tour.js, e.g. the bottom menu only exists on phones.

STEPS = {
    "home": [
        ("series", ".series-nav"),
        ("home_next", ".hero"),
        ("home_cards", ".card-grid .next-card"),
        ("time", ".toggle"),
        ("bottom", ".bottom-nav"),
    ],
    "calendar": [
        ("series", ".series-nav"),
        ("seasons", ".season-picker"),
        ("time", ".toggle"),
        ("subscribe", ".subscribe"),
        ("races", ".hero, .race-grid .race-card"),
        ("bottom", ".bottom-nav"),
    ],
    "standings": [
        ("series", ".series-nav"),
        ("seasons", ".season-picker"),
        ("drivers", ".leaders"),
        ("chart", "#title-fight"),
        ("bottom", ".bottom-nav"),
    ],
    "driver": [
        ("series", ".series-nav"),
        ("driver_tiles", ".driver-hero .driver-tiles"),
        ("driver_bars", "#driver-bars"),
    ],
}

TEXT = {
    "en": {
        "welcome": ("Welcome to Kerbline",
                    "F1, MotoGP, Moto2, Moto3 and WorldSBK: calendars, results and standings in one place. "
                    "Let us show you around, it takes a minute."),
        "series": ("Series", "Switch between the series here. Each one has its own calendar, results and standings."),
        "time": ("Your time or track time",
                 "Show session times in your own time zone, or in the local time of the circuit."),
        "home_next": ("Up next", "The next race and its countdown. Tap it to see the whole weekend's schedule."),
        "home_cards": ("The other series",
                       "The next race of every series. Once you pick a favourite driver, their position shows up here too."),
        "bottom": ("Quick menu", "Jump between home, the calendar and the standings from here."),
        "seasons": ("Seasons", "Tap the year to look at any season since 2020."),
        "subscribe": ("Add to your calendar",
                      "Puts every session in your phone's or computer's calendar. When times change, it updates by itself."),
        "races": ("Races", "Tap a race for its schedule. Once it's over you get the podium and the full results too."),
        "drivers": ("Drivers",
                    "Tap a driver for their photo, a short bio and their season. From there you can make them "
                    "your favourite or open their own page."),
        "chart": ("Title fight", "How the points changed after every round. Hover over it, or slide a finger across."),
        "driver_tiles": ("Season at a glance", "Position, points, gap to the leader, wins and podiums."),
        "driver_bars": ("Points per round", "What they scored every race weekend. The race-by-race results are below."),
        "help": ("The tour is always here", "Want to see this again? Press the question mark."),
        "install": ("Use it like an app",
                    "On your phone, choose \"Add to Home Screen\" in the browser menu and Kerbline opens like an app."),
    },
    "tr": {
        "welcome": ("Kerbline'a hoş geldin",
                    "F1, MotoGP, Moto2, Moto3 ve WorldSBK: takvimler, sonuçlar ve puan durumu tek yerde. "
                    "Bir dakikada neyin nerede olduğunu gösterelim."),
        "series": ("Seriler", "Buradan seriler arasında geçersin. Her serinin kendi takvimi, sonuçları ve puan durumu var."),
        "time": ("Senin saatin, pist saati",
                 "Seans saatlerini bulunduğun yerin saatine ya da yarışın yapıldığı pistin yerel saatine göre gösterir."),
        "home_next": ("Sıradaki yarış", "En yakın yarış ve geri sayımı. Dokununca o hafta sonunun programı açılır."),
        "home_cards": ("Diğer seriler",
                       "Her serinin sıradaki yarışı. Favori pilot seçtiğinde onun sırası ve puanı da burada görünür."),
        "bottom": ("Hızlı menü", "Ana sayfa, takvim ve puan durumu arasında buradan geçersin."),
        "seasons": ("Sezonlar", "Yıla dokunup 2020'den bu yana istediğin sezona bakabilirsin."),
        "subscribe": ("Takvimine ekle",
                      "Bütün seansları telefonunun ya da bilgisayarının takvimine ekler. Saatler değişirse takvimin "
                      "kendiliğinden güncellenir."),
        "races": ("Yarışlar", "Bir yarışa dokun, seans programı açılır. Yarış bittiyse podyum ve tüm sonuçlar da gelir."),
        "drivers": ("Pilotlar",
                    "Bir pilota dokun: fotoğrafı, kısa biyografisi ve sezonu açılır. Oradan favorine ekleyebilir "
                    "ya da pilot sayfasına geçebilirsin."),
        "chart": ("Şampiyonluk yarışı",
                  "Her turdan sonra puanların nasıl değiştiğini gösterir. Üstüne gel ya da parmağını grafikte kaydır."),
        "driver_tiles": ("Sezon özeti", "Sırası, puanı, lidere farkı, galibiyetleri ve podyumları bir bakışta."),
        "driver_bars": ("Tur tur puanlar", "Her yarış hafta sonunda kaç puan aldığını gösterir. Altında yarış yarış sonuçlar var."),
        "help": ("Tur hep burada", "Bu turu tekrar görmek istersen soru işaretine bas."),
        "install": ("Uygulama gibi kullan",
                    "Telefonunda tarayıcının menüsünden \"Ana ekrana ekle\"yi seçersen Kerbline uygulama gibi açılır."),
    },
}

# The language choice on the welcome card. Each name is written in its own language,
# so someone who doesn't read the current one still finds theirs.
LANGUAGES = [("tr", "Türkçe"), ("en", "English")]
LANGUAGE_LABEL = "Dil · Language"

LABELS = {
    "en": {"start": "Start the tour", "later": "Not now", "next": "Next", "back": "Back", "done": "Done",
           "skip": "Skip", "help": "Show me around"},
    "tr": {"start": "Turu başlat", "later": "Şimdilik geç", "next": "İleri", "back": "Geri", "done": "Bitir",
           "skip": "Geç", "help": "Siteyi tanı"},
}


def step(step_id, target, lang):
    title, text = TEXT[lang][step_id]
    return {"id": step_id, "target": target, "title": title, "text": text}


def tour_for(page, lang):
    # Everything tour.js needs for this page, in the page's language.
    return {
        "steps": [step(step_id, target, lang) for step_id, target in STEPS.get(page, [])],
        "welcome": step("welcome", None, lang),
        "help": step("help", ".tour-help", lang),
        "install": step("install", None, lang),
        "labels": LABELS[lang],
        "languages": [{"code": code, "name": name} for code, name in LANGUAGES],
        "language_label": LANGUAGE_LABEL,
    }
