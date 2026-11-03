// Kerbline's prediction (worked out in predict.py):
// - the card on the calendar page: who wins the next race, with chances and reasons
// - a short line on the home page cards
// - "Kerbline's pick: Norris · Called it" in the race panel of races that are over

const predictionCache = {};

function fetchPrediction(url) {
    // Every part of the page asks for the same data, so it's only loaded once.
    if (!predictionCache[url]) {
        const controller = new AbortController();
        const timer = setTimeout(function () {
            controller.abort();
        }, 60000);
        predictionCache[url] = fetch(url, { signal: controller.signal })
            .then(function (response) {
                return response.ok ? response.json() : null;
            })
            .catch(function () {
                return null;
            })
            .finally(function () {
                clearTimeout(timer);
            });
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

function showPredictionCard(card, data) {
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
    fetchPrediction(predictionCard.dataset.url).then(function (data) {
        if (data) {
            showPredictionCard(predictionCard, data);
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
