// Right-to-left helpers (Arabic, Hebrew, Persian, Urdu).
const RTL_CHARS = /[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]/;

export function isRtlText(text: string): boolean {
  return RTL_CHARS.test(text);
}

// Units for staggered per-unit animation. Arabic letters join into words,
// so splitting per character would break the joining: split per word instead.
export function splitAnimationUnits(text: string): string[] {
  if (!isRtlText(text)) return text.split("");
  return text.split(/(\s+)/).filter((part) => part.length > 0);
}
