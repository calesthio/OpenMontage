import { el, fmtAgo, getJSON, postJSON, subscribe, thumbURL } from "/ui/lib.js";

const grid = document.getElementById("grid");
const wrap = document.querySelector(".wrap");
const THEME_KEY = "backlot.theme";
let currentTheme = localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
let pipelineChoices = ["animated-explainer", "cinematic", "screen-demo", "documentary-montage"];

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

function createStarter() {
  const card = el("section", { class: "panel starter-panel" },
    el("div", { class: "panel-head" },
      el("h2", {}, "New video"),
      el("span", { class: "meta" }, "enter a prompt and create a project"),
    ),
  );
  const body = el("div", { class: "panel-body starter-body" });
  const title = el("input", { class: "starter-input", type: "text", name: "title", placeholder: "Title (optional)" });
  const prompt = el("textarea", { class: "starter-textarea", name: "prompt", rows: "5", placeholder: "Describe the video you want to make" });
  const pipeline = el("select", { class: "starter-select", name: "pipeline_type" },
    ...pipelineChoices.map((name) => el("option", { value: name }, name)),
  );
  const style = el("select", { class: "starter-select", name: "style_playbook" },
    el("option", { value: "clean-professional" }, "clean-professional"),
    el("option", { value: "flat-motion-graphics" }, "flat-motion-graphics"),
    el("option", { value: "minimalist-diagram" }, "minimalist-diagram"),
  );
  const status = el("div", { class: "starter-status" }, "");
  const submit = el("button", { class: "starter-submit", type: "submit" }, "Create project");
  const form = el("form", { class: "starter-form" },
    title,
    prompt,
    el("div", { class: "starter-row" }, pipeline, style),
    el("div", { class: "starter-actions" }, submit, status),
  );
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = {
      title: title.value.trim(),
      prompt: prompt.value.trim(),
      pipeline_type: pipeline.value,
      style_playbook: style.value,
    };
    if (!body.prompt) {
      status.textContent = "Prompt is required.";
      return;
    }
    submit.disabled = true;
    status.textContent = "Creating project…";
    try {
      const result = await postJSON("/api/projects/create", body);
      location.href = result.project_url;
    } catch (err) {
      status.textContent = err.message || String(err);
      submit.disabled = false;
    }
  });
  body.append(form);
  card.append(body);
  wrap.prepend(card);
}

async function loadPipelines() {
  try {
    const list = await getJSON("/api/pipelines");
    if (Array.isArray(list) && list.length) pipelineChoices = list;
  } catch {
    // Keep the built-in defaults if the endpoint is unavailable.
  }
}

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

async function render() {
  const projects = await getJSON("/api/projects");
  document.getElementById("count").textContent = `${projects.length} projects`;
  const liveCount = projects.filter((p) => p.live).length;
  const badge = document.getElementById("liveBadge");
  badge.classList.toggle("idle", liveCount === 0);
  document.getElementById("liveText").textContent = liveCount ? `${liveCount} LIVE` : "IDLE";
  grid.innerHTML = "";
  document.getElementById("empty").style.display = projects.length ? "none" : "block";
  for (const p of projects) grid.append(card(p));
}

await loadPipelines();
createStarter();
render().catch(console.error);
if (!new URLSearchParams(location.search).has("static")) {
  subscribe("/api/library/events", () => render().catch(console.error));
}
