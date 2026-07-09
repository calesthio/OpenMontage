import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface HeroTitleProps {
  title: string;
  subtitle?: string;
  textColor?: string; // non-accent title glyphs
  accentColor?: string; // first-word accent + underline
  subtitleColor?: string;
  veil?: boolean; // dark radial behind the text — for busy media backgrounds
}

export const HeroTitle: React.FC<HeroTitleProps> = ({
  title,
  subtitle,
  textColor = "#F8FAFC",
  accentColor = "#22D3EE",
  subtitleColor = "#94A3B8",
  veil = true,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  // Wrap at WORD boundaries (per-char flex items wrap mid-word); letters
  // still animate individually inside each word.
  const words = title.split(" ");

  // Scale down long titles instead of overflowing/wrapping to three lines.
  const base = height > width ? 60 : 72;
  const fontSize =
    title.length > 55 ? Math.round(base * 0.66) : title.length > 35 ? Math.round(base * 0.8) : base;

  let charIndex = 0;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: veil
          ? "radial-gradient(ellipse at center, rgba(15,23,42,0.35) 0%, rgba(15,23,42,0.55) 100%)"
          : undefined,
      }}
    >
      <div style={{ textAlign: "center", maxWidth: "85%" }}>
        {/* Main title: word-wrapped, per-character spring */}
        <div
          style={{
            fontSize,
            fontWeight: 800,
            fontFamily: "Space Grotesk, Inter, system-ui, sans-serif",
            lineHeight: 1.2,
            display: "flex",
            justifyContent: "center",
            flexWrap: "wrap",
            columnGap: "0.3em",
          }}
        >
          {words.map((word, wi) => (
            <span key={wi} style={{ display: "inline-flex", whiteSpace: "nowrap" }}>
              {word.split("").map((char) => {
                const i = charIndex++;
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
                      color: i < 8 ? accentColor : textColor, // Accent first word
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
              fontWeight: 500,
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
