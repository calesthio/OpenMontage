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
}

export const HeroTitle: React.FC<HeroTitleProps> = ({ title, subtitle }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Staggered letter-by-letter spring
  const titleChars = title.split("");
  // Group characters into words so each word wraps as an unbreakable unit
  // (per-character flex items would otherwise break mid-word at the line edge).
  const titleWords = title.split(" ");

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background:
          "radial-gradient(ellipse at center, rgba(15,23,42,0.35) 0%, rgba(15,23,42,0.55) 100%)",
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
            columnGap: "0.28em",
            rowGap: "0.1em",
          }}
        >
          {(() => {
            let charIndex = 0;
            return titleWords.map((word, wIdx) => {
              const wordSpan = (
                <div
                  key={wIdx}
                  style={{ display: "inline-flex", whiteSpace: "nowrap" }}
                >
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
                          color: wIdx === 0 ? "#22D3EE" : "#F8FAFC", // Accent first word
                        }}
                      >
                        {char}
                      </span>
                    );
                  })}
                </div>
              );
              charIndex++; // account for the inter-word space in stagger timing
              return wordSpan;
            });
          })()}
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
              color: "#A78BFA",
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
            backgroundColor: "#22D3EE",
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
