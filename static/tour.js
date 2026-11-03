// Intro tour: the first time someone visits, a short walk through the page, one highlighted part at a time.
// The texts come from tour.py (in the page's language) through <script id="tour-data">.
// Steps already shown are remembered, so a page only shows the parts you haven't seen yet.
// The "?" button in the top bar plays the tour of the current page again.

const TOUR_KEY = "kerbline-tour-seen";
const tourMotionOff = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const tourData = JSON.parse(document.getElementById("tour-data").textContent);
let tour = null;

// null means the browser doesn't let us store anything: then the tour never starts by itself,
// otherwise it would show up on every single page.
function loadSeen() {
    try {
        return JSON.parse(localStorage.getItem(TOUR_KEY) || "[]");
    } catch (error) {
        return null;
    }
}

function saveSeen(ids) {
    try {
        localStorage.setItem(TOUR_KEY, JSON.stringify(ids));
    } catch (error) {
        // Nothing to do: storage is blocked.
    }
}

function isVisible(element) {
    const box = element.getBoundingClientRect();
    return box.width > 0 && box.height > 0 && getComputedStyle(element).visibility !== "hidden";
}

function findTarget(selector) {
    for (const element of document.querySelectorAll(selector)) {
        if (isVisible(element)) {
            return element;
        }
    }
    return null;
}

// The top bar and the bottom menu stay in place, so there's nothing to scroll to.
function staysInPlace(element) {
    return element.closest(".topbar, .bottom-nav") !== null;
}

function tourSteps(replay) {
    const seen = loadSeen() || [];
    const onPage = tourData.steps.filter(function (step) {
        return findTarget(step.target) && (replay || !seen.includes(step.id));
    });
    if (replay) {
        return onPage;
    }
    if (seen.length === 0) {
        // The very first visit: hello first, then the page, then two tips.
        const steps = [tourData.welcome].concat(onPage);
        if (findTarget(tourData.help.target)) {
            steps.push(tourData.help);
        }
        steps.push(tourData.install);
        return steps;
    }
    return onPage;
}

// ---------- Drawing ----------

function buildTour() {
    const blocker = document.createElement("div");
    blocker.className = "tour-blocker";
    const hole = document.createElement("div");
    hole.className = "tour-hole";
    const bubble = document.createElement("div");
    bubble.className = "tour-bubble";
    bubble.setAttribute("role", "dialog");
    bubble.setAttribute("aria-live", "polite");
    document.body.append(blocker, hole, bubble);
    return { blocker: blocker, hole: hole, bubble: bubble };
}

function button(className, text, onClick) {
    const element = document.createElement("button");
    element.type = "button";
    element.className = className;
    element.textContent = text;
    element.addEventListener("click", onClick);
    return element;
}

function fillBubble(step, index) {
    const labels = tourData.labels;
    const bubble = tour.parts.bubble;
    const centered = !step.target;
    bubble.textContent = "";
    bubble.classList.toggle("center", centered);

    if (step.id === "welcome") {
        const brand = document.createElement("p");
        brand.className = "tour-brand";
        brand.textContent = "Kerbline";
        const kerb = document.createElement("span");
        kerb.className = "kerb";
        brand.appendChild(kerb);
        bubble.appendChild(brand);
    } else {
        const count = document.createElement("p");
        count.className = "tour-count";
        count.textContent = (index + 1) + " / " + tour.steps.length;
        bubble.appendChild(count);
    }

    const title = document.createElement("p");
    title.className = "tour-title";
    title.textContent = step.title;
    const text = document.createElement("p");
    text.className = "tour-text";
    text.textContent = step.text;
    bubble.append(title, text);

    const actions = document.createElement("div");
    actions.className = "tour-actions";
    const last = index === tour.steps.length - 1;
    if (step.id === "welcome") {
        // Saying "not now" to the welcome means: no tours by themselves any more (the ? button still works).
        actions.append(
            button("tour-skip", labels.later, function () {
                endTour(true);
            }),
            button("tour-next", labels.start, nextStep),
        );
    } else {
        actions.appendChild(button("tour-skip", labels.skip, function () {
            endTour(false);
        }));
        if (index > 0 && tour.steps[index - 1].id !== "welcome") {
            actions.appendChild(button("tour-back", labels.back, previousStep));
        }
        actions.appendChild(button("tour-next", last ? labels.done : labels.next, nextStep));
    }
    bubble.appendChild(actions);

    // Replays the little "rise" animation for every new step.
    bubble.classList.remove("enter");
    void bubble.offsetWidth;
    bubble.classList.add("enter");
}

