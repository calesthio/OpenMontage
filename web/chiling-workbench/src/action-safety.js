export function normalizeProgress(value) {
  const progress = Number.parseFloat(value);
  if (!Number.isFinite(progress)) return 0;
  return Math.min(100, Math.max(0, progress));
}

export function normalizeTaskRoute(route, status = "") {
  if (route === "delivery" || route === "generating") return route;
  return status === "completed" ? "delivery" : "generating";
}

export function normalizeDeliveryUrl(value, baseUrl = globalThis.location?.href || "http://localhost/") {
  const rawUrl = String(value || "").trim();
  if (!rawUrl) return "";

  try {
    const base = new URL(baseUrl, "http://localhost/");
    const url = new URL(rawUrl, base);
    const hasExplicitScheme = /^[a-z][a-z\d+.-]*:/i.test(rawUrl);

    if (url.protocol === "blob:") {
      return url.origin === base.origin ? url.href : "";
    }
    if (url.protocol !== "http:" && url.protocol !== "https:") return "";
    if (!hasExplicitScheme && url.origin !== base.origin) return "";

    return url.href;
  } catch {
    return "";
  }
}
