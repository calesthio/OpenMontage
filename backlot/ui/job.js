import { el, fmtDuration, getJSON } from "/ui/lib.js";

const transcript = document.getElementById("chatTranscript");
const form = document.getElementById("chatForm");
const input = document.getElementById("chatInput");
const quickRow = document.getElementById("quickRow");
const briefList = document.getElementById("briefList");
const readyEl = document.getElementById("briefReady");
const statusEl = document.getElementById("jobStatus");
const submit = document.getElementById("jobSubmit");
const filesInput = document.getElementById("messageFiles");
const composerAttachments = document.getElementById("composerAttachments");
const modelVariant = document.getElementById("modelVariant");
const modelHelp = document.getElementById("modelHelp");

const MAX_DURATION = 180;
const MODEL_OPTIONS = {
  "grok-imagine-video": {
    label: "Grok Imagine",
    provider: "fal.ai / xAI",
    maxSceneSeconds: 15,
    supportedAspects: ["16:9", "9:16", "1:1", "4:3", "3:4"],
    note: "Default Fal-backed xAI option for character, wardrobe, and product consistency.",
  },
  "kling-v3": {
    label: "Kling 3",
    provider: "fal.ai",
    maxSceneSeconds: 10,
    supportedAspects: ["16:9", "9:16", "1:1"],
    note: "Priority Fal option for cinematic motion. Uses one reference image as image-to-video in this hosted adapter.",
  },
  "veo3.1": {
    label: "Veo 3.1",
    provider: "fal.ai",
    maxSceneSeconds: 8,
    supportedAspects: ["16:9", "9:16"],
    note: "Higher quality reference video through Fal, with slower and costlier clips.",
  },
  "veo3.1-fast": {
    label: "Veo 3.1 Fast",
    provider: "fal.ai",
    maxSceneSeconds: 8,
    supportedAspects: ["16:9", "9:16"],
    note: "Lower-cost Veo route. If it returns no media, retry with Grok instead of looping.",
  },
  "seedance-standard": {
    label: "Seedance 2.0 Standard",
    provider: "fal.ai",
    maxSceneSeconds: 15,
    supportedAspects: ["16:9", "9:16", "1:1", "4:3", "3:4"],
    note: "Opt-in only. Paid generation requires explicit Seedance risk approval.",
  },
  "seedance-fast": {
    label: "Seedance 2.0 Fast",
    provider: "fal.ai",
    maxSceneSeconds: 15,
    supportedAspects: ["16:9", "9:16", "1:1", "4:3", "3:4"],
    note: "Opt-in only. Paid generation requires explicit Seedance risk approval.",
  },
};
const brief = {
  prompt: "",
  duration_seconds: null,
  aspect_ratio: "",
  audience: "",
  style: "",
  must_haves: "",
};

let activeQuestion = "prompt";
let ready = false;
let modelAvailability = {};
let pendingFiles = [];
const referenceFiles = [];
const chatTurns = [];
const previewUrls = new WeakMap();

const ASPECTS = {
  "youtube": "16:9",
  "landscape": "16:9",
  "wide": "16:9",
  "short": "9:16",
  "shorts": "9:16",
  "reel": "9:16",
  "reels": "9:16",
  "tiktok": "9:16",
  "vertical": "9:16",
  "square": "1:1",
  "instagram post": "1:1",
};

function previewUrl(file) {
  if (!previewUrls.has(file)) previewUrls.set(file, URL.createObjectURL(file));
  return previewUrls.get(file);
}

function fileMeta(file) {
  return {
    name: file.name,
    size: file.size,
    type: file.type || "application/octet-stream",
  };
}

function fileBadge(file, removable = false, index = -1) {
  const isImage = (file.type || "").startsWith("image/");
  const remove = removable
    ? el("button", { type: "button", class: "attachment-remove", onclick: () => removePendingFile(index), title: "Remove attachment" }, "x")
    : null;
  return el("div", { class: `attachment-chip ${isImage ? "image" : ""}` },
    isImage ? el("img", { src: previewUrl(file), alt: "" }) : el("span", { class: "attachment-file" }, "FILE"),
    el("span", { class: "attachment-name" }, file.name || "attachment"),
    remove,
  );
}

