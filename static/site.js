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
