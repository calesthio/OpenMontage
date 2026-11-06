import { el, fmtAgo, getJSON, subscribe, thumbURL } from "/ui/lib.js";

const grid = document.getElementById("grid");
const THEME_KEY = "backlot.theme";
let currentTheme = localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";

function applyTheme(theme) {
  currentTheme = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = currentTheme;
  localStorage.setItem(THEME_KEY, currentTheme);
}

function renderThemeToggle() {
  const next = currentTheme === "light" ? "dark" : "light";
  return el("button", {
    class: "theme-toggle",
    type: "button",
    title: `Switch to ${next} theme`,
    "aria-label": `Switch to ${next} theme`,
    "aria-pressed": currentTheme === "light" ? "true" : "false",
    onclick: () => {
      applyTheme(next);
      const replacement = renderThemeToggle();
      document.querySelector(".theme-toggle").replaceWith(replacement);
    },
  }, el("span", { class: "theme-toggle-icon", "aria-hidden": "true" }, currentTheme === "light" ? "☾" : "☀"));
}

applyTheme(currentTheme);
document.getElementById("liveBadge").before(renderThemeToggle());

function miniRail(states) {
  const rail = el("div", { class: "mini-rail" });
  for (const s of states) {
    const cls = s.status === "completed" ? "d"
      : s.status === "in_progress" ? "a"
      : s.status === "awaiting_human" ? "w" : "";
    rail.append(el("i", { class: cls, title: `${s.name}: ${s.status}` }));
  }
  return rail;
}

function card(p) {
  const poster = el("div", { class: "lib-poster" });
  if (p.poster) {
    poster.append(el("img", { src: thumbURL(p.project_id, p.poster, 640), loading: "lazy", alt: "" }));
  } else {
    poster.append(el("span", { class: "lp-txt" }, "NO MEDIA YET"));
  }
  if (p.live && p.active_stage) {
    poster.append(el("span", { class: "lp-live" },
      el("span", { class: "dot" }),
      p.awaiting_human ? "◈ AWAITING YOU" : `LIVE · ${p.active_stage.toUpperCase()}`));
  } else if (p.awaiting_human) {
    poster.append(el("span", { class: "lp-live" }, "◈ AWAITING YOU"));
  }

  const meta = el("div", { class: "lb-meta" },
    el("span", { class: "chip" }, p.pipeline_type || "unknown"),
    p.scene_count ? el("span", { class: "chip" }, `${p.scene_count} scenes`) : null,
    p.render_count ? el("span", { class: "chip" }, `${p.render_count} renders`) : null,
    el("span", { class: "when" }, fmtAgo(p.last_activity)),
  );

  const staticSuffix = new URLSearchParams(location.search).has("static") ? "?static=1" : "";
  return el("a", { class: `lib-card${p.live ? " live-card" : ""}`, href: `/p/${p.project_id}${staticSuffix}`, style: "text-decoration:none;color:inherit" },
    poster,
    el("div", { class: "lib-body" },
      el("h3", {}, (p.title || p.project_id).toUpperCase()),
      meta,
      p.stage_states.length ? miniRail(p.stage_states) : null,
    ),
  );
}

// Series sections remember open/closed per viewer; storage may be unavailable.
const SERIES_KEY = "backlot.series.collapsed";
function loadCollapsed() {
  try { return new Set(JSON.parse(localStorage.getItem(SERIES_KEY) || "[]")); } catch { return new Set(); }
}
function saveCollapsed(set) {
  try { localStorage.setItem(SERIES_KEY, JSON.stringify([...set])); } catch { /* ignore */ }
}

function seriesSection(name, members, collapsed) {
  const live = members.filter((p) => p.live).length;
  const awaiting = members.filter((p) => p.awaiting_human).length;
  const latest = Math.max(...members.map((p) => p.last_activity || 0));
  const details = el("details", { class: `lib-series${live ? " live-series" : ""}`, "data-series": name });
  details.open = !collapsed.has(name);
  details.addEventListener("toggle", () => {
    const set = loadCollapsed();
    if (details.open) set.delete(name); else set.add(name);
    saveCollapsed(set);
  });
  details.append(
    el("summary", {},
      el("span", { class: "ls-caret", "aria-hidden": "true" }, "▸"),
      el("h2", {}, name.toUpperCase()),
      el("span", { class: "chip" }, `${members.length} ${members.length === 1 ? "project" : "projects"}`),
      live ? el("span", { class: "chip ls-live" }, el("span", { class: "dot" }), `${live} LIVE`) : null,
      awaiting ? el("span", { class: "chip ls-live" }, `◈ ${awaiting} AWAITING YOU`) : null,
      el("span", { class: "when" }, fmtAgo(latest)),
    ),
    el("div", { class: "lib-grid ls-grid" }, ...members.map(card)),
  );
  return details;
}

// Projects arrive live-first, then by recency. A series is placed where its
// first (most relevant) member would have been; loose projects stay in place.
function layout(projects) {
  const bySeries = new Map();
  const items = [];
  for (const p of projects) {
    if (!p.series) { items.push(p); continue; }
    if (!bySeries.has(p.series)) { bySeries.set(p.series, []); items.push({ series: p.series }); }
    bySeries.get(p.series).push(p);
  }
  return { items, bySeries };
}

async function render() {
  const projects = await getJSON("/api/projects");
  const { items, bySeries } = layout(projects);
  const seriesCount = bySeries.size;
  document.getElementById("count").textContent = `${projects.length} projects`
    + (seriesCount ? ` · ${seriesCount} series` : "");
  const liveCount = projects.filter((p) => p.live).length;
  const badge = document.getElementById("liveBadge");
  badge.classList.toggle("idle", liveCount === 0);
  document.getElementById("liveText").textContent = liveCount ? `${liveCount} LIVE` : "IDLE";
  grid.innerHTML = "";
  document.getElementById("empty").style.display = projects.length ? "none" : "block";
  const collapsed = loadCollapsed();
  for (const item of items) {
    grid.append(item.project_id ? card(item) : seriesSection(item.series, bySeries.get(item.series), collapsed));
  }
}

render().catch(console.error);
if (!new URLSearchParams(location.search).has("static")) {
  subscribe("/api/library/events", () => render().catch(console.error));
}
