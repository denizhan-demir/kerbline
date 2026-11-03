// Charts drawn by hand with SVG and plain HTML, no library needed:
// - the title fight on the standings page (points after every round, one line per driver)
// - the points-per-round bars on a driver page (used by driver.js)

const chartMotionOff = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const SVG_NS = "http://www.w3.org/2000/svg";

function svg(name, attributes, parent) {
    const element = document.createElementNS(SVG_NS, name);
    for (const key in attributes) {
        element.setAttribute(key, attributes[key]);
    }
    if (parent) {
        parent.appendChild(element);
    }
    return element;
}

// A step that looks good on the axis: 10, 20, 25, 50, 100...
function niceStep(max, lines) {
    const raw = max / lines;
    const power = Math.pow(10, Math.floor(Math.log10(raw)));
    for (const factor of [1, 2, 2.5, 5, 10]) {
        if (raw <= factor * power) {
            return factor * power;
        }
    }
    return 10 * power;
}

function formatPoints(value) {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

// Fetches JSON; null when it fails. The first load can be slow, so we wait up to a minute.
async function loadJSON(url) {
    const controller = new AbortController();
    const timer = setTimeout(function () {
        controller.abort();
    }, 60000);
    try {
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
            return null;
        }
        return await response.json();
    } catch (error) {
        return null;
    } finally {
        clearTimeout(timer);
    }
}

function chartMessage(body, text) {
    body.textContent = "";
    const note = document.createElement("p");
    note.className = "note";
    note.textContent = text;
    body.appendChild(note);
}

// ---------- Title fight (line chart) ----------

function drawLineChart(card, data, animate) {
    const body = card.querySelector(".chart-body");
    body.textContent = "";

    const rounds = data.rounds;
    const lines = data.lines;
    const count = rounds.length;
    const width = Math.max(280, body.clientWidth);
    const narrow = width < 560;
    const height = narrow ? 250 : 320;
    const pad = { left: 36, right: narrow ? 78 : 96, top: 14, bottom: 30 };
    const plotWidth = width - pad.left - pad.right;
    const plotHeight = height - pad.top - pad.bottom;

    let max = 0;
    for (const line of lines) {
        for (const value of line.points) {
            max = Math.max(max, value);
        }
    }
    const step = niceStep(max || 10, 4);
    const top = Math.ceil((max || 10) / step) * step;

    // Position 0 is "before the season" (0 points), position 1 is after round one, and so on.
    function x(index) {
        return pad.left + index / count * plotWidth;
    }
    function y(value) {
        return pad.top + plotHeight - value / top * plotHeight;
    }

    const chart = svg("svg", {
        viewBox: `0 0 ${width} ${height}`, width: width, height: height,
        class: "line-chart", role: "img", "aria-label": card.querySelector(".chart-title").textContent,
    }, body);

    // Horizontal guide lines with the points on the left.
    for (let value = 0; value <= top; value += step) {
        svg("line", { x1: pad.left, x2: width - pad.right, y1: y(value), y2: y(value), class: "grid" }, chart);
        const label = svg("text", { x: pad.left - 8, y: y(value) + 4, class: "axis", "text-anchor": "end" }, chart);
        label.textContent = formatPoints(value);
    }

    // Flags along the bottom; with many rounds on a phone only every second or third one.
    const every = Math.max(1, Math.ceil(count / (plotWidth / 22)));
    rounds.forEach(function (round, index) {
        if ((count - 1 - index) % every !== 0) {
            return;
        }
        const label = svg("text", { x: x(index + 1), y: height - 8, class: "axis flag", "text-anchor": "middle" }, chart);
        label.textContent = round.flag || round.round;
    });

    // The lines sit behind a "curtain" that opens from left to right, so they seem to draw themselves.
    const clipId = "clip-" + Math.random().toString(36).slice(2);
    const clip = svg("clipPath", { id: clipId }, svg("defs", {}, chart));
    const curtain = svg("rect", { x: 0, y: 0, width: animate ? 0 : width, height: height }, clip);
    const group = svg("g", { "clip-path": `url(#${clipId})` }, chart);

    // The leader is drawn last, so their line ends up on top.
    lines.slice().reverse().forEach(function (line) {
        const points = [0].concat(line.points);
        let path = "";
        points.forEach(function (value, index) {
            path += (index ? " L" : "M") + x(index).toFixed(1) + " " + y(value).toFixed(1);
        });
        svg("path", { d: path, class: "line" + (line.dashed ? " dashed" : ""), stroke: line.color }, group);
        svg("circle", { cx: x(count), cy: y(points[count]), r: 4, fill: line.color }, group);
    });

    // Names at the end of the lines, nudged apart so they never overlap.
    const tags = lines.map(function (line) {
        return { line: line, y: y(line.points[count - 1]) };
    }).sort(function (a, b) {
        return a.y - b.y;
    });
    for (let i = 1; i < tags.length; i++) {
        tags[i].y = Math.max(tags[i].y, tags[i - 1].y + 15);
    }
    for (let i = tags.length - 1; i >= 0; i--) {
        const limit = i === tags.length - 1 ? pad.top + plotHeight : tags[i + 1].y - 15;
        tags[i].y = Math.min(tags[i].y, limit);
    }
    const season = document.body.dataset.season;
    tags.forEach(function (tag, index) {
        const link = svg("a", { href: `/${document.body.dataset.series}/${season}/driver/${tag.line.slug}` }, chart);
        const text = svg("text", {
            x: x(count) + 10, y: tag.y + 4, fill: tag.line.color,
            class: "end-label" + (animate ? " later" : ""), style: `--k: ${index}`,
        }, link);
        text.textContent = tag.line.short;
    });

    if (animate && !chartMotionOff) {
        const start = performance.now();
        function frame(now) {
            // The first frame can be stamped a hair before "start", so keep it between 0 and 1.
            const progress = Math.max(0, Math.min(1, (now - start) / 1500));
            curtain.setAttribute("width", width * (1 - Math.pow(1 - progress, 3)));
            if (progress < 1) {
                requestAnimationFrame(frame);
            }
        }
        requestAnimationFrame(frame);
    } else {
        curtain.setAttribute("width", width);
    }

    // Hover (or drag a finger) to see everyone's points after that round.
    const guide = svg("line", { class: "guide", x1: 0, x2: 0, y1: pad.top, y2: pad.top + plotHeight, visibility: "hidden" }, chart);
    const tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    body.appendChild(tip);

    function show(event) {
        const box = chart.getBoundingClientRect();
        const pointerX = (event.clientX - box.left) * (width / box.width);
        const index = Math.max(1, Math.min(count, Math.round((pointerX - pad.left) / plotWidth * count)));
        const round = rounds[index - 1];
        guide.setAttribute("x1", x(index));
        guide.setAttribute("x2", x(index));
        guide.setAttribute("visibility", "visible");

        tip.textContent = "";
        const head = document.createElement("p");
        head.className = "chart-tip-head";
        head.textContent = `${round.flag} ${card.dataset.round} ${round.round} · ${round.name}`;
        tip.appendChild(head);
        const rows = lines.map(function (line) {
            return { line: line, value: line.points[index - 1] };
        }).sort(function (a, b) {
            return b.value - a.value;
        });
        for (const row of rows) {
            const item = document.createElement("p");
            const dot = document.createElement("i");
            dot.style.background = row.line.color;
            const name = document.createElement("span");
            name.textContent = row.line.short;
            const value = document.createElement("b");
            value.textContent = formatPoints(row.value);
            item.append(dot, name, value);
            tip.appendChild(item);
        }
        tip.hidden = false;

        // The box goes to the side of the line that has more room.
        const guideX = x(index) / width * box.width;
        const left = guideX > box.width / 2 ? guideX - tip.offsetWidth - 14 : guideX + 14;
        tip.style.left = Math.max(0, left) + "px";
    }

    function hide() {
        tip.hidden = true;
        guide.setAttribute("visibility", "hidden");
    }

    chart.addEventListener("pointermove", show);
    chart.addEventListener("pointerdown", show);
    chart.addEventListener("pointerleave", hide);
}

