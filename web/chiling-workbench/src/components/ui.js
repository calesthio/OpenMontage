import { escapeHtml } from "../format.js";

export function button(label, { variant = "secondary", attrs = "" } = {}) {
  const modifier = variant ? ` button--${escapeHtml(variant)}` : "";
  return `<button class="button${modifier}" ${attrs}>${escapeHtml(label)}</button>`;
}

export function panel(content, { className = "", title = "" } = {}) {
  const titleMarkup = title ? `<h2>${escapeHtml(title)}</h2>` : "";
  return `
    <section class="panel ${escapeHtml(className)}">
      ${titleMarkup}
      ${content}
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
