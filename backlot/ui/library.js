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

// ---------------------------------------------------------------------------
// Series navigation. Projects may carry an optional `series` label
// (project.json). The library shows one card per series plus every loose
// project; `/?series=<name>` shows that series' projects with the original
// grid; `/?view=series` lists only the series. Projects without a label
// render exactly as they always did.
// ---------------------------------------------------------------------------

const params = new URLSearchParams(location.search);
const isStatic = params.has("static");

function libURL(query = {}) {
  const q = new URLSearchParams(query);
  if (isStatic) q.set("static", "1");
  const s = q.toString();
  return s ? `/?${s}` : "/";
}

function seriesCard(name, members) {
  const live = members.filter((p) => p.live).length;
  const awaiting = members.filter((p) => p.awaiting_human).length;
  const latest = Math.max(...members.map((p) => p.last_activity || 0));
  const lead = members.find((p) => p.poster);
  const poster = el("div", { class: "lib-poster" });
  if (lead) {
    poster.append(el("img", { src: thumbURL(lead.project_id, lead.poster, 640), loading: "lazy", alt: "" }));
  } else {
    poster.append(el("span", { class: "lp-txt" }, "NO MEDIA YET"));
  }
  if (live || awaiting) {
    poster.append(el("span", { class: "lp-live" },
      live ? el("span", { class: "dot" }) : null,
      [live ? `${live} LIVE` : null, awaiting ? `◈ ${awaiting} AWAITING YOU` : null].filter(Boolean).join(" · ")));
  }
  return el("a", {
    class: `lib-card series-card${live ? " live-card" : ""}`,
    href: libURL({ series: name }),
    style: "text-decoration:none;color:inherit",
  },
    poster,
    el("div", { class: "lib-body" },
      el("h3", {}, el("span", { class: "series-tag" }, "SERIES"), " ", name.toUpperCase()),
      el("div", { class: "lb-meta" },
        el("span", { class: "chip" }, `${members.length} ${members.length === 1 ? "project" : "projects"}`),
        el("span", { class: "when" }, fmtAgo(latest)),
      ),
    ),
  );
}

// Projects arrive live-first, then by recency; a series takes the slot of its
// most relevant member, loose projects keep their own slot.
function group(projects) {
  const bySeries = new Map();
  const items = [];
  for (const p of projects) {
    if (!p.series) { items.push(p); continue; }
    if (!bySeries.has(p.series)) { bySeries.set(p.series, []); items.push({ series: p.series }); }
    bySeries.get(p.series).push(p);
  }
  return { items, bySeries };
}

function renderNav(current, bySeries, view) {
  const nav = document.getElementById("nav");
  nav.innerHTML = "";
  if (!bySeries.size && !current) { nav.hidden = true; return; }
  nav.hidden = false;
  if (current) {
    nav.append(el("a", { class: "nav-link", href: libURL() }, "← Library"));
    nav.append(el("a", { class: "nav-link", href: libURL({ view: "series" }) }, "All series"));
    if (bySeries.size > 1) {
      const pick = el("select", {
        class: "nav-select", "aria-label": "Jump to series",
        onchange: (e) => { location.href = libURL({ series: e.target.value }); },
      });
      for (const name of bySeries.keys()) {
        const opt = el("option", { value: name }, name);
        if (name === current) opt.selected = true;
        pick.append(opt);
      }
      nav.append(pick);
    }
  } else {
    nav.append(el("a", { class: `nav-link${view === "series" ? "" : " on"}`, href: libURL() }, "All"));
    nav.append(el("a", { class: `nav-link${view === "series" ? " on" : ""}`, href: libURL({ view: "series" }) }, `Series (${bySeries.size})`));
  }
}

async function render() {
  const projects = await getJSON("/api/projects");
  const { items, bySeries } = group(projects);
  const current = params.get("series");
  const view = params.get("view");
  const shown = current ? (bySeries.get(current) || []) : projects;

  document.getElementById("title").textContent = current ? current.toUpperCase() : (view === "series" ? "Series" : "Library");
  document.title = current ? `Backlot — ${current}` : "Backlot — Library";
  document.getElementById("count").textContent = current
    ? `${shown.length} ${shown.length === 1 ? "project" : "projects"}`
    : `${projects.length} projects` + (bySeries.size ? ` · ${bySeries.size} series` : "");
  const liveCount = shown.filter((p) => p.live).length;
  const badge = document.getElementById("liveBadge");
  badge.classList.toggle("idle", liveCount === 0);
  document.getElementById("liveText").textContent = liveCount ? `${liveCount} LIVE` : "IDLE";
  renderNav(current, bySeries, view);

  grid.innerHTML = "";
  const empty = document.getElementById("empty");
  if (current) {
    empty.textContent = `No projects in series "${current}".`;
    empty.style.display = shown.length ? "none" : "block";
    for (const p of shown) grid.append(card(p));
    return;
  }
  if (view === "series") {
    empty.textContent = "No series yet — add a \"series\" label to a project's project.json.";
    empty.style.display = bySeries.size ? "none" : "block";
    for (const [name, members] of bySeries) grid.append(seriesCard(name, members));
    return;
  }
  empty.textContent = "No projects yet — run a production and it will appear here.";
  empty.style.display = projects.length ? "none" : "block";
  for (const item of items) {
    grid.append(item.project_id ? card(item) : seriesCard(item.series, bySeries.get(item.series)));
  }
}

render().catch(console.error);
if (!isStatic) {
  subscribe("/api/library/events", () => render().catch(console.error));
}
