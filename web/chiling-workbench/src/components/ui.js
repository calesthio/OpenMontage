import { escapeHtml } from "../format.js";

function dataAttributeName(name) {
  const kebabName = String(name)
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .toLowerCase();

  if (!/^[a-z0-9-]+$/.test(kebabName) || /^on(?:-|$)/.test(kebabName)) {
    return "";
  }

  return kebabName;
}

export function button(
  label,
  {
    variant = "secondary",
    type = "button",
    className = "",
    disabled = false,
    ariaLabel = "",
    data = {},
  } = {},
) {
  const classes = ["button"];
  if (variant) {
    classes.push(`button--${variant}`);
  }
  if (className) {
    classes.push(className);
  }

  const attributeParts = [
    `class="${escapeHtml(classes.join(" "))}"`,
    `type="${escapeHtml(type)}"`,
  ];

  if (disabled) {
    attributeParts.push("disabled");
  }
  if (ariaLabel) {
    attributeParts.push(`aria-label="${escapeHtml(ariaLabel)}"`);
  }

  Object.entries(data).forEach(([name, value]) => {
    const safeName = dataAttributeName(name);
    if (!safeName) return;

    attributeParts.push(`data-${safeName}="${escapeHtml(value)}"`);
  });

  return `<button ${attributeParts.join(" ")}>${escapeHtml(label)}</button>`;
}

export function panel(bodyHtml, { className = "", title = "" } = {}) {
  const titleMarkup = title ? `<h2>${escapeHtml(title)}</h2>` : "";
  return `
    <section class="panel ${escapeHtml(className)}">
      ${titleMarkup}
      ${bodyHtml}
    </section>
  `;
}

export function phonePreview(image, label, modifier = "") {
  return `
    <div class="phone ${escapeHtml(modifier)}">
      <div class="phone__screen">
        <img src="${escapeHtml(image)}" alt="${escapeHtml(label)}" />
        <span class="phone__label">${escapeHtml(label)}</span>
      </div>
      <div class="phone__progress"><span></span></div>
    </div>
  `;
}

export function metric(label, value, helper) {
  return `
    <div class="metric-card">
      <span class="metric-card__label">${escapeHtml(label)}</span>
      <strong class="metric-card__value">${escapeHtml(value)}</strong>
      <span class="metric-card__helper">${escapeHtml(helper)}</span>
    </div>
  `;
}

export function pill(label, className = "") {
  return `<span class="pill ${escapeHtml(className)}">${escapeHtml(label)}</span>`;
}
