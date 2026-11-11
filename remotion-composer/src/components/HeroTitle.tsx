import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { splitGraphemes } from "../lib/graphemes";

type HeroTitleProps = {
  title: string;
  subtitle?: string;
  /** Color of the leading accent characters and the underline. */
  accentColor?: string;
  /** Color of the remaining title characters. Pass the theme's textColor. */
  textColor?: string;
  /** Subtitle color. */
  subtitleColor?: string;
  /**
   * Scrim painted behind the title so it separates from whatever is underneath.
   * Defaults to a dark wash; a light theme must pass a light one, otherwise the
   * scrim darkens the backdrop and cancels out the theme's dark text.
   */
  scrimBackground?: string;
};

const DEFAULT_SCRIM =
  "radial-gradient(ellipse at center, rgba(15,23,42,0.35) 0%, rgba(15,23,42,0.55) 100%)";

export const HeroTitle: React.FC<HeroTitleProps> = ({
  title,
  subtitle,
  accentColor = "#22D3EE",
  textColor = "#F8FAFC",
  subtitleColor = "#A78BFA",
  scrimBackground = DEFAULT_SCRIM,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Staggered letter-by-letter spring. Split by grapheme: a UTF-16 split
  // breaks emoji into U+FFFD boxes and strips Thai vowels/tone marks.
  const titleChars = splitGraphemes(title);
  // Characters are grouped by word so a title wider than the frame (9:16
  // shorts) wraps between words, never inside one. `start` keeps each
  // character's index in the full title, so stagger and accent are unchanged.
  const titleWords = title.split(" ").reduce<{ chars: string[]; start: number }[]>(
    (words, word) => {
      const last = words[words.length - 1];
      const start = last ? last.start + last.chars.length + 1 : 0;
      return [...words, { chars: splitGraphemes(word), start }];
    },
    [],
  );

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: scrimBackground,
      }}
    >
      <div style={{ textAlign: "center", maxWidth: "85%" }}>
        {/* Main title with per-character spring */}
        <div
          style={{
            fontSize: 72,
            fontWeight: 800,
            fontFamily: "Space Grotesk, Inter, system-ui, sans-serif",
            lineHeight: 1.2,
            display: "flex",
            justifyContent: "center",
            flexWrap: "wrap",
            rowGap: 0,
            columnGap: "0.3em", // the space between words
          }}
        >
          {titleWords.map((word, w) => (
            <span key={w} style={{ display: "inline-flex", whiteSpace: "nowrap" }}>
              {word.chars.map((char, j) => {
                const i = word.start + j;
                const delay = i * 1.2;
                const charSpring = spring({
                  frame: frame - delay,
                  fps,
                  config: { damping: 12, stiffness: 150 },
                });

                return (
                  <span
                    key={i}
                    style={{
                      display: "inline-block",
                      opacity: charSpring,
                      transform: `translateY(${interpolate(charSpring, [0, 1], [30, 0])}px)`,
                      // Accent the whole first word. A fixed character
                      // count switched colour mid-word: "Your rai|nbow".
                      color: w === 0 ? accentColor : textColor,
                    }}
                  >
                    {char}
                  </span>
                );
              })}
            </span>
          ))}
        </div>

        {/* Subtitle */}
        {subtitle && (
          <div
            style={{
              marginTop: 20,
              opacity: spring({
                frame: frame - titleChars.length * 1.2 - 5,
                fps,
                config: { damping: 20 },
              }),
              fontSize: 28,
              fontWeight: 400,
              color: subtitleColor,
              fontFamily: "Space Grotesk, Inter, system-ui, sans-serif",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}
          >
            {subtitle}
          </div>
        )}

        {/* Animated underline */}
        <div
          style={{
            margin: "24px auto 0",
            height: 3,
            backgroundColor: accentColor,
            borderRadius: 2,
            width: interpolate(
              spring({
                frame: frame - 15,
                fps,
                config: { damping: 15, stiffness: 60 },
              }),
              [0, 1],
              [0, 400]
            ),
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
