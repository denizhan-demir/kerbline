const MODE_KEY = "kerbline-time-mode";

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

const DATE_FORMAT = { day: "2-digit", month: "2-digit", year: "numeric" };
const DAY_FORMAT = { weekday: "long", day: "numeric", month: "long" };
const TIME_FORMAT = { hour: "2-digit", minute: "2-digit" };
const LONG_FORMAT = { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" };

function format(utc, timeZone, options) {
    const finalOptions = { ...options };
    if (timeZone) {
        finalOptions.timeZone = timeZone;
    }
    return new Date(utc).toLocaleString(locale, finalOptions);
}

function render() {
    for (const el of document.querySelectorAll(".date[data-utc]")) {
        const timeZone = mode === "track" ? el.dataset.tz : null;
        el.textContent = format(el.dataset.utc, timeZone, DATE_FORMAT);
    }

    for (const el of document.querySelectorAll(".hero-date[data-utc]")) {
        const timeZone = mode === "track" ? el.dataset.tz : null;
        el.textContent = format(el.dataset.utc, timeZone, LONG_FORMAT);
    }

    for (const list of document.querySelectorAll(".sessions")) {
        let previousDay = "";
        for (const item of list.querySelectorAll("li[data-utc]")) {
            const timeZone = mode === "track" ? item.dataset.tz : null;
            const day = format(item.dataset.utc, timeZone, DAY_FORMAT);
            item.querySelector(".time").textContent = format(item.dataset.utc, timeZone, TIME_FORMAT);
            item.querySelector(".day").textContent = day === previousDay ? "" : day;
            previousDay = day;
        }
    }

    const btnYours = document.getElementById("btn-yours");
    const btnTrack = document.getElementById("btn-track");
    if (btnYours && btnTrack) {
        btnYours.classList.toggle("active", mode === "yours");
        btnTrack.classList.toggle("active", mode === "track");
        const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        btnYours.title = document.body.dataset.tzYours + " (" + zone + ")";
        btnTrack.title = document.body.dataset.tzTrack;
    }
}

function updateCountdowns() {
    for (const box of document.querySelectorAll(".countdown[data-target]")) {
        updateCountdown(box);
    }
}

function updateCountdown(box) {
    let remaining = Math.max(0, new Date(box.dataset.target) - new Date());
    const days = Math.floor(remaining / 86400000);
    remaining -= days * 86400000;
    const hours = Math.floor(remaining / 3600000);
    remaining -= hours * 3600000;
    const minutes = Math.floor(remaining / 60000);
    remaining -= minutes * 60000;
    const seconds = Math.floor(remaining / 1000);

    box.querySelector('[data-unit="days"]').textContent = days;
    box.querySelector('[data-unit="hours"]').textContent = String(hours).padStart(2, "0");
    box.querySelector('[data-unit="minutes"]').textContent = String(minutes).padStart(2, "0");
    box.querySelector('[data-unit="seconds"]').textContent = String(seconds).padStart(2, "0");
}

function setupDetails(details, onOpen) {
    const summary = details.querySelector("summary");
    const content = details.querySelector(".content");
    if (!summary || !content) {
        return;
    }

    summary.addEventListener("click", function (event) {
        if (!details.open && onOpen) {
            onOpen(details);
        }
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
                { duration: 320, easing: EASE_IN_OUT, fill: "forwards" }
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
                { duration: 520, easing: EASE_OUT }
            );
        }
    });
}

async function loadResults(details) {
    const box = details.querySelector(".results[data-url]");
    if (!box || box.dataset.loaded) {
        return;
    }
    box.dataset.loaded = "true";
    const controller = new AbortController();
    const timer = setTimeout(function () {
        controller.abort();
    }, 15000);
    try {
        const response = await fetch(box.dataset.url, { signal: controller.signal });
        const html = (await response.text()).trim();
        if (!response.ok) {
            delete box.dataset.loaded;
        }
        const startHeight = box.offsetHeight;
        box.innerHTML = html;
        render();
        const endHeight = box.offsetHeight;
        if (!reduceMotion && details.open && startHeight !== endHeight) {
            box.animate(
                [{ height: startHeight + "px" }, { height: endHeight + "px" }],
                { duration: 500, easing: EASE_OUT }
            );
        }
        for (const inner of box.querySelectorAll("details.full-results")) {
            setupDetails(inner, null);
        }
    } catch (error) {
        box.innerHTML = "";
        delete box.dataset.loaded;
    } finally {
        clearTimeout(timer);
    }
}

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

document.addEventListener("click", function (event) {
    for (const menu of document.querySelectorAll("details.subscribe[open]")) {
        if (!menu.contains(event.target)) {
            menu.open = false;
        }
    }
});

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
        for (const menu of document.querySelectorAll("details.subscribe[open]")) {
            menu.open = false;
        }
    }
});

render();
updateCountdowns();
setInterval(updateCountdowns, 1000);

for (const details of document.querySelectorAll("details.race:not(.static)")) {
    setupDetails(details, loadResults);
    if (details.open) {
        loadResults(details);
    }
}

for (const group of document.querySelectorAll("details.completed-group")) {
    setupDetails(group, null);
}