function placeTour() {
    if (!tour) {
        return;
    }
    const { hole, bubble } = tour.parts;
    const step = tour.steps[tour.index];
    const target = step.target ? findTarget(step.target) : null;
    const width = window.innerWidth;
    const height = window.innerHeight;

    if (!target) {
        // Centred card: the hole shrinks to nothing in the middle, so the whole page is dimmed.
        hole.classList.add("closed");
        Object.assign(hole.style, { left: width / 2 + "px", top: height / 2 + "px", width: "0px", height: "0px" });
        bubble.style.left = Math.max(16, (width - bubble.offsetWidth) / 2) + "px";
        bubble.style.top = Math.max(16, (height - bubble.offsetHeight) / 2) + "px";
        return;
    }

    hole.classList.remove("closed");
    const box = target.getBoundingClientRect();
    const pad = 8;
    const left = Math.max(6, box.left - pad);
    const top = Math.max(6, box.top - pad);
    const right = Math.min(width - 6, box.right + pad);
    const bottom = Math.min(height - 6, box.bottom + pad);
    const radius = parseFloat(getComputedStyle(target).borderTopLeftRadius) || 12;
    Object.assign(hole.style, {
        left: left + "px", top: top + "px", width: (right - left) + "px", height: (bottom - top) + "px",
        borderRadius: Math.min(radius + pad, 28) + "px",
    });

    // The bubble goes under the highlighted part if there's room, otherwise above it,
    // otherwise at the bottom of the screen.
    const bubbleHeight = bubble.offsetHeight;
    const bubbleWidth = bubble.offsetWidth;
    let bubbleTop;
    if (height - bottom >= bubbleHeight + 16) {
        bubbleTop = bottom + 12;
    } else if (top >= bubbleHeight + 16) {
        bubbleTop = top - bubbleHeight - 12;
    } else {
        bubbleTop = height - bubbleHeight - 16;
    }
    const center = (left + right) / 2;
    bubble.style.left = Math.min(width - bubbleWidth - 16, Math.max(16, center - bubbleWidth / 2)) + "px";
    bubble.style.top = Math.max(16, bubbleTop) + "px";
}

function showStep(index) {
    tour.index = index;
    const step = tour.steps[index];
    fillBubble(step, index);
    const target = step.target ? findTarget(step.target) : null;
    if (target && !staysInPlace(target)) {
        target.scrollIntoView({ block: "center", behavior: tourMotionOff ? "auto" : "smooth" });
        // Wait for the scrolling to finish before drawing the highlight.
        placeTour();
        setTimeout(placeTour, tourMotionOff ? 0 : 420);
    } else {
        placeTour();
    }
    tour.parts.bubble.querySelector(".tour-next").focus({ preventScroll: true });
}

function nextStep() {
    if (tour.index < tour.steps.length - 1) {
        showStep(tour.index + 1);
    } else {
        endTour(false);
    }
}

function previousStep() {
    if (tour.index > 0) {
        showStep(tour.index - 1);
    }
}

// ---------- Start and stop ----------

function onTourKey(event) {
    if (event.key === "Escape") {
        endTour(false);
    } else if (event.key === "ArrowRight") {
        nextStep();
    } else if (event.key === "ArrowLeft") {
        previousStep();
    }
}

function onTourMove() {
    requestAnimationFrame(placeTour);
}

function startTour(steps) {
    if (tour || steps.length === 0) {
        return;
    }
    tour = { steps: steps, index: 0, parts: buildTour() };
    document.documentElement.classList.add("touring");
    document.addEventListener("keydown", onTourKey);
    window.addEventListener("resize", onTourMove);
    window.addEventListener("scroll", onTourMove, { passive: true });
    requestAnimationFrame(function () {
        tour.parts.blocker.classList.add("show");
        showStep(0);
    });
}

function endTour(noMoreTours) {
    if (!tour) {
        return;
    }
    // Remember what was shown, so the next pages only show what's new.
    const seen = loadSeen() || [];
    for (const step of tour.steps) {
        if (!seen.includes(step.id)) {
            seen.push(step.id);
        }
    }
    if (noMoreTours && !seen.includes("*")) {
        // "*" = this visitor doesn't want tours to start by themselves.
        seen.push("*");
    }
    saveSeen(seen);

    const parts = tour.parts;
    tour = null;
    document.documentElement.classList.remove("touring");
    document.removeEventListener("keydown", onTourKey);
    window.removeEventListener("resize", onTourMove);
    window.removeEventListener("scroll", onTourMove);
    for (const part of [parts.blocker, parts.hole, parts.bubble]) {
        part.classList.add("leaving");
    }
    setTimeout(function () {
        parts.blocker.remove();
        parts.hole.remove();
        parts.bubble.remove();
    }, tourMotionOff ? 0 : 300);
}

// Waits until the page is calm: no panel open and no champion celebration on screen.
function startWhenCalm(tries) {
    const busy = document.querySelector("dialog[open], .celebration");
    if (busy) {
        if (tries > 0) {
            setTimeout(function () {
                startWhenCalm(tries - 1);
            }, 1000);
        }
        return;
    }
    startTour(tourSteps(false));
}

const helpButton = document.querySelector(".tour-help");
if (helpButton) {
    helpButton.addEventListener("click", function () {
        startTour(tourSteps(true));
    });
}

const seenSoFar = loadSeen();
if (seenSoFar !== null && !seenSoFar.includes("*")) {
    setTimeout(function () {
        startWhenCalm(20);
    }, 1400);
}
