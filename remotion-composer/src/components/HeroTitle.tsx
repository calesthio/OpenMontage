import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

type HeroTitleProps = {
  title: string;
  subtitle?: string;
  /** Color of the leading accent characters and the underline. */
  accentColor?: string;
  /** Color of the remaining title characters. Pass the theme's textColor. */
  textColor?: string;
  /** Subtitle color. */
  subtitleColor?: string;
  /** Title size in px. Vertical 1080x1920 deliverables need a smaller value
   *  than the 1920-wide default, otherwise long titles wrap to four lines. */
  fontSize?: number;
  /** How many leading words take the accent colour. Counted in words, not
   *  characters, so the accent never stops in the middle of one. */
  accentWords?: number;
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
  fontSize = 72,
  accentWords = 1,
  scrimBackground = DEFAULT_SCRIM,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Staggered letter-by-letter spring, grouped by word. Each group is one
  // word plus the space that follows it, so the flex container can only wrap
  // between words. `offset` is the index of the group's first character in the
  // whole title, which keeps the stagger timing identical to a flat char list.
  const words: { chars: string[]; offset: number }[] = [];
  let offset = 0;
  for (const token of title.split(/(\s+)/)) {
    if (token === "") continue;
    const isSpace = /^\s+$/.test(token);
    if (isSpace && words.length > 0) {
      // Fold the separator into the previous word so it cannot start a line.
      words[words.length - 1].chars.push(...token.split(""));
    } else {
      words.push({ chars: token.split(""), offset });
    }
    offset += token.length;
  }
  const titleCharCount = title.length;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: scrimBackground,
      }}
    >
      <div style={{ textAlign: "center", maxWidth: "85%" }}>
        {/* Main title with per-character spring.
            Characters are grouped into word-level spans: the flex container
            wraps at flex-item boundaries, so one span per character let a line
            break fall inside a word ("Reconcil / iation"). One span per word
            keeps the per-character spring and wraps only at spaces. */}
        <div
          style={{
            fontSize,
            fontWeight: 800,
            fontFamily: "Space Grotesk, Inter, system-ui, sans-serif",
            lineHeight: 1.2,
            display: "flex",
            justifyContent: "center",
            flexWrap: "wrap",
            gap: 0,
          }}
        >
          {words.map((word, wordIndex) => (
            <span
              key={wordIndex}
              style={{
                display: "inline-block",
                whiteSpace: "pre",
                // Accent runs to a word boundary, never mid-word.
                color: wordIndex < accentWords ? accentColor : textColor,
              }}
            >
              {word.chars.map((char, charIndex) => {
                const delay = (word.offset + charIndex) * 1.2;
                const charSpring = spring({
                  frame: frame - delay,
                  fps,
                  config: { damping: 12, stiffness: 150 },
                });

                return (
                  <span
                    key={charIndex}
                    style={{
                      display: "inline-block",
                      opacity: charSpring,
                      transform: `translateY(${interpolate(charSpring, [0, 1], [30, 0])}px)`,
                      whiteSpace: char === " " ? "pre" : undefined,
                      minWidth: char === " " ? "0.3em" : undefined,
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
                frame: frame - titleCharCount * 1.2 - 5,
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