function addMessage(role, text, attachments = []) {
  const node = el("div", { class: `chat-msg ${role}` },
    el("span", { class: "msg-role" }, role === "user" ? "You" : "Ray"),
    el("div", { class: "msg-text" }, text),
  );
  if (attachments.length) {
    node.append(el("div", { class: "msg-attachments" }, attachments.map((file) => fileBadge(file))));
  }
  transcript.append(node);
  transcript.scrollTop = transcript.scrollHeight;
}

function renderComposerAttachments() {
  if (!composerAttachments) return;
  composerAttachments.innerHTML = "";
  if (!pendingFiles.length) {
    composerAttachments.hidden = true;
    return;
  }
  composerAttachments.hidden = false;
  for (const [idx, file] of pendingFiles.entries()) {
    composerAttachments.append(fileBadge(file, true, idx));
  }
}

function removePendingFile(index) {
  pendingFiles.splice(index, 1);
  renderComposerAttachments();
  renderBrief();
}

function setQuickReplies(items = []) {
  quickRow.innerHTML = "";
  for (const item of items) {
    quickRow.append(el("button", {
      type: "button",
      class: "quick-chip",
      onclick: () => handleUserText(item),
    }, item));
  }
}

function extractDuration(text) {
  const lower = text.toLowerCase();
  const minuteMatch = lower.match(/(\d+(?:\.\d+)?)\s*(minutes?|mins?|m)\b/);
  if (minuteMatch) return Math.round(Number(minuteMatch[1]) * 60);
  const secondMatch = lower.match(/(\d+)\s*(seconds?|secs?|s)\b/);
  if (secondMatch) return Number(secondMatch[1]);
  if (activeQuestion === "duration_seconds") {
    const bare = lower.match(/\b(\d{1,3})\b/);
    if (bare) return Number(bare[1]);
  }
  return null;
}

function extractAspect(text) {
  const lower = text.toLowerCase();
  const ratio = lower.match(/\b(21:9|16:9|9:16|1:1|4:3|3:4)\b/);
  if (ratio) return ratio[1];
  for (const [key, value] of Object.entries(ASPECTS)) {
    if (lower.includes(key)) return value;
  }
  return "";
}

function looksLikeNone(text) {
  return /^(no|none|nothing|skip|na|n\/a)$/i.test(text.trim());
}

function extractAudience(text) {
  const lower = text.toLowerCase();
  const direct = lower.match(/\bfor\s+(women|men|brides|grooms|parents|students|founders|clients|customers|shoppers|buyers|doctors|patients|investors|teachers|kids|children|professionals|business owners|small businesses|retailers)\b/);
  if (direct) return direct[1].replace(/\b\w/g, (c) => c.toUpperCase());
  if (/\b(youtube|shorts|reels?|tiktok|instagram)\b/.test(lower)) return "Social media viewers";
  if (/\b(client|clients|sell|sales|lead|leads|ad|campaign)\b/.test(lower)) return "Prospective customers";
  return "";
}

function extractStyle(text) {
  const lower = text.toLowerCase();
  if (/\b(luxury|premium|elegant|cinematic|film|commercial|35mm|photoreal|photorealistic)\b/.test(lower)) {
    return "Cinematic and premium";
  }
  if (/\b(fast|punchy|viral|reel|shorts|tiktok|social ad|ugc)\b/.test(lower)) {
    return "Fast social ad";
  }
  if (/\b(explainer|saas|demo|walkthrough|clean|minimal|corporate)\b/.test(lower)) {
    return "Clean explainer";
  }
  return "";
}

function extractConstraints(text) {
  const lower = text.toLowerCase();
  const items = [];
  if (/\bcta|call to action|book now|shop now|buy now|contact\b/.test(lower)) items.push("Include CTA");
  if (/\bno text|without text|no captions|no overlay|no logo\b/.test(lower)) items.push("No text/logo overlays unless requested");
  if (/\buse (the )?(uploaded|reference) (images|files|photos)|reference images|uploaded images\b/.test(lower)) items.push("Use uploaded references");
  if (/\bconsistent (character|model|person|face|wardrobe|product)|same (character|model|person|face|outfit|product)\b/.test(lower)) items.push("Maintain visual consistency");
  return items.join("; ");
}

