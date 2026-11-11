// Split a callout's `text` into paragraphs and bullet items.
//
// SCENE_TYPES.md describes `callout` as a "boxed message with bullets", but
// CalloutBox rendered `text` as one run: newlines collapsed and "- item"
// lines ran together (seen on the 2026-11-11 audit render).

export type CalloutLine = { kind: "paragraph" | "bullet"; text: string };

const BULLET = /^\s*(?:[-*•–])\s+(.*)$/;

export function parseCalloutText(text: string): CalloutLine[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => {
      const match = BULLET.exec(line);
      return match
        ? { kind: "bullet" as const, text: match[1].trim() }
        : { kind: "paragraph" as const, text: line };
    });
}
