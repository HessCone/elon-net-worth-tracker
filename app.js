(() => {
  const C = window.WorthCalc;
  const TZ = C.TZ;
  const $ = id => document.getElementById(id);
  const HOUR = 3600 * 1000;
  const bust = "?v=" + Math.floor(Date.now() / 60000);
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const fmtCT = (iso, opts) => new Date(iso).toLocaleString("en-US", { timeZone: TZ, ...opts });
  const stamp = iso => fmtCT(iso, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) + " CT";
  const dayLabel = iso => fmtCT(iso, { weekday: "short", month: "short", day: "numeric" });

  function fmtBillions(usd) {
    const abs = Math.abs(usd) / 1e9;
    return (usd < 0 ? "−" : "") + "$" + abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "B";
  }
  function fmtFull(usd) {
    return (usd < 0 ? "−" : "") + "$" + Math.abs(Math.round(usd)).toLocaleString("en-US");
  }
  function fmtAbs(usd) {
    const a = Math.abs(usd);
    if (a >= 1e9) return "$" + (a / 1e9).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "B";
    if (a >= 1e6) return "$" + (a / 1e6).toLocaleString("en-US", { maximumFractionDigits: 1 }) + "M";
    return "$" + Math.round(a).toLocaleString("en-US");
  }
  function fmtDelta(usd) {
    if (usd == null || Number.isNaN(usd)) return "—";
    if (usd > 0) return "+" + fmtAbs(usd);
    if (usd < 0) return "−" + fmtAbs(usd);
    return fmtAbs(0);
  }
  function fmtShares(n) {
    return Math.round(n).toLocaleString("en-US");
  }
  function fmtPrice(n) {
    return "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  }
  function shortCompany(name) {
    return /space exploration technologies/i.test(name) ? "SpaceX" : name;
  }

  function countUp(el, billions) {
    const text = "$" + billions.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "B";
    if (reduceMotion) { el.textContent = text; return; }
    const start = performance.now();
    const ms = 1400;
    const ease = t => 1 - Math.pow(1 - t, 4);
    const step = now => {
      const t = Math.min(1, (now - start) / ms);
      const v = billions * ease(t);
      el.textContent = "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "B";
      if (t < 1) requestAnimationFrame(step);
      else el.textContent = text;
    };
    requestAnimationFrame(step);
  }

  function paintDelta(numId, subId, result, empty) {
    const num = $(numId);
    const sub = $(subId);
    num.classList.remove("up", "down");
    if (!result) {
      num.textContent = "—";
      sub.textContent = empty;
      return null;
    }
    num.textContent = fmtDelta(result.delta);
    if (result.delta > 0) num.classList.add("up");
    else if (result.delta < 0) num.classList.add("down");
    sub.textContent = result.label;
    return result;
  }

  function pageUrl() {
    if (!location.protocol.startsWith("http")) return "";
    if (/localhost|127\.0\.0\.1/.test(location.host)) return "";
    let path = location.pathname;
    if (path.endsWith("/index.html")) path = path.slice(0, -"index.html".length);
    if (!path.endsWith("/")) path += "/";
    return location.origin + path;
  }

  function groups(holdings) {
    const map = new Map();
    for (const row of holdings) {
      if (!map.has(row.company)) {
        map.set(row.company, { company: row.company, ticker: row.ticker, exchange: row.exchange, lines: [], value: 0 });
      }
      const group = map.get(row.company);
      group.lines.push(row);
      group.value += row.value_usd;
    }
    return [...map.values()].sort((a, b) => b.value - a.value);
  }

  const MIX = ["#00e5ff", "#ff3d71", "#7c4dff", "#ffd166", "#8a93a6"];

  function renderHoldings(latest) {
    const foot = $("holdings-foot");
    const box = $("holdings");
    const bar = $("mix-bar");
    const legend = $("mix-legend");
    if (!latest.holdings_included) {
      box.innerHTML = "";
      bar.hidden = true;
      legend.innerHTML = "";
      foot.textContent = latest.holdings_note || "No holdings breakdown in this reading.";
      return;
    }
    const grouped = groups(latest.holdings);
    const parts = grouped.map(g => ({ name: shortCompany(g.company), value: g.value, group: g }));
    if (latest.private_assets_usd) {
      parts.push({ name: "Other private", value: latest.private_assets_usd, group: null });
    }
    box.innerHTML = parts.map((part, i) => {
      const color = MIX[i % MIX.length];
      const pct = latest.worth_usd ? (part.value / latest.worth_usd) * 100 : 0;
      let lines = "";
      if (part.group) {
        const legal = part.group.company !== shortCompany(part.group.company)
          ? `<li>${esc(part.group.company)}</li>` : "";
        const id = [part.group.exchange, part.group.ticker].filter(Boolean).join(" · ");
        lines = `<ul class="holding-lines">${legal}${id ? `<li>${esc(id)}</li>` : ""}${part.group.lines.map(line => {
          const qty = `${fmtShares(line.shares)} ${line.kind === "options" ? "options" : "shares"} at ${fmtPrice(line.price_usd)}`;
          const strike = line.exercise_price_usd != null ? `, strike ${fmtPrice(line.exercise_price_usd)}` : "";
          return `<li>${esc(qty + strike)}</li>`;
        }).join("")}</ul>`;
      } else {
        lines = `<ul class="holding-lines"><li>Forbes private-assets figure. Not split by company.</li></ul>`;
      }
      return `<article class="card"><div class="card-label"><span class="swatch" style="background:${color}"></span>${esc(part.name)}</div><div class="card-num sm">${esc(fmtBillions(part.value))}</div><div class="card-sub">${pct.toFixed(1)}% of the total</div>${lines}</article>`;
    }).join("");
    bar.hidden = false;
    bar.innerHTML = parts.map((part, i) => `<span data-w="${(part.value / latest.worth_usd) * 100}" style="background:${MIX[i % MIX.length]}"></span>`).join("");
    legend.innerHTML = parts.map((part, i) => `<span><span class="swatch" style="background:${MIX[i % MIX.length]}"></span>${esc(part.name)}</span>`).join("");
    requestAnimationFrame(() => {
      bar.querySelectorAll("span").forEach(span => { span.style.width = span.dataset.w + "%"; });
    });
    foot.textContent = "These line items match Forbes's headline total. Options are priced at the share price minus the strike.";
  }

  function renderDays(hist) {
    const rows = C.dailyCloses(hist, TZ);
    let shown = 8;
    const render = () => {
      $("days").innerHTML = rows.slice(0, shown).map(row => {
        const cls = row.delta ? "" : "zero";
        const deltaCls = row.delta > 0 ? "up" : row.delta < 0 ? "down" : "";
        const rounded = row.seeded ? ` <span class="tiny muted">rounded</span>` : "";
        return `<li class="${cls}"><span>${esc(dayLabel(row.t))}${rounded}</span><span class="nums"><b>${esc(fmtBillions(row.worth_usd))}</b><b class="${deltaCls}">${esc(fmtDelta(row.delta))}</b></span></li>`;
      }).join("");
      $("days-more").style.display = rows.length > shown ? "flex" : "none";
    };
    $("days-more").onclick = () => { shown += 14; render(); };
    render();
  }

  function drawChart(hist) {
    if (!window.Chart || !hist.length) return;
    const ctx = $("chart").getContext("2d");
    const g = ctx.createLinearGradient(0, 0, 0, 340);
    g.addColorStop(0, "rgba(0,229,255,.35)");
    g.addColorStop(1, "rgba(0,229,255,0)");
    Chart.defaults.font.family = "Inter, sans-serif";
    Chart.defaults.color = "#8a93a6";
    const data = hist.map(h => ({ x: Date.parse(h.t), y: h.worth_usd, seeded: !!h.seeded }));
    new Chart(ctx, {
      type: "line",
      data: { datasets: [{
        label: "Net worth",
        data,
        borderColor: "#00e5ff",
        backgroundColor: g,
        fill: true,
        cubicInterpolationMode: "monotone",
        borderWidth: 2,
        pointRadius: hist.length > 400 ? 0 : 2,
        pointHoverRadius: 6,
        pointBorderWidth: 2,
        pointBackgroundColor: c => c.raw && c.raw.seeded ? "#05060a" : "#00e5ff",
        pointBorderColor: "#00e5ff",
      }]},
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#0b0d14",
            borderColor: "rgba(0,229,255,.4)",
            borderWidth: 1,
            padding: 12,
            titleFont: { family: "JetBrains Mono" },
            bodyFont: { family: "JetBrains Mono" },
            callbacks: {
              title: items => fmtCT(items[0].parsed.x, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }) + " CT",
              label: item => " " + fmtBillions(item.parsed.y) + (item.raw.seeded ? " (Forbes history, rounded)" : ""),
            },
          },
        },
        scales: {
          x: { type: "time", time: { unit: "day" }, grid: { color: "rgba(255,255,255,.05)" }, ticks: { maxRotation: 0 } },
          y: {
            beginAtZero: false,
            grace: "8%",
            grid: { color: "rgba(255,255,255,.05)" },
            ticks: { callback: v => "$" + (Number(v) / 1e9).toFixed(0) + "B" },
          },
        },
      },
    });
  }

  async function load() {
    const [latest, history] = await Promise.all([
      fetch("data/latest.json" + bust, { cache: "no-cache" }).then(r => r.json()),
      fetch("data/history.json" + bust, { cache: "no-cache" }).then(r => r.json()).catch(() => []),
    ]);
    if (!latest || typeof latest.worth_usd !== "number" || latest.worth_usd < 1e9) {
      throw new Error("bad payload");
    }
    const worth = latest.worth_usd;
    const now = Date.parse(latest.as_of || latest.checked_at);
    countUp($("worth"), worth / 1e9);
    $("worth-exact").textContent = fmtFull(worth);

    const when = latest.as_of || latest.checked_at;
    $("as-of").textContent = stamp(when);
    const source = latest.source || {};
    const sourceName = source.name || "Forbes";
    $("source-line").innerHTML = `Source: <a href="${esc(source.url || "https://www.forbes.com/real-time-billionaires/")}" target="_blank" rel="noopener">${esc(sourceName)}</a>`;
    $("source-id").textContent = source.id || "—";
    if (source.api) $("api-link").href = source.api;
    if (source.url) $("source-link").href = source.url;
    if (source.fallback) $("live-label").innerHTML = `FALLBACK<span class="hide-sm"> · ${esc(source.id || "FORBES")}</span>`;

    const hist = (Array.isArray(history) ? history : []).slice().sort((a, b) => a.t < b.t ? -1 : 1);
    const todayCut = C.startOfZonedDay(TZ, now);
    const ageLabel = base => {
      const hours = (now - Date.parse(base.t)) / HOUR;
      const span = hours >= 36 ? Math.round(hours / 24) + " days earlier" : Math.round(hours) + " h earlier";
      return "vs " + stamp(base.t) + " · " + span;
    };
    let today = C.changeSince(hist, worth, todayCut, 36 * HOUR, false);
    if (today) today.label = ageLabel(today.base);
    else if (typeof latest.forbes_previous_worth_usd === "number") {
      today = { delta: worth - latest.forbes_previous_worth_usd, label: "Forbes day change" };
    }
    const week = C.changeSince(hist, worth, now - 7 * C.DAY, 2 * C.DAY, true);
    if (week) week.label = ageLabel(week.base);
    const month = C.changeSince(hist, worth, now - 30 * C.DAY, 4 * C.DAY, true);
    if (month) month.label = ageLabel(month.base);

    paintDelta("d-today", "d-today-sub", today, "Needs an earlier reading");
    paintDelta("d-week", "d-week-sub", week, "Needs a week of history");
    paintDelta("d-month", "d-month-sub", month, "Needs a month of history");

    const chip = $("today-chip");
    chip.classList.remove("flat", "up", "down");
    if (!today) { chip.textContent = "Today's change needs more history"; chip.classList.add("flat"); }
    else if (today.delta > 0) { chip.textContent = "▲ " + fmtAbs(today.delta) + " today"; chip.classList.add("up"); }
    else if (today.delta < 0) { chip.textContent = "▼ " + fmtAbs(today.delta) + " today"; chip.classList.add("down"); }
    else { chip.textContent = "No change today"; chip.classList.add("flat"); }

    $("rank").textContent = latest.rank ? "#" + latest.rank : "—";

    const changeLabel = !today ? "" : today.delta > 0 ? "up " + fmtAbs(today.delta) + " today" : today.delta < 0 ? "down " + fmtAbs(today.delta) + " today" : "unchanged today";
    const text = C.shareText(fmtBillions(worth), changeLabel, pageUrl());
    $("share-x").href = "https://x.com/intent/post?text=" + encodeURIComponent(text);

    renderHoldings(latest);
    renderDays(hist);
    drawChart(hist);
  }

  load().catch(err => {
    console.error(err);
    $("live-label").textContent = "DATA UNAVAILABLE";
    $("worth").textContent = "—";
  });
  setTimeout(() => location.reload(), 10 * 60e3);
})();