function mergeBrief(text) {
  const duration = extractDuration(text);
  if (duration != null) brief.duration_seconds = duration;
  const aspect = extractAspect(text);
  if (aspect) brief.aspect_ratio = aspect;

  if (activeQuestion === "prompt" && text.trim().length > 6) brief.prompt = text.trim();
  if (activeQuestion === "duration_seconds" && duration == null) brief.duration_seconds = Number.NaN;
  if (activeQuestion === "aspect_ratio" && !aspect) brief.aspect_ratio = text.trim();
  if (activeQuestion === "audience") brief.audience = looksLikeNone(text) ? "General audience" : text.trim();
  if (activeQuestion === "style") brief.style = looksLikeNone(text) ? "Clean cinematic commercial" : text.trim();
  if (activeQuestion === "must_haves") brief.must_haves = looksLikeNone(text) ? "No extra constraints" : text.trim();

  if (!brief.audience) {
    const audience = extractAudience(text);
    if (audience) brief.audience = audience;
  }
  if (!brief.style) {
    const style = extractStyle(text);
    if (style) brief.style = style;
  }
  if (!brief.must_haves) {
    const constraints = extractConstraints(text);
    if (constraints) brief.must_haves = constraints;
  }
  if (!brief.must_haves && activeQuestion === "prompt" && text.trim().length > 90) {
    brief.must_haves = "No extra constraints beyond the brief.";
  }

  // Let users revise key fields naturally after the brief is already formed.
  if (/duration|make it|change/i.test(text) && duration != null) brief.duration_seconds = duration;
  if (/format|aspect|youtube|short|reel|vertical|square|landscape|16:9|9:16|1:1/i.test(text) && aspect) {
    brief.aspect_ratio = aspect;
  }
}

function nextQuestion() {
  const model = currentModel();
  const maxDuration = maxDurationForModel(model);
  if (!brief.prompt) return ["prompt", "What video should I make? Give me the core idea, product, or story."];
  if (!Number.isFinite(brief.duration_seconds)) return ["duration_seconds", `What duration do you want? This hosted build currently supports 5 seconds to ${fmtDuration(maxDuration)}.`];
  if (brief.duration_seconds < 5 || brief.duration_seconds > maxDuration) {
    return ["duration_seconds", `Pick a duration between 5 seconds and ${fmtDuration(maxDuration)}.`];
  }
  if (!brief.aspect_ratio) return ["aspect_ratio", "What format should I render: YouTube 16:9, Shorts/Reels 9:16, square, or another ratio?"];
  if (!model.supportedAspects.includes(brief.aspect_ratio)) {
    return ["aspect_ratio", `This hosted build supports ${model.supportedAspects.join(", ")} right now.`];
  }
  if (!brief.audience) return ["audience", "Who is this for?"];
  if (!brief.style) return ["style", "What visual style and tone should it have?"];
  if (!brief.must_haves) return ["must_haves", "Any must-have details, exclusions, CTA, brand notes, or client constraints? Say none if not."];
  return [null, ""];
}

function currentModel() {
  return MODEL_OPTIONS[modelVariant.value] || MODEL_OPTIONS["grok-imagine-video"];
}

function modelStatus(modelId = modelVariant.value) {
  return modelAvailability[modelId] || null;
}

function maxDurationForModel(model = currentModel()) {
  return Math.min(MAX_DURATION, model.maxSceneSeconds * 12);
}

function recommendedSceneCount(duration) {
  if (!Number.isFinite(duration)) return 3;
  return Math.max(1, Math.min(12, Math.ceil(duration / currentModel().maxSceneSeconds)));
}

function titleFromPrompt(prompt) {
  const clean = prompt.replace(/\s+/g, " ").trim();
  const words = clean.split(" ").slice(0, 8).join(" ");
  return words || "Ray video";
}

function buildPrompt() {
  const parts = [
    brief.prompt,
    `Target audience: ${brief.audience}.`,
    `Visual style and tone: ${brief.style}.`,
    `Must-haves and constraints: ${brief.must_haves}.`,
    `Deliverable: ${fmtDuration(brief.duration_seconds)} video in ${brief.aspect_ratio}.`,
  ];
  if (referenceFiles.length) {
    parts.push("Attached references: use the files attached in chat as the visual source of truth.");
  }
  return parts.join("\n");
}

