// Kerbline's prediction (worked out in predict.py):
// - the card on the calendar page: who wins the next race, with chances and reasons
// - a short line on the home page cards
// - "Kerbline's pick: Norris · Called it" in the race panel of races that are over

const predictionCache = {};
const pendingWatchers = {};

function wait(ms) {
    return new Promise(function (resolve) {
        setTimeout(resolve, ms);
    });
}

// The server works the prediction out in the background. Until it's ready it answers 202
// ("not ready yet"), so we ask again every 3 seconds, for up to 3 minutes.
async function askUntilReady(url) {
    for (let attempt = 0; attempt < 60; attempt++) {
        try {
            const response = await fetch(url);
            if (response.status === 202) {
                for (const watcher of pendingWatchers[url] || []) {
                    watcher();
                }
                await wait(3000);
                continue;
            }
            return response.ok ? await response.json() : null;
        } catch (error) {
            await wait(3000);
        }
    }
    return null;
}

function fetchPrediction(url, onPending) {
    // Every part of the page asks for the same data, so it's only loaded once.
    if (onPending) {
        (pendingWatchers[url] = pendingWatchers[url] || []).push(onPending);
    }
    if (!predictionCache[url]) {
        predictionCache[url] = askUntilReady(url);
    }
    return predictionCache[url];
}

function percent(value) {
    return Math.round(value) + "%";
}

function recordText(card, record) {
    if (!record || !record.races) {
        return "";
    }
    const template = card.dataset.current ? card.dataset.record : card.dataset.recordPast;
    return template.replace("{hits}", record.hits).replace("{races}", record.races).replace("{season}", card.dataset.season);
}

// ---------- The card on the calendar page ----------

// Little chips under the title: the weather and (F1) the kind of track.
function showChips(card, data) {
    const chips = card.querySelector(".predict-chips");
    chips.textContent = "";
    const texts = [];
    if (data.weather) {
        const rain = Math.round(data.weather.rain * 100);
        let text = rain >= 30 ? card.dataset.rain.replace("{n}", rain) : card.dataset.dry;
        if (data.weather.temp !== null && data.weather.temp !== undefined) {
            text += " · " + data.weather.temp + "°C";
        }
        texts.push([text, rain >= 30 ? "rain" : "dry"]);
    }
    if (data.track_type) {
        const key = "track" + data.track_type.charAt(0).toUpperCase() + data.track_type.slice(1);
        if (card.dataset[key]) {
            texts.push([card.dataset[key], "track"]);
        }
    }
    for (const [text, kind] of texts) {
        const chip = document.createElement("span");
        chip.className = "predict-chip " + kind;
        chip.textContent = text;
        chips.appendChild(chip);
    }
}

function showPredictionCard(card, data) {
    card.querySelector(".predict-wait").hidden = true;
    const list = card.querySelector(".predict-list");
    const sub = card.querySelector(".predict-sub");
    const record = recordText(card, data.record);
    card.querySelector(".predict-record").textContent = record;
    list.textContent = "";

    if (!data.race || !data.drivers.length) {
        // A season that's over: only how often the favourite won.
        if (!record) {
            return;
        }
        sub.textContent = "";
        card.classList.add("only-record");
        card.hidden = false;
        return;
    }

    sub.textContent = `${data.race.flag} ${data.race.name} · `
        + (data.basis === "grid" ? card.dataset.basisGrid : card.dataset.basisForm);
    showChips(card, data);

    const top = data.drivers[0].chance || 1;
    data.drivers.forEach(function (driver, index) {
        const item = document.createElement("li");
        item.className = "predict-row";
        item.style.setProperty("--team", driver.color);
        item.style.setProperty("--i", index);
        // Bars are measured against the favourite, so the first one is full.
        item.style.setProperty("--w", (driver.chance / top * 100) + "%");

        const rank = document.createElement("span");
        rank.className = "predict-rank";
        rank.textContent = index + 1;

        const body = document.createElement("div");
        body.className = "predict-body";
        const name = document.createElement("button");
        name.type = "button";
        name.className = "driver-link name-link predict-name";
        name.dataset.name = driver.name;
        name.dataset.slug = driver.slug;
        name.dataset.team = driver.team;
        name.dataset.color = driver.color;
        name.dataset.flag = driver.flag || "";
        name.textContent = `${driver.flag || ""} ${driver.name}`.trim();
        const bar = document.createElement("span");
        bar.className = "predict-bar";
        const reasons = document.createElement("span");
        reasons.className = "predict-reasons";
        reasons.textContent = driver.reasons.join(" · ");
        body.append(name, bar, reasons);

        const chance = document.createElement("b");
        chance.className = "predict-chance";
        chance.textContent = percent(driver.chance);

        item.append(rank, body, chance);
        list.appendChild(item);
    });
    card.hidden = false;
    if (typeof markFavourites === "function") {
        markFavourites();
    }
}

const predictionCard = document.getElementById("prediction");
if (predictionCard) {
    // While the server is still working, the card shows a "working on it" note.
    fetchPrediction(predictionCard.dataset.url, function () {
        if (predictionCard.hidden) {
            predictionCard.querySelector(".predict-wait").hidden = false;
            predictionCard.hidden = false;
        }
    }).then(function (data) {
        if (data) {
            showPredictionCard(predictionCard, data);
        } else {
            predictionCard.hidden = true;
        }
    });
}

// ---------- In the race panel: did we call it? ----------

async function addPredictionNote(results, round) {
    if (!predictionCard) {
        return;
    }
    const data = await fetchPrediction(predictionCard.dataset.url);
    const past = data && data.past ? data.past[round] : null;
    if (!past || results.querySelector(".predict-note")) {
        return;
    }
    const note = document.createElement("p");
    note.className = "predict-note " + (past.hit ? "hit" : "miss");
    const pick = document.createElement("span");
    pick.textContent = `🔮 ${predictionCard.dataset.pick}: ${past.favourite} (${past.chance}%)`;
    const verdict = document.createElement("b");
    verdict.textContent = past.hit
        ? "✓ " + predictionCard.dataset.called
        : "✗ " + predictionCard.dataset.winner.replace("{name}", past.winner);
    note.append(pick, verdict);
    results.prepend(note);
}

// ---------- Home page: one line per series ----------

for (const line of document.querySelectorAll(".predict-line")) {
    fetchPrediction(line.dataset.url).then(function (data) {
        if (!data || !data.race || !data.drivers.length || String(data.race.round) !== line.dataset.round) {
            return;
        }
        const favourite = data.drivers[0];
        line.textContent = "";
        const label = document.createElement("span");
        label.className = "predict-label";
        label.textContent = "🔮 " + line.dataset.label;
        const name = document.createElement("span");
        name.className = "fav-name";
        name.textContent = favourite.name;
        const chance = document.createElement("span");
        chance.className = "fav-stat";
        chance.textContent = percent(favourite.chance);
        line.append(label, name, chance);
        line.hidden = false;
    });
}
