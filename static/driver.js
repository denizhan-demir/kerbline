// The driver page: season numbers, points per round, the race-by-race table and the Wikipedia bio.
// Uses loadJSON and drawBars from charts.js, and fetchDriver, showDriverInfo and countUp from site.js.

const driverPage = document.querySelector(".driver-page");

function positionChip(position) {
    const chip = document.createElement("span");
    chip.className = "pos-chip";
    if (typeof position === "number") {
        chip.textContent = "P" + position;
        if (position <= 3) {
            chip.classList.add("p" + position);
        }
    } else {
        // DNF, DSQ, DNS...
        chip.textContent = position;
        chip.classList.add("out");
    }
    return chip;
}

function setTile(tile, text, delay) {
    const number = tile.querySelector("b");
    number.classList.remove("wait");
    number.textContent = text;
    if (!motionOff && /^\d+$/.test(text)) {
        countUp(number, delay);
    }
}

function fillStats(stats) {
    const values = {
        wins: String(stats.wins),
        podiums: String(stats.podiums),
        best: stats.best ? "P" + stats.best : "—",
    };
    for (const tile of document.querySelectorAll(".driver-hero [data-stat]")) {
        setTile(tile, values[tile.dataset.stat], 100);
    }
}

function fillCareer(career) {
    const section = document.getElementById("driver-career");
    if (!section || !career) {
        return;
    }
    section.hidden = false;
    for (const tile of section.querySelectorAll("[data-career]")) {
        setTile(tile, String(career[tile.dataset.career]), 150 + Number(tile.style.getPropertyValue("--n")) * 80);
    }
}

function fillTable(box, results, labels) {
    const table = document.createElement("table");
    table.className = "result-table driver-table";

    const head = table.createTHead().insertRow();
    for (const text of [driverPage.dataset.round, ""]) {
        const cell = document.createElement("th");
        cell.textContent = text;
        head.appendChild(cell);
    }
    for (const label of labels) {
        const cell = document.createElement("th");
        cell.className = "race-cell";
        cell.textContent = label.text;
        head.appendChild(cell);
    }
    const pointsHead = document.createElement("th");
    pointsHead.className = "pts";
    pointsHead.textContent = driverPage.dataset.points;
    head.appendChild(pointsHead);

    const body = table.createTBody();
    // Newest round at the top.
    results.slice().reverse().forEach(function (result, index) {
        const row = body.insertRow();
        row.style.setProperty("--k", index);
        row.style.setProperty("--team", driverPage.dataset.color);

        const round = row.insertCell();
        round.className = "pos";
        round.textContent = result.round;

        const name = row.insertCell();
        name.className = "race-name";
        name.textContent = `${result.flag} ${result.name}`;

        for (const label of labels) {
            const cell = row.insertCell();
            cell.className = "race-cell";
            const race = result.races.find(function (item) {
                return item.label === label.key;
            });
            if (race) {
                cell.appendChild(positionChip(race.position));
            } else {
                cell.textContent = "–";
            }
        }

        const points = row.insertCell();
        points.className = "pts strong";
        points.textContent = formatPoints(result.points);
    });

    box.textContent = "";
    box.appendChild(table);
}

async function loadSeason() {
    const bars = document.getElementById("driver-bars");
    const tableBox = document.getElementById("driver-results");
    const data = await loadJSON(driverPage.dataset.url);

    if (!data) {
        chartMessage(bars, driverPage.dataset.error);
        chartMessage(tableBox, driverPage.dataset.error);
        return;
    }
    if (data.stats) {
        fillStats(data.stats);
    }
    fillCareer(data.career);
    if (!data.results.length) {
        chartMessage(bars, driverPage.dataset.empty);
        chartMessage(tableBox, driverPage.dataset.empty);
        for (const tile of document.querySelectorAll(".driver-hero [data-stat]")) {
            setTile(tile, "—", 0);
        }
        return;
    }
    drawBars(bars, data.results, driverPage.dataset.color, {
        round: driverPage.dataset.round,
        points: driverPage.dataset.points,
    });
    fillTable(tableBox, data.results, data.labels);
}

async function loadBio() {
    const info = await fetchDriver(document.body.dataset.series, driverPage.dataset.name);
    showDriverInfo(info, document.querySelector("main.page"));
}

if (driverPage) {
    loadSeason();
    loadBio();
}
