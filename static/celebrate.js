// Champion celebration: confetti in the team's colours and a big banner.
// Plays by itself once per browser (driver title when the page opens, team titles when you scroll to them),
// and again whenever you press "Celebrate again" on the ribbon.

const celebrateMotionOff = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let celebrating = false;

function seenCelebration(key) {
    try {
        return localStorage.getItem(key) === "yes";
    } catch (error) {
        return false;
    }
}

function rememberCelebration(key) {
    try {
        localStorage.setItem(key, "yes");
    } catch (error) {
        // Private browsing: it just plays again next time.
    }
}

// ---------- Confetti ----------

function runConfetti(canvas, colors) {
    const ratio = window.devicePixelRatio || 1;
    const width = window.innerWidth;
    const height = window.innerHeight;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    const context = canvas.getContext("2d");
    context.scale(ratio, ratio);

    const pieces = [];
    function burst(x, y, count, angle, spread, speed) {
        for (let i = 0; i < count; i++) {
            const direction = angle + (Math.random() - 0.5) * spread;
            const velocity = speed * (0.55 + Math.random() * 0.65);
            pieces.push({
                x: x,
                y: y,
                vx: Math.cos(direction) * velocity,
                vy: Math.sin(direction) * velocity,
                size: 6 + Math.random() * 7,
                color: colors[Math.floor(Math.random() * colors.length)],
                turn: Math.random() * Math.PI * 2,
                spin: (Math.random() - 0.5) * 0.35,
                round: Math.random() < 0.25,
            });
        }
    }

    // Two cannons in the bottom corners, then a shower from the top.
    const power = Math.max(14, height / 42);
    burst(0, height, 90, -Math.PI / 3, 0.9, power);
    burst(width, height, 90, -Math.PI * 2 / 3, 0.9, power);
    setTimeout(function () {
        for (let i = 0; i < 70; i++) {
            burst(Math.random() * width, -20, 1, Math.PI / 2, 0.6, 3);
        }
    }, 500);

    const start = performance.now();
    let last = start;
    function frame(now) {
        const step = Math.min(3, (now - last) / 16.7);
        last = now;
        context.clearRect(0, 0, width, height);
        for (const piece of pieces) {
            piece.vy += 0.32 * step;
            piece.vx *= Math.pow(0.985, step);
            piece.vy *= Math.pow(0.985, step);
            piece.x += piece.vx * step;
            piece.y += piece.vy * step;
            piece.turn += piece.spin * step;

            context.save();
            context.translate(piece.x, piece.y);
            context.rotate(piece.turn);
            context.fillStyle = piece.color;
            if (piece.round) {
                context.beginPath();
                context.arc(0, 0, piece.size / 2.6, 0, Math.PI * 2);
                context.fill();
            } else {
                // Squashing the width makes the paper look like it flips in the air.
                context.scale(Math.cos(piece.turn * 2), 1);
                context.fillRect(-piece.size / 2, -piece.size / 4, piece.size, piece.size / 2);
            }
            context.restore();
        }
        if (now - start < 6000) {
            requestAnimationFrame(frame);
        } else {
            context.clearRect(0, 0, width, height);
        }
    }
    requestAnimationFrame(frame);
}

// ---------- Banner ----------

function celebrate(ribbon) {
    if (celebrating) {
        return;
    }
    celebrating = true;
    const data = ribbon.dataset;
    const colors = data.colors.split(",");

    const overlay = document.createElement("div");
    overlay.className = "celebration";
    overlay.style.setProperty("--c1", colors[0]);
    overlay.style.setProperty("--c2", colors[1] || colors[0]);

    const canvas = document.createElement("canvas");
    const card = document.createElement("div");
    card.className = "celebration-card";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-label", data.title + ": " + data.name);

    const parts = [
        ["cel-trophy", "🏆"],
        ["cel-title", data.title],
        ["cel-name", data.name],
        ["cel-team", data.team],
        ["cel-sub", data.sub],
        ["cel-close", data.close],
    ];
    for (const [className, text] of parts) {
        if (!text) {
            continue;
        }
        const element = document.createElement(className === "cel-trophy" ? "span" : "p");
        element.className = className;
        element.textContent = text;
        card.appendChild(element);
    }

    overlay.append(canvas, card);
    document.body.appendChild(overlay);
    requestAnimationFrame(function () {
        overlay.classList.add("show");
    });
    if (!celebrateMotionOff) {
        runConfetti(canvas, colors);
    }

    let timer = null;
    function close() {
        clearTimeout(timer);
        document.removeEventListener("keydown", onKey);
        overlay.classList.remove("show");
        setTimeout(function () {
            overlay.remove();
            celebrating = false;
        }, celebrateMotionOff ? 0 : 450);
    }
    function onKey(event) {
        if (event.key === "Escape") {
            close();
        }
    }
    overlay.addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    timer = setTimeout(close, 6500);
}

// ---------- When to play ----------

function playOnce(ribbon) {
    const key = ribbon.dataset.key;
    if (!ribbon.dataset.auto || seenCelebration(key)) {
        return;
    }
    // If another celebration is still on screen, try again a little later.
    if (celebrating) {
        setTimeout(function () {
            playOnce(ribbon);
        }, 1500);
        return;
    }
    rememberCelebration(key);
    celebrate(ribbon);
}

for (const ribbon of document.querySelectorAll("[data-celebrate]")) {
    ribbon.querySelector(".ribbon-replay").addEventListener("click", function () {
        celebrate(ribbon);
    });

    if (ribbon.dataset.kind === "drivers") {
        // The drivers' title plays as soon as the page has settled.
        setTimeout(function () {
            playOnce(ribbon);
        }, 900);
    } else if ("IntersectionObserver" in window) {
        // Team titles play when you scroll down to them.
        const watcher = new IntersectionObserver(function (entries) {
            if (entries[0].isIntersecting) {
                watcher.disconnect();
                setTimeout(function () {
                    playOnce(ribbon);
                }, 300);
            }
        }, { threshold: 0.8 });
        watcher.observe(ribbon);
    }
}
