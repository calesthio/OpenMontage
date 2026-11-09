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
  /** Font family. Pass the theme's heading font; falls back to Space Grotesk. */
  fontFamily?: string;
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
  fontFamily = "Space Grotesk, Inter, system-ui, sans-serif",
  scrimBackground = DEFAULT_SCRIM,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Staggered letter-by-letter spring. Words carry the global character index
  // so the stagger timing is identical to the previous per-character layout.
  const titleWords = (() => {
    let cursor = 0;
    return title.split(" ").map((word) => {
      const entry = { word, start: cursor };
      cursor += word.length + 1; // + the space that was consumed by the split
      return entry;
    });
  })();
  // Accent the first word. This used to be a hardcoded `i < 8`, which cuts
  // mid-word for any first word that is not exactly eight characters long.
  const firstSpace = title.indexOf(" ");
  const accentChars = firstSpace === -1 ? title.length : firstSpace;

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
            fontFamily,
            lineHeight: 1.2,
            display: "flex",
            justifyContent: "center",
            flexWrap: "wrap",
            gap: 0,
          }}
        >
          {titleWords.map(({ word, start }, wi) => (
            // One flex item per word: the container wraps between items, so a
            // long title can no longer break in the middle of a word.
            <span
              key={wi}
              style={{
                display: "inline-block",
                whiteSpace: "nowrap",
                marginRight: wi < titleWords.length - 1 ? "0.28em" : 0,
              }}
            >
              {word.split("").map((char, ci) => {
                const i = start + ci;
                const charSpring = spring({
                  frame: frame - i * 1.2,
                  fps,
                  config: { damping: 12, stiffness: 150 },
                });

                return (
                  <span
                    key={ci}
                    style={{
                      display: "inline-block",
                      opacity: charSpring,
                      transform: `translateY(${interpolate(charSpring, [0, 1], [30, 0])}px)`,
                      color: i < accentChars ? accentColor : textColor,
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
                frame: frame - title.length * 1.2 - 5,
                fps,
                config: { damping: 20 },
              }),
              fontSize: 28,
              fontWeight: 400,
              color: subtitleColor,
              fontFamily,
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