function renderBrief() {
  const model = currentModel();
  const status = modelStatus();
  updateModelHelp();
  const rows = [
    ["Video", brief.prompt || "Needed"],
    ["Duration", Number.isFinite(brief.duration_seconds) ? fmtDuration(brief.duration_seconds) : "Needed"],
    ["Format", brief.aspect_ratio || "Needed"],
    ["Audience", brief.audience || "Needed"],
    ["Style", brief.style || "Needed"],
    ["Constraints", brief.must_haves || "Needed"],
    ["Scenes", `${recommendedSceneCount(brief.duration_seconds)} planned`],
  ];
  if (briefList) {
    briefList.innerHTML = "";
    for (const [k, v] of rows) {
      briefList.append(el("dt", {}, k), el("dd", { class: v === "Needed" ? "missing" : "" }, v));
    }
  }
  const [missing] = nextQuestion();
  const modelBlocked = status && status.available === false;
  ready = !missing && !modelBlocked;
  if (readyEl) {
    readyEl.textContent = !missing ? (modelBlocked ? "Model key needed" : "Ready") : "Draft";
    readyEl.className = !missing && !modelBlocked ? "meta ready" : "meta";
  }
  if (submit) submit.disabled = !ready;
}

function askNext() {
  renderBrief();
  const [key, question] = nextQuestion();
  activeQuestion = key || "ready";
  if (!key) {
    const status = modelStatus();
    if (status && status.available === false) {
      addMessage("assistant", `${currentModel().label} is selected, but ${status.requires_any_env.join(" or ")} is not configured on this deployment.`);
      setQuickReplies(["Use Grok Imagine", "Use Kling 3", "Use Veo 3.1"]);
      return;
    }
    addMessage("assistant", `I have enough to create the OpenMontage plan: ${fmtDuration(brief.duration_seconds)}, ${brief.aspect_ratio}, ${recommendedSceneCount(brief.duration_seconds)} scenes. I will choose the best available video path during planning. This will not spend video-generation credits.`);
    setQuickReplies(["Create plan", "Change duration to 60s", "Make it 9:16"]);
    return;
  }
  addMessage("assistant", question);
  if (key === "duration_seconds") {
    setQuickReplies(maxDurationForModel() < 120 ? ["15s", "30s", "60s", "90s"] : ["15s", "30s", "60s", "2 minutes"]);
  }
  else if (key === "aspect_ratio") {
    const replies = currentModel().supportedAspects.includes("1:1")
      ? ["YouTube 16:9", "Shorts 9:16", "Square 1:1"]
      : ["YouTube 16:9", "Shorts 9:16"];
    setQuickReplies(replies);
  }
  else if (key === "style") setQuickReplies(["Cinematic and premium", "Fast social ad", "Clean explainer"]);
  else if (key === "must_haves") setQuickReplies(["None", "Include a CTA", "Keep the same product/person"]);
  else setQuickReplies([]);
}

async function apiJSON(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `${res.status} ${url}`);
  return data;
}

