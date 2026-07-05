export function clampNumber(number, min, max) {
  return Math.min(Math.max(Number(number) || min, min), max);
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function lineBreaks(value) {
  return escapeHtml(value).replaceAll("\n", "<br />");
}

export function normalizeSubtitleText(text) {
  return String(text || "")
    .split("\n")
    .map((line) => line.trim().replace(/[，。！？、,.!?]+$/u, ""))
    .filter(Boolean)
    .join("\n");
}

export function formatRelativeTime(timestamp, now = Date.now()) {
  if (!timestamp) return "刚刚";
  const seconds = Math.max(0, Math.round((now - Number(timestamp)) / 1000));
  if (seconds < 60) return "刚刚";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}分钟前`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}小时前`;
  const days = Math.round(hours / 24);
  return `${days}天前`;
}
