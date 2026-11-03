const MODE_KEY = "kerbline-time-mode";
const LIGHTS_KEY = "kerbline-lights-shown";

function loadMode() {
    try {
        return localStorage.getItem(MODE_KEY) === "track" ? "track" : "yours";
    } catch (error) {
        return "yours";
    }
}

function saveMode(value) {
    try {
        localStorage.setItem(MODE_KEY, value);
    } catch (error) {
        // Private browsing can block storage; the choice then lasts until the page closes.
    }
}

let mode = loadMode();
const locale = document.body.dataset.locale;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const EASE_OUT = "cubic-bezier(0.22, 1, 0.36, 1)";
const EASE_IN_OUT = "cubic-bezier(0.4, 0, 0.2, 1)";

const DAY_FORMAT = { weekday: "long", day: "numeric", month: "long" };
const TIME_FORMAT = { hour: "2-digit", minute: "2-digit" };
const LONG_FORMAT = { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" };
const CARD_FORMAT = { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" };
const DAY_ONLY_FORMAT = { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" };

function format(utc, timeZone, options) {
    const finalOptions = { ...options };
    if (timeZone) {
        finalOptions.timeZone = timeZone;
    }
    return new Date(utc).toLocaleString(locale, finalOptions);
}

// ---------- Dates and session times ----------

function render() {
    for (const el of document.querySelectorAll(".hero-date[data-utc]")) {
        const timeZone = mode === "track" ? el.dataset.tz : null;
        el.textContent = format(el.dataset.utc, timeZone, LONG_FORMAT);
    }

    for (const el of document.querySelectorAll(".rc-date[data-utc]")) {
        const timeZone = mode === "track" ? el.dataset.tz : null;
        el.textContent = format(el.dataset.utc, timeZone, CARD_FORMAT);
    }

    // Races without a time yet: only the day.
    for (const el of document.querySelectorAll("[data-day]")) {
        el.textContent = new Date(el.dataset.day + "T12:00:00Z").toLocaleDateString(locale, DAY_ONLY_FORMAT);
    }

    const now = new Date();
    for (const list of document.querySelectorAll(".sessions")) {
        let previousDay = "";
        let nextMarked = false;
        for (const item of list.querySelectorAll("li[data-utc]")) {
            const timeZone = mode === "track" ? item.dataset.tz : null;
            const day = format(item.dataset.utc, timeZone, DAY_FORMAT);
            item.querySelector(".time").textContent = format(item.dataset.utc, timeZone, TIME_FORMAT);
            item.querySelector(".day").textContent = day === previousDay ? "" : day;
            previousDay = day;

            // Timeline dots: finished sessions are filled, the next one pulses.
            const started = new Date(item.dataset.utc) < now;
            item.classList.toggle("is-past", started);
            item.classList.toggle("is-next", !started && !nextMarked);
            if (!started) {
                nextMarked = true;
            }
        }
    }

    renderWeek(now);

    const btnYours = document.getElementById("btn-yours");
    const btnTrack = document.getElementById("btn-track");
    if (btnYours && btnTrack) {
        btnYours.classList.toggle("active", mode === "yours");
        btnTrack.classList.toggle("active", mode === "track");
        const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        btnYours.title = document.body.dataset.tzYours + " (" + zone + ")";
        btnTrack.title = document.body.dataset.tzTrack;
        movePill(btnYours.parentElement, "button.active");
    }
}

// ---------- This week (home page) ----------

// "Today" / "Tomorrow" in the page's language, otherwise the weekday and date.
function weekDayLabel(utc, timeZone, now) {
    const options = { year: "numeric", month: "numeric", day: "numeric" };
    const day = format(utc, timeZone, options);
    const relative = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
    let label = format(utc, timeZone, DAY_FORMAT);
    if (day === format(now, timeZone, options)) {
        label = relative.format(0, "day");
    } else if (day === format(new Date(now.getTime() + 86400000), timeZone, options)) {
        label = relative.format(1, "day");
    }
    return label.charAt(0).toLocaleUpperCase(locale) + label.slice(1);
}

function renderWeek(now) {
    for (const list of document.querySelectorAll(".week-list")) {
        for (const header of list.querySelectorAll(".week-day")) {
            header.remove();
        }
        let previousDay = "";
        for (const item of list.querySelectorAll(".week-item")) {
            const timeZone = mode === "track" ? item.dataset.tz : null;
            item.querySelector(".week-time").textContent = format(item.dataset.utc, timeZone, TIME_FORMAT);
            item.classList.toggle("is-past", new Date(item.dataset.utc) < now);
            // Practice rows that are hidden don't get a day header of their own.
            if (list.classList.contains("hide-practice") && item.classList.contains("practice")) {
                continue;
            }
            const day = weekDayLabel(item.dataset.utc, timeZone, now);
            if (day !== previousDay) {
                const header = document.createElement("li");
                header.className = "week-day";
                header.textContent = day;
                item.before(header);
                previousDay = day;
            }
        }
    }
}

for (const toggle of document.querySelectorAll(".week-toggle")) {
    toggle.addEventListener("click", function () {
        const list = toggle.parentElement.querySelector(".week-list");
        const hidden = list.classList.toggle("hide-practice");
        toggle.textContent = hidden ? toggle.dataset.more : toggle.dataset.less;
        render();
    });
}

// A pill or line that slides to the chosen option.
function movePill(container, activeSelector) {
    const active = container.querySelector(activeSelector);
    if (!active) {
        return;
    }
    container.style.setProperty("--pill-x", active.offsetLeft + "px");
    container.style.setProperty("--pill-w", active.offsetWidth + "px");
    if (!container.classList.contains("ready")) {
        // The first placement happens without animation, after that it slides.
        requestAnimationFrame(function () {
            container.classList.add("ready");
        });
    }
}

// ---------- Countdown with rolling digits ----------

function buildDigits(span, length) {
    span.textContent = "";
    for (let i = 0; i < length; i++) {
        const digit = document.createElement("span");
        digit.className = "digit";
        const reel = document.createElement("span");
        reel.className = "reel";
        for (let n = 0; n <= 9; n++) {
            const b = document.createElement("b");
            b.textContent = n;
            reel.appendChild(b);
        }
        digit.appendChild(reel);
        span.appendChild(digit);
    }
}

function setDigits(span, text) {
    if (span.querySelectorAll(".reel").length !== text.length) {
        buildDigits(span, text.length);
    }
    const reels = span.querySelectorAll(".reel");
    for (let i = 0; i < text.length; i++) {
        reels[i].style.setProperty("--n", text[i]);
    }
}

function countdownParts(target) {
    let remaining = Math.max(0, new Date(target) - new Date());
    const days = Math.floor(remaining / 86400000);
    remaining -= days * 86400000;
    const hours = Math.floor(remaining / 3600000);
    remaining -= hours * 3600000;
    const minutes = Math.floor(remaining / 60000);
    remaining -= minutes * 60000;
    const seconds = Math.floor(remaining / 1000);
    return {
        days: String(days),
        hours: String(hours).padStart(2, "0"),
        minutes: String(minutes).padStart(2, "0"),
        seconds: String(seconds).padStart(2, "0"),
    };
}

function showCountdown(box, zero) {
    const parts = countdownParts(box.dataset.target);
    for (const unit in parts) {
        const span = box.querySelector('[data-unit="' + unit + '"]');
        if (span) {
            setDigits(span, zero ? "0".repeat(parts[unit].length) : parts[unit]);
        }
    }
}

function updateCountdowns() {
    for (const box of document.querySelectorAll(".countdown[data-target]:not([data-waiting])")) {
        showCountdown(box, false);
    }
}

// ---------- Start lights ----------

function startLights() {
    const sets = document.querySelectorAll(".lights");
    const boxes = document.querySelectorAll(".countdown[data-target]");
    let alreadyShown = false;
    try {
        alreadyShown = sessionStorage.getItem(LIGHTS_KEY) === "yes";
        sessionStorage.setItem(LIGHTS_KEY, "yes");
    } catch (error) {
        alreadyShown = false;
    }

    if (reduceMotion) {
        updateCountdowns();
        return;
    }

    // Every digit starts at 0 and rolls to the real time.
    for (const box of boxes) {
        showCountdown(box, true);
        box.dataset.waiting = "true";
    }

    function release() {
        for (const box of boxes) {
            delete box.dataset.waiting;
        }
        updateCountdowns();
    }

    // The lights are shown once per visit; after that the digits just roll in.
    if (sets.length === 0 || alreadyShown) {
        setTimeout(release, 300);
        return;
    }

    for (let i = 0; i < 5; i++) {
        setTimeout(function () {
            for (const set of sets) {
                set.children[i].classList.add("on");
            }
        }, 400 + i * 240);
    }
    // Lights out and away we go.
    setTimeout(function () {
        for (const set of sets) {
            for (const light of set.children) {
                light.classList.remove("on");
            }
        }
        release();
    }, 400 + 5 * 240 + 450);
}

// ---------- Opening and closing (completed races, result tables) ----------

function setupDetails(details) {
    const summary = details.querySelector("summary");
    const content = details.querySelector(".content");
    if (!summary || !content) {
        return;
    }

    summary.addEventListener("click", function (event) {
        if (reduceMotion) {
            return;
        }
        event.preventDefault();
        if (content.getAnimations().length > 0) {
            return;
        }

        if (details.open) {
            details.classList.add("closing");
            const closing = content.animate(
                [
                    { height: content.offsetHeight + "px", opacity: 1 },
                    { height: "0px", opacity: 0 }
                ],
                { duration: 380, easing: EASE_IN_OUT, fill: "forwards" }
            );
            closing.onfinish = function () {
                details.open = false;
                details.classList.remove("closing");
                closing.cancel();
            };
        } else {
            details.open = true;
            content.animate(
                [
                    { height: "0px", opacity: 0 },
                    { height: content.offsetHeight + "px", opacity: 1 }
                ],
                { duration: 560, easing: EASE_OUT }
            );
        }
    });
}

// ---------- Race panel (bottom sheet on phones, window on computers) ----------

const sheet = document.getElementById("race-sheet");
const resultsCache = {};

function sheetPart(selector) {
    return sheet.querySelector(selector);
}

function showTab(name) {
    for (const button of sheet.querySelectorAll(".sheet-tabs button")) {
        const active = button.dataset.tab === name;
        button.classList.toggle("active", active);
        button.setAttribute("aria-selected", active ? "true" : "false");
    }
    for (const pane of sheet.querySelectorAll(".sheet-pane")) {
        pane.hidden = pane.dataset.pane !== name;
    }
    movePill(sheetPart(".sheet-tabs"), "button.active");
}

async function fetchResults(url) {
    if (resultsCache[url]) {
        return resultsCache[url];
    }
    const controller = new AbortController();
    const timer = setTimeout(function () {
        controller.abort();
    }, 15000);
    try {
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
            return "";
        }
        const html = (await response.text()).trim();
        resultsCache[url] = html;
        return html;
    } catch (error) {
        return "";
    } finally {
        clearTimeout(timer);
    }
}

async function openRace(card) {
    const schedule = sheetPart('[data-pane="schedule"]');
    const results = sheetPart('[data-pane="results"]');
    const resultsTab = sheetPart('[data-tab="results"]');
    const done = card.classList.contains("done") || card.classList.contains("past");

    sheetPart(".sheet-round").textContent = card.dataset.label;
    sheetPart(".sheet-title").textContent = card.dataset.name;
    sheetPart(".sheet-place").textContent = card.dataset.place;

    // F1 sends the sessions with the page; MotoGP and WorldSBK send them with the results.
    schedule.innerHTML = "";
    const template = card.querySelector("template.race-sessions");
    if (template) {
        schedule.appendChild(template.content.cloneNode(true));
    }
    results.innerHTML = "";
    resultsTab.hidden = !card.dataset.url;

    showSheet();
    showTab(done && card.dataset.url ? "results" : "schedule");
    render();

    if (!card.dataset.url) {
        return;
    }

    if (!schedule.children.length) {
        schedule.innerHTML = '<div class="skeleton"><span></span><span></span><span></span></div>';
    }
    results.innerHTML = '<div class="skeleton"><span></span><span></span><span></span></div>';

    const html = await fetchResults(card.dataset.url);
    if (sheet.dataset.round !== card.dataset.round) {
        return;
    }
    const box = document.createElement("div");
    box.innerHTML = html;

    // The session list goes to the "Schedule" tab, everything else to "Results".
    const sessions = box.querySelector(".sessions");
    if (sessions) {
        sessions.remove();
    }
    if (!template) {
        schedule.innerHTML = "";
        if (sessions) {
            schedule.appendChild(sessions);
        }
    }

    const hasResults = box.querySelector(".outcome > *, .tables > *");
    results.innerHTML = hasResults ? box.innerHTML : '<p class="note">' + results.dataset.empty + "</p>";
    for (const inner of results.querySelectorAll("details.full-results")) {
        setupDetails(inner);
    }
    markFavourites();
    render();
}

// Opening, closing and dragging the panel are shared with the driver panel (site.js).
let raceSheet = null;

function showSheet() {
    raceSheet.open();
}

function openRound(round) {
    const card = document.getElementById("round-" + round);
    if (!card || card.classList.contains("static")) {
        return;
    }
    sheet.dataset.round = round;
    history.replaceState(null, "", "#round-" + round);
    openRace(card);
}

if (sheet) {
    for (const button of document.querySelectorAll(".race-open")) {
        button.addEventListener("click", function () {
            openRound(button.closest(".race-card").dataset.round);
        });
    }

    for (const link of document.querySelectorAll("[data-open]")) {
        link.addEventListener("click", function (event) {
            event.preventDefault();
            openRound(link.dataset.open);
        });
    }

    for (const button of sheet.querySelectorAll(".sheet-tabs button")) {
        button.addEventListener("click", function () {
            showTab(button.dataset.tab);
        });
    }

    raceSheet = makeSheet(sheet, function () {
        delete sheet.dataset.round;
        history.replaceState(null, "", location.pathname + location.search);
    });

    // A link like kerbline.../wsbk/2026#round-12 opens that race directly.
    const match = location.hash.match(/^#round-(\d+)$/);
    if (match) {
        openRound(match[1]);
    }
}

// ---------- Time toggle ----------

const yoursButton = document.getElementById("btn-yours");
const trackButton = document.getElementById("btn-track");

if (yoursButton && trackButton) {
    yoursButton.addEventListener("click", function () {
        mode = "yours";
        saveMode(mode);
        render();
    });
    trackButton.addEventListener("click", function () {
        mode = "track";
        saveMode(mode);
        render();
    });
}

// ---------- "Add to calendar" menu ----------

for (const button of document.querySelectorAll(".copy-link")) {
    button.addEventListener("click", async function () {
        if (!button.dataset.label) {
            button.dataset.label = button.textContent;
        }
        try {
            await navigator.clipboard.writeText(button.dataset.url);
            button.textContent = button.dataset.copied;
            setTimeout(function () {
                button.textContent = button.dataset.label;
            }, 1800);
        } catch (error) {
            window.prompt("", button.dataset.url);
        }
    });
}

// ---------- Start ----------

render();
startLights();
setInterval(updateCountdowns, 1000);
setInterval(render, 60000);
window.addEventListener("resize", render);

for (const group of document.querySelectorAll("details.completed-group")) {
    setupDetails(group);
}
