import React, { Fragment } from "react";
import {
  AbsoluteFill,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// Word-level caption for TikTok-style highlight display
export interface WordCaption {
  word: string;
  startMs: number;
  endMs: number;
  // Force a page break after this word (e.g. sentence or scene boundaries).
  // Useful for CJK captions where pages should align with clause boundaries.
  pageBreakAfter?: boolean;
}

type CaptionOverlayProps = {
  words: WordCaption[];
  // How many words to show at once in a "page"
  wordsPerPage?: number;
  fontSize?: number;
  color?: string;
  highlightColor?: string;
  backgroundColor?: string;
  fontFamily?: string;
  // Separator rendered between words. Left unset, it is decided per adjacent
  // pair by `separatorBetween`, which is what CJK captions need — a fixed
  // string cannot be right for both sides of a script boundary. Set it to
  // force one separator everywhere.
  wordSeparator?: string;
  // Base text direction. "auto" (default) picks RTL when most words of the
  // captions are Arabic/Hebrew/Persian/Urdu. Each word is an
  // inline-block, which the bidi algorithm treats as a neutral object, so
  // without an explicit direction RTL words are laid out left-to-right and
  // the sentence reads backwards.
  direction?: "ltr" | "rtl" | "auto";
};

const RTL_CHAR = /[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]/;
const LTR_CHAR = /[A-Za-z\u00C0-\u024F\u0370-\u03FF\u0400-\u04FF]/;

function detectDirection(words: WordCaption[]): "ltr" | "rtl" {
  // Count words, not first letter: Arabic captions often open with a Latin
  // brand name ("OpenMontage يحوّل ...") and must still read right-to-left.
  let rtl = 0;
  let ltr = 0;
  for (const w of words) {
    if (RTL_CHAR.test(w.word)) rtl++;
    else if (LTR_CHAR.test(w.word)) ltr++;
  }
  return rtl > ltr ? "rtl" : "ltr";
}

interface CaptionPage {
  words: WordCaption[];
  startMs: number;
  endMs: number;
}

// Scripts written without inter-word spaces: Han ideographs (including the
// Extension blocks that carry rarer Traditional forms), kana, Hangul, and the
// CJK punctuation / fullwidth blocks — the latter matter because a closing
// mark like "。" must stay glued to the word it follows.
const CJK_CHARACTER =
  /^(?:[\u3000-\u303F\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\uF900-\uFAFF\uFF00-\uFFEF]|[\u{20000}-\u{2FA1F}])$/u;

// Array.from splits by code point, so an Extension B ideograph is compared as
// one character rather than as half of a surrogate pair.
const firstCharacter = (text: string): string => Array.from(text)[0] ?? "";
const lastCharacter = (text: string): string => {
  const characters = Array.from(text);
  return characters[characters.length - 1] ?? "";
};

/**
 * Separator to render between two caption tokens when none was configured.
 *
 * The space is dropped only when *both* sides are CJK, so a script boundary
 * keeps the space that separates the two writing systems — "使用 OpenMontage
 * 製作的影片" reads correctly, and space-delimited text is unchanged.
 */
export const separatorBetween = (left: string, right: string): string =>
  CJK_CHARACTER.test(lastCharacter(left)) && CJK_CHARACTER.test(firstCharacter(right))
    ? ""
    : " ";

function buildPages(words: WordCaption[], wordsPerPage: number): CaptionPage[] {
  const pages: CaptionPage[] = [];
  let pageWords: WordCaption[] = [];
  const flush = () => {
    if (pageWords.length === 0) return;
    pages.push({
      words: pageWords,
      startMs: pageWords[0].startMs,
      endMs: pageWords[pageWords.length - 1].endMs,
    });
    pageWords = [];
  };
  for (const w of words) {
    pageWords.push(w);
    if (pageWords.length >= wordsPerPage || w.pageBreakAfter) flush();
  }
  flush();
  return pages;
}

const PageRenderer: React.FC<{
  page: CaptionPage;
  fontSize: number;
  color: string;
  highlightColor: string;
  backgroundColor: string;
  fontFamily: string;
  wordSeparator?: string;
  direction: "ltr" | "rtl";
}> = ({ page, fontSize, color, highlightColor, backgroundColor, fontFamily, wordSeparator, direction }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const currentMs = page.startMs + (frame / fps) * 1000;

  // Spring entrance
  const entrance = spring({
    frame,
    fps,
    config: { damping: 18, stiffness: 120 },
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 80,
      }}
    >
      <div
        dir={direction}
        style={{
          direction,
          opacity: entrance,
          transform: `translateY(${interpolate(entrance, [0, 1], [20, 0])}px)`,
          backgroundColor,
          borderRadius: 12,
          padding: "14px 28px",
          maxWidth: "80%",
          textAlign: "center",
        }}
      >
        <span
          style={{
            fontSize,
            fontWeight: 700,
            fontFamily,
            lineHeight: 1.4,
            whiteSpace: "pre-wrap",
          }}
        >
          {page.words.map((w, i) => {
            const isActive = w.startMs <= currentMs && w.endMs > currentMs;
            const isPast = w.endMs <= currentMs;
            const next = page.words[i + 1];
            // Computed here rather than inline so no JSX line break can
            // reintroduce whitespace a CJK caption must not have.
            const separator = next
              ? wordSeparator ?? separatorBetween(w.word, next.word)
              : "";
            return (
              <Fragment key={`${w.startMs}-${i}`}>
                <span
                  style={{
                    // Keep each word unbroken so lines wrap only at word
                    // boundaries. For space-delimited text this matches the
                    // previous behavior; for CJK it prevents mid-word breaks.
                    display: "inline-block",
                    whiteSpace: "nowrap",
                    color: isActive ? highlightColor : isPast ? color : `${color}99`,
                    transition: "none", // CSS transitions forbidden in Remotion
                    textShadow: isActive
                      ? `0 0 20px ${highlightColor}66, 0 2px 4px rgba(0,0,0,0.5)`
                      : "0 2px 4px rgba(0,0,0,0.5)",
                  }}
                >
                  {w.word}
                </span>
                {separator}
              </Fragment>
            );
          })}
        </span>
      </div>
    </AbsoluteFill>
  );
};

export const CaptionOverlay: React.FC<CaptionOverlayProps> = ({
  words,
  wordsPerPage = 6,
  fontSize = 42,
  color = "#F8FAFC",
  highlightColor = "#22D3EE",
  backgroundColor = "rgba(15, 23, 42, 0.75)",
  fontFamily = "Space Grotesk, Inter, system-ui, sans-serif",
  wordSeparator,
  direction = "auto",
}) => {
  const { fps } = useVideoConfig();
  const pages = buildPages(words, wordsPerPage);
  const resolvedDirection =
    direction === "auto" ? detectDirection(words) : direction;

  return (
    <AbsoluteFill>
      {pages.map((page, i) => {
        const fromFrame = Math.round((page.startMs / 1000) * fps);
        const nextStart = pages[i + 1]?.startMs ?? page.endMs + 500;
        const duration = Math.max(
          1,
          Math.round(((nextStart - page.startMs) / 1000) * fps)
        );

        return (
          <Sequence key={i} from={fromFrame} durationInFrames={duration}>
            <PageRenderer
              page={page}
              fontSize={fontSize}
              color={color}
              highlightColor={highlightColor}
              backgroundColor={backgroundColor}
              fontFamily={fontFamily}
              wordSeparator={wordSeparator}
              direction={resolvedDirection}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
