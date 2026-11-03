// Small animations used on every page.

const motionOff = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Points count up from 0 when the standings appear.
function countUp(element, delay) {
    const text = element.textContent.trim();
    const target = parseFloat(text);
    if (Number.isNaN(target)) {
        return;
    }
    const decimals = (text.split(".")[1] || "").length;
    const duration = 1200;
    let start = null;

    function step(time) {
        if (start === null) {
            start = time;
        }
        const progress = Math.min(1, (time - start) / duration);
        const eased = 1 - Math.pow(1 - progress, 4);
        element.textContent = (target * eased).toFixed(decimals);
        if (progress < 1) {
            requestAnimationFrame(step);
        }
    }

    element.textContent = (0).toFixed(decimals);
    setTimeout(function () {
        requestAnimationFrame(step);
    }, delay);
}

// Cards get a soft light that follows the mouse.
function followPointer(card) {
    card.addEventListener("pointermove", function (event) {
        const box = card.getBoundingClientRect();
        card.style.setProperty("--mx", (event.clientX - box.left) + "px");
        card.style.setProperty("--my", (event.clientY - box.top) + "px");
    });
}

if (!motionOff) {
    document.querySelectorAll(".count-up").forEach(function (element, index) {
        countUp(element, 200 + Math.min(index, 20) * 30);
    });

    if (window.matchMedia("(hover: hover)").matches) {
        document.querySelectorAll(".spotlight, .race-card:not(.static)").forEach(followPointer);
    }
}

// Small menus (season picker, add to calendar): close with an animation,
// and close when you click somewhere else or press Escape.
function closePopover(details) {
    if (!details.open || details.classList.contains("closing")) {
        return;
    }
    if (motionOff) {
        details.open = false;
        return;
    }
    details.classList.add("closing");
    setTimeout(function () {
        details.open = false;
        details.classList.remove("closing");
    }, 170);
}

for (const summary of document.querySelectorAll("details.popover > summary")) {
    summary.addEventListener("click", function (event) {
        const details = summary.parentElement;
        if (details.open) {
            event.preventDefault();
            closePopover(details);
            return;
        }
        for (const other of document.querySelectorAll("details.popover[open]")) {
            closePopover(other);
        }
    });
}

document.addEventListener("click", function (event) {
    for (const details of document.querySelectorAll("details.popover[open]")) {
        if (!details.contains(event.target)) {
            closePopover(details);
        }
    }
});

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
        for (const details of document.querySelectorAll("details.popover[open]")) {
            closePopover(details);
            details.querySelector("summary").focus();
        }
    }
});

// ---------- Panels: shared opening, closing and dragging ----------
// Used by the race panel (calendar.js) and the driver panel below.

function makeSheet(dialog, onClose) {
    const panel = dialog.querySelector(".sheet-panel");

    function updateScrollLock() {
        const anyOpen = document.querySelector("dialog.sheet[open]") !== null;
        document.documentElement.classList.toggle("sheet-locked", anyOpen);
    }

    function open() {
        if (dialog.open) {
            return;
        }
        dialog.showModal();
        updateScrollLock();
        requestAnimationFrame(function () {
            dialog.classList.add("open");
        });
    }

    function close() {
        if (!dialog.open || dialog.classList.contains("closing")) {
            return;
        }
        panel.style.transform = "";
        dialog.classList.remove("open");
        dialog.classList.add("closing");
        function finish() {
            dialog.classList.remove("closing");
            dialog.close();
            updateScrollLock();
            if (onClose) {
                onClose();
            }
        }
        if (motionOff) {
            finish();
        } else {
            setTimeout(finish, 320);
        }
    }

    dialog.querySelector(".sheet-close").addEventListener("click", close);
    dialog.addEventListener("cancel", function (event) {
        event.preventDefault();
        close();
    });
    // A click on the dark area around the panel closes it.
    dialog.addEventListener("click", function (event) {
        if (event.target === dialog) {
            close();
        }
    });

    // Drag the panel down to close it (phones).
    let startY = null;
    let delta = 0;

    function down(event) {
        if (window.innerWidth > 700 || event.target.closest("button")) {
            return;
        }
        startY = event.clientY;
        delta = 0;
        panel.classList.add("dragging");
    }

    function move(event) {
        if (startY === null) {
            return;
        }
        delta = Math.max(0, event.clientY - startY);
        panel.style.transform = "translateY(" + delta + "px)";
    }

    function up() {
        if (startY === null) {
            return;
        }
        startY = null;
        panel.classList.remove("dragging");
        if (delta > 110) {
            close();
        } else {
            panel.style.transform = "";
        }
    }

    for (const target of dialog.querySelectorAll(".sheet-head, .sheet-grab")) {
        target.addEventListener("pointerdown", down);
    }
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);

    return { open: open, close: close };
}

