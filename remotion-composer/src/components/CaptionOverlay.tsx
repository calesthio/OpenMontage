import React from "react";
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
  // Separator rendered between words. Space-delimited languages want the
  // default " "; CJK languages (no inter-word spacing) should pass "".
  wordSeparator?: string;
  // Gap between the caption block and the bottom of the frame, in px.
  // Vertical deliverables need a much larger one: TikTok, Reels and Shorts all
  // paint their own UI over roughly the bottom 12% of the frame, so a caption
  // sitting 80px up is covered on every one of them.
  bottomOffset?: number;
};

interface CaptionPage {
  words: WordCaption[];
  startMs: number;
  endMs: number;
}

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
  bottomOffset: number;
  color: string;
  highlightColor: string;
  backgroundColor: string;
  fontFamily: string;
  wordSeparator: string;
}> = ({ page, fontSize, bottomOffset, color, highlightColor, backgroundColor, fontFamily, wordSeparator }) => {
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
        paddingBottom: bottomOffset,
      }}
    >
      <div
        style={{
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
            return (
              <React.Fragment key={`${w.startMs}-${i}`}>
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
              {/* The separator lives outside the inline-block: a trailing space
                  inside an inline-block collapses, which ran words together. */}
              {i < page.words.length - 1 ? wordSeparator : ""}
              </React.Fragment>
            );
          })}
        </span>
      </div>
    </AbsoluteFill>
  );
};

export const CaptionOverlay: React.FC<CaptionOverlayProps> = ({
  words,
  wordsPerPage,
  fontSize,
  bottomOffset,
  color = "#F8FAFC",
  highlightColor = "#22D3EE",
  backgroundColor = "rgba(15, 23, 42, 0.75)",
  fontFamily = "Space Grotesk, Inter, system-ui, sans-serif",
  wordSeparator = " ",
}) => {
  const { fps, width, height } = useVideoConfig();

  // Vertical frames are read on a phone held at arm's length and the player
  // chrome eats the bottom of the frame, so the landscape defaults are wrong
  // there in three different ways. Scale them off the frame instead of making
  // every caller remember to pass three overrides.
  const isVertical = height > width;
  const resolvedFontSize = fontSize ?? (isVertical ? 60 : 42);
  const resolvedWordsPerPage = wordsPerPage ?? (isVertical ? 4 : 6);
  const resolvedBottomOffset = bottomOffset ?? Math.round(height * (isVertical ? 0.17 : 0.07));

  const pages = buildPages(words, resolvedWordsPerPage);

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
              fontSize={resolvedFontSize}
              bottomOffset={resolvedBottomOffset}
              color={color}
              highlightColor={highlightColor}
              backgroundColor={backgroundColor}
              fontFamily={fontFamily}
              wordSeparator={wordSeparator}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