async function startTitleFight(card) {
    const body = card.querySelector(".chart-body");
    const data = await loadJSON(card.dataset.url);
    if (!data) {
        chartMessage(body, card.dataset.error);
        return;
    }
    if (!data.rounds.length || !data.lines.length) {
        chartMessage(body, card.dataset.empty);
        return;
    }
    drawLineChart(card, data, true);

    // Phones turn, windows resize: draw again at the new width (without the animation).
    let lastWidth = body.clientWidth;
    let timer = null;
    window.addEventListener("resize", function () {
        clearTimeout(timer);
        timer = setTimeout(function () {
            if (body.clientWidth !== lastWidth) {
                lastWidth = body.clientWidth;
                drawLineChart(card, data, false);
            }
        }, 150);
    });
}

const titleFight = document.getElementById("title-fight");
if (titleFight) {
    startTitleFight(titleFight);
}

// ---------- Points per round (bars, driver pages) ----------

function drawBars(body, results, color, labels) {
    body.textContent = "";
    let max = 1;
    for (const result of results) {
        max = Math.max(max, result.points);
    }

    const bars = document.createElement("div");
    bars.className = "bars" + (results.length > 12 ? " many" : "");
    bars.style.setProperty("--count", results.length);
    bars.style.setProperty("--team", color);

    results.forEach(function (result, index) {
        const column = document.createElement("div");
        column.className = "bar-col";
        column.tabIndex = 0;
        column.style.setProperty("--i", index);
        column.title = `${labels.round} ${result.round} · ${result.name}: ${formatPoints(result.points)} ${labels.points}`;

        const value = document.createElement("span");
        value.className = "bar-value";
        value.textContent = formatPoints(result.points);

        const bar = document.createElement("div");
        bar.className = "bar" + (result.points === 0 ? " zero" : "");
        bar.style.setProperty("--h", (result.points / max * 100) + "%");

        const flag = document.createElement("span");
        flag.className = "bar-flag";
        flag.textContent = result.flag;

        column.append(value, bar, flag);
        bars.appendChild(column);
    });
    body.appendChild(bars);
}