// ---------- Favourite driver (one per series) ----------
// Kept in a cookie like "fav_f1=Max%20Verstappen", so the server can show it on the home page too.

function getFavourite(series) {
    const prefix = "fav_" + series + "=";
    for (const part of document.cookie.split("; ")) {
        if (part.startsWith(prefix)) {
            try {
                return decodeURIComponent(part.slice(prefix.length));
            } catch (error) {
                return "";
            }
        }
    }
    return "";
}

function setFavourite(series, name) {
    // An empty name deletes the cookie (max-age=0).
    const maxAge = name ? 60 * 60 * 24 * 365 : 0;
    document.cookie = "fav_" + series + "=" + encodeURIComponent(name)
        + "; path=/; max-age=" + maxAge + "; SameSite=Lax";
}

// Gives the favourite's rows and cards a gold star. Also called after results load in the race panel.
function markFavourites() {
    const series = document.body.dataset.series;
    const favourite = series ? getFavourite(series) : "";
    for (const link of document.querySelectorAll(".driver-link")) {
        const isFavourite = favourite !== "" && link.dataset.name === favourite;
        link.classList.toggle("is-fav", isFavourite);
        const row = link.closest("tr");
        if (row) {
            row.classList.toggle("is-fav", isFavourite);
        }
    }
}

markFavourites();

// ---------- Driver panel: photo, season numbers and a short bio ----------

const driverDialog = document.getElementById("driver-sheet");
const driverCache = {};

function driverPart(selector) {
    return driverDialog.querySelector(selector);
}

function initials(name) {
    const words = name.split(" ").filter(Boolean);
    if (words.length === 0) {
        return "";
    }
    const first = words[0][0];
    const last = words.length > 1 ? words[words.length - 1][0] : "";
    return (first + last).toUpperCase();
}

async function fetchDriver(series, name) {
    const key = series + "|" + name;
    if (driverCache[key]) {
        return driverCache[key];
    }
    const url = document.body.dataset.driverInfo
        + "?series=" + encodeURIComponent(series)
        + "&name=" + encodeURIComponent(name)
        + "&lang=" + encodeURIComponent(document.documentElement.lang);
    try {
        const response = await fetch(url);
        if (!response.ok) {
            return null;
        }
        const info = await response.json();
        driverCache[key] = info;
        return info;
    } catch (error) {
        return null;
    }
}

function addFact(list, label, value) {
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = value;
    list.append(term, detail);
}