async function uploadFiles(projectId, files) {
  if (!files.length) return [];
  const fd = new FormData();
  for (const file of files) fd.append("files", file);
  const res = await fetch(`/api/project/${encodeURIComponent(projectId)}/uploads`, { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Upload failed");
  return data.files || [];
}

async function createJob() {
  if (!ready || submit?.disabled) return;
  if (pendingFiles.length) {
    const files = [...pendingFiles];
    pendingFiles = [];
    renderComposerAttachments();
    addMessage("user", "Attached reference files.", files);
    referenceFiles.push(...files);
    chatTurns.push({ role: "user", text: "Attached reference files.", attachments: files.map(fileMeta) });
    renderBrief();
  }
  if (submit) submit.disabled = true;
  statusEl.textContent = "Creating safe plan...";
  const files = [...referenceFiles];
  const payload = {
    title: titleFromPrompt(brief.prompt),
    prompt: buildPrompt(),
    aspect_ratio: brief.aspect_ratio,
    duration_seconds: brief.duration_seconds,
    scene_count: recommendedSceneCount(brief.duration_seconds),
    video_model: modelVariant.value,
    chat_messages: chatTurns,
  };
  try {
    const job = await apiJSON("/api/jobs", { method: "POST", body: JSON.stringify(payload) });
    if (files.length) {
      statusEl.textContent = "Uploading references...";
      const uploaded = await uploadFiles(job.project_id, files);
      await apiJSON(`/api/jobs/${encodeURIComponent(job.project_id)}/references`, {
        method: "POST",
        body: JSON.stringify({ reference_assets: uploaded }),
      });
    }
    await apiJSON(`/api/jobs/${encodeURIComponent(job.project_id)}/plan`, { method: "POST", body: "{}" });
    statusEl.textContent = "Plan started. No video credits spent.";
    location.href = job.url;
  } catch (err) {
    statusEl.textContent = err.message;
    if (submit) submit.disabled = false;
  }
}

function handleUserText(text, files = []) {
  const rawValue = text.trim();
  const turnFiles = [...files];
  if (!rawValue && !turnFiles.length) return;
  const value = rawValue || "Attached reference files.";
  addMessage("user", value, turnFiles);
  if (turnFiles.length) {
    referenceFiles.push(...turnFiles);
    chatTurns.push({ role: "user", text: value, attachments: turnFiles.map(fileMeta) });
  } else {
    chatTurns.push({ role: "user", text: value, attachments: [] });
  }
  let modelCommand = true;
  if (/use\s+kling\s*3|use\s+kling\b/i.test(value)) modelVariant.value = "kling-v3";
  else if (/use\s+veo\s+3\.?1\s+fast/i.test(value)) modelVariant.value = "veo3.1-fast";
  else if (/use\s+veo\s+3\.?1\b/i.test(value)) modelVariant.value = "veo3.1";
  else if (/use\s+grok/i.test(value)) modelVariant.value = "grok-imagine-video";
  else if (/use\s+seedance\s+standard/i.test(value)) modelVariant.value = "seedance-standard";
  else if (/use\s+seedance\s+fast/i.test(value)) modelVariant.value = "seedance-fast";
  else modelCommand = false;
  if (!modelCommand && rawValue) mergeBrief(rawValue);
  if (ready && /^(create\s+plan|plan|generate|start|go)$/i.test(value)) {
    createJob();
    return;
  }
  askNext();
}

async function renderConfig() {
  const cfg = await getJSON("/api/config");
  modelAvailability = Object.fromEntries((cfg.video_models || []).map((item) => [item.id, item]));
  const pills = document.getElementById("configPills");
  pills.innerHTML = "";
  pills.append(
    el("span", { class: `chip ${cfg.llm_configured ? "" : "warn"}` }, cfg.llm_configured ? "LLM READY" : "LLM KEY NEEDED"),
    el("span", { class: `chip ${cfg.fal_configured ? "" : "warn"}` }, cfg.fal_configured ? "FAL READY" : "FAL MISSING"),
    el("span", { class: `chip ${cfg.grok_configured ? "" : "warn"}` }, cfg.grok_configured ? "GROK READY" : "GROK MISSING"),
    el("span", { class: `chip ${cfg.r2_configured ? "" : "warn"}` }, cfg.r2_configured ? "R2 READY" : "R2 MISSING"),
    el("span", { class: "chip" }, cfg.auth_provider.toUpperCase()),
  );
  for (const option of modelVariant.options) {
    const status = modelAvailability[option.value];
    const model = MODEL_OPTIONS[option.value];
    if (status && model) {
      option.textContent = `${model.label}${status.available ? "" : " — key needed"}`;
    }
  }
  renderBrief();
}

function updateModelHelp() {
  if (!modelHelp) return;
  const model = currentModel();
  const status = modelStatus();
  const availability = status && status.available === false
    ? ` Requires ${status.requires_any_env.join(" or ")}.`
    : "";
  modelHelp.textContent = `${model.note} Clips up to ${model.maxSceneSeconds}s. Supports ${model.supportedAspects.join(", ")}.${availability}`;
}

form?.addEventListener("submit", (event) => {
  event.preventDefault();
  const files = [...pendingFiles];
  pendingFiles = [];
  renderComposerAttachments();
  handleUserText(input.value, files);
  input.value = "";
  input.focus();
});
submit?.addEventListener("click", createJob);
modelVariant?.addEventListener("change", () => {
  renderBrief();
});
filesInput?.addEventListener("change", () => {
  pendingFiles.push(...filesInput.files);
  filesInput.value = "";
  renderComposerAttachments();
  renderBrief();
});

addMessage("assistant", "Tell me the full video brief in one message. I will extract duration, format, style, audience, constraints, and references before asking only for what is missing.");
setQuickReplies(["15s vertical premium saree ad", "60s client explainer in 16:9", "30s YouTube product teaser"]);
renderBrief();
renderConfig().catch(() => {});
