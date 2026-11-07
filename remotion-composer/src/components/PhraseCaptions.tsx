// Phrase captions driven by real word timings (e.g. Qwen3 Forced Aligner).
//
// Promoted from the bespoke `projects/ai-capex-to-korea-mortgage/remotion/Captions.tsx`
// with its behaviour unchanged:
//   - words are packed into short phrase cues (<= maxChars visible characters,
//     a sentence end or a `pageBreakAfter` closes the cue)
//   - the whole cue is on screen for its lifetime, box included — silence
//     between words inside a cue never hides it
//   - a word turns active at its real start time and stays active; words not
//     yet spoken are dim
//   - each cue is held until the next one starts, for at most `holdSeconds`
//     past its last word
//
// Selected with `edit_decisions.subtitles.style = "karaoke"` (see
// `isPhraseCaptionStyle`). Every other style keeps using CaptionOverlay.
import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { WordCaption } from "./CaptionOverlay";

export type PhraseCaptionPosition = "bottom-center" | "top-center" | "center";

export interface PhraseCue {
  startMs: number;
  endMs: number;
  words: WordCaption[];
}

export const PHRASE_CAPTION_STYLES = ["karaoke"] as const;

export const isPhraseCaptionStyle = (style: unknown): boolean =>
  typeof style === "string" &&
  (PHRASE_CAPTION_STYLES as readonly string[]).includes(style.trim().toLowerCase());

const SENTENCE_END = /[.?!]$/;

export function buildPhraseCues(
  words: WordCaption[],
  { maxChars = 26, holdMs = 600 }: { maxChars?: number; holdMs?: number } = {},
): PhraseCue[] {
  const cues: PhraseCue[] = [];
  let cur: WordCaption[] = [];
  let chars = 0;
  const flush = () => {
    if (!cur.length) return;
    cues.push({ startMs: cur[0].startMs, endMs: cur[cur.length - 1].endMs, words: cur });
    cur = [];
    chars = 0;
  };
  for (const w of words) {
    const len = w.word.length;
    if (chars + len > maxChars && cur.length) flush();
    cur.push(w);
    chars += len + 1;
    if (SENTENCE_END.test(w.word) || w.pageBreakAfter) flush();
  }
  flush();
  // Hold each cue until the next begins (max +holdMs) so captions never flash.
  for (let i = 0; i < cues.length; i++) {
    const next = cues[i + 1];
    const hold = cues[i].endMs + holdMs;
    cues[i].endMs = next ? Math.min(hold, next.startMs) : hold;
  }
  return cues;
}

export interface PhraseCaptionsProps {
  words: WordCaption[];
  maxChars?: number;
  holdSeconds?: number;
  fontFamily?: string;
  fontSize?: number;
  fontWeight?: number;
  activeColor?: string;
  dimColor?: string;
  backgroundColor?: string;
  position?: PhraseCaptionPosition;
  // " " for space-delimited scripts (Korean eojeol included); "" for CJK without spaces.
  wordSeparator?: string;
}

/** Map `edit_decisions.subtitles` (snake_case) onto PhraseCaptions props. */
export function phraseCaptionPropsFromSubtitles(subtitles: unknown): Partial<PhraseCaptionsProps> {
  if (!subtitles || typeof subtitles !== "object") return {};
  const s = subtitles as Record<string, unknown>;
  const out: Partial<PhraseCaptionsProps> = {};
  if (typeof s.font === "string") out.fontFamily = s.font;
  if (typeof s.font_size === "number") out.fontSize = s.font_size;
  if (typeof s.color === "string") out.activeColor = s.color;
  if (typeof s.dim_color === "string") out.dimColor = s.dim_color;
  if (typeof s.background === "string") out.backgroundColor = s.background;
  if (s.position === "bottom-center" || s.position === "top-center" || s.position === "center") {
    out.position = s.position;
  }
  if (typeof s.max_chars_per_cue === "number") out.maxChars = s.max_chars_per_cue;
  if (typeof s.hold_seconds === "number") out.holdSeconds = s.hold_seconds;
  return out;
}

export const PhraseCaptions: React.FC<PhraseCaptionsProps> = ({
  words,
  maxChars = 26,
  holdSeconds = 0.6,
  fontFamily = "'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif",
  fontSize = 40,
  fontWeight = 600,
  activeColor = "#E7ECF3",
  dimColor = "#8592A6",
  backgroundColor = "rgba(11,18,32,0.72)",
  position = "bottom-center",
  wordSeparator = " ",
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const tMs = (frame / fps) * 1000;
  const cues = useMemo(
    () => buildPhraseCues(words, { maxChars, holdMs: holdSeconds * 1000 }),
    [words, maxChars, holdSeconds],
  );
  const cue = cues.find((c) => tMs >= c.startMs && tMs < c.endMs);
  if (!cue) return null;

  // Reference layout: box top at y=930 on a 1080p frame.
  const boxHeight = fontSize * 1.3 + 20;
  const top =
    position === "top-center"
      ? Math.round(height * 0.08)
      : position === "center"
        ? Math.round((height - boxHeight) / 2)
        : Math.round(height * (930 / 1080));

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        width,
        top,
        display: "flex",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          padding: "10px 28px",
          borderRadius: 10,
          backgroundColor,
          fontFamily,
          fontWeight,
          fontSize,
          lineHeight: 1.3,
          letterSpacing: -0.2,
          whiteSpace: "nowrap",
        }}
      >
        {cue.words.map((w, i) => (
          <span key={i} style={{ color: tMs >= w.startMs ? activeColor : dimColor }}>
            {w.word}
            {i < cue.words.length - 1 ? wordSeparator : ""}
          </span>
        ))}
      </div>
    </div>
  );
};