// Birth date in the page's language, plus the age: "16 Ekim 1999 · 26 yaşında".
function birthText(isoDate) {
    const born = new Date(isoDate + "T12:00:00Z");
    const now = new Date();
    let age = now.getUTCFullYear() - born.getUTCFullYear();
    const birthdayPassed = now.getUTCMonth() > born.getUTCMonth()
        || (now.getUTCMonth() === born.getUTCMonth() && now.getUTCDate() >= born.getUTCDate());
    if (!birthdayPassed) {
        age -= 1;
    }
    const date = born.toLocaleDateString(document.body.dataset.locale, { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
    return date + " · " + driverDialog.dataset.age.replace("{age}", age);
}

// root: where the photo, bio and facts go — the driver panel, or the driver page (driver.js).
function showDriverInfo(info, root) {
    root = root || driverDialog;
    function part(selector) {
        return root.querySelector(selector);
    }
    const bio = part(".driver-bio");
    const credit = part(".driver-credit");
    const facts = part(".driver-facts");
    bio.textContent = "";
    credit.textContent = "";
    facts.textContent = "";

    if (!info || !info.found) {
        const note = document.createElement("p");
        note.className = "note";
        note.textContent = driverDialog.dataset.noInfo;
        bio.appendChild(note);
        return;
    }

    part(".driver-desc").textContent = info.description || "";

    if (info.born) {
        addFact(facts, driverDialog.dataset.born, birthText(info.born));
    }
    if (info.birthplace) {
        addFact(facts, driverDialog.dataset.birthplace, info.birthplace);
    }

    // Text from Wikipedia goes in with textContent, never as HTML.
    for (const part of (info.extract || "").split("\n").filter(Boolean)) {
        const paragraph = document.createElement("p");
        paragraph.textContent = part;
        bio.appendChild(paragraph);
    }
    if (info.url) {
        const link = document.createElement("a");
        link.className = "more-link";
        link.href = info.url;
        link.target = "_blank";
        link.rel = "noopener";
        // Say so when the article is only in English.
        const sameLanguage = info.extract_lang === document.documentElement.lang;
        link.textContent = sameLanguage ? driverDialog.dataset.readMore : driverDialog.dataset.readMoreEn;
        bio.appendChild(link);
    }

    if (info.photo) {
        const box = part(".driver-photo");
        const img = part(".driver-photo img");
        img.onload = function () {
            box.classList.add("loaded");
        };
        img.src = info.photo;
        img.hidden = false;
    }

    if (info.credit) {
        const link = document.createElement("a");
        link.href = info.credit.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = [info.credit.artist, info.credit.license, "Wikimedia Commons"].filter(Boolean).join(" · ");
        credit.append(driverDialog.dataset.photo + ": ", link);
    }
}

async function openDriver(button) {
    const data = button.dataset;
    const series = document.body.dataset.series;

    driverDialog.style.setProperty("--team", data.color || "var(--muted)");
    driverDialog.dataset.name = data.name;
    driverPart(".driver-team").textContent = [data.flag, data.team].filter(Boolean).join("  ");
    driverPart("#driver-name").textContent = data.name;
    driverPart(".driver-desc").textContent = "";
    driverPart(".driver-initials").textContent = initials(data.name);

    const box = driverPart(".driver-photo");
    const img = driverPart(".driver-photo img");
    box.classList.remove("loaded");
    img.hidden = true;
    img.removeAttribute("src");

    for (const stat of driverDialog.querySelectorAll("[data-stat]")) {
        const value = data[stat.dataset.stat];
        const number = stat.querySelector("b");
        stat.hidden = value === undefined || value === "" || value === "None";
        number.textContent = value || "";
        if (!stat.hidden && !motionOff) {
            countUp(number, 250 + Number(stat.style.getPropertyValue("--n")) * 80);
        }
    }

    driverPart(".driver-facts").textContent = "";
    driverPart(".driver-bio").innerHTML = '<div class="skeleton"><span></span><span></span><span></span></div>';
    driverPart(".driver-credit").textContent = "";
    showFavouriteButton(series === "" ? null : getFavourite(series) === data.name);

    // Link to the driver's own page (needs a season, so not on the home page).
    const pageLink = driverPart(".driver-page-link");
    const season = document.body.dataset.season;
    pageLink.hidden = !(series && season && data.slug);
    if (!pageLink.hidden) {
        pageLink.href = "/" + series + "/" + season + "/driver/" + data.slug + "?lang=" + document.documentElement.lang;
    }
    driverPanel.open();

    const info = await fetchDriver(series, data.name);
    if (driverDialog.dataset.name === data.name) {
        showDriverInfo(info);
    }
}

// The star button in the driver panel. null hides it (pages without a series).
function showFavouriteButton(pressed) {
    const button = driverPart(".fav-toggle");
    button.hidden = pressed === null;
    button.setAttribute("aria-pressed", pressed ? "true" : "false");
    button.querySelector("span").textContent = pressed ? button.dataset.on : button.dataset.add;
}

let driverPanel = null;

if (driverDialog) {
    driverPanel = makeSheet(driverDialog);

    const favouriteButton = driverPart(".fav-toggle");
    favouriteButton.addEventListener("click", function () {
        const series = document.body.dataset.series;
        const name = driverDialog.dataset.name;
        const pressed = favouriteButton.getAttribute("aria-pressed") === "true";
        // Picking a new favourite replaces the old one; pressing again removes it.
        setFavourite(series, pressed ? "" : name);
        showFavouriteButton(!pressed);
        markFavourites();
        if (!pressed && !motionOff) {
            favouriteButton.classList.remove("pop");
            void favouriteButton.offsetWidth;  // restarts the animation
            favouriteButton.classList.add("pop");
        }
    });
    // One listener for every driver name, also those that load later inside the race panel.
    document.addEventListener("click", function (event) {
        const button = event.target.closest(".driver-link");
        if (button) {
            event.preventDefault();
            openDriver(button);
        }
    });
}
