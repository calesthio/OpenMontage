import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface StatRevealProps {
  stat: string;
  label?: string;
  accentColor?: string;
  /** Label color. Defaults to near-white; pass the theme's textColor on light themes. */
  textColor?: string;
  position?: "center" | "bottom-right" | "right";
}

export const StatReveal: React.FC<StatRevealProps> = ({
  stat,
  label,
  accentColor = "#A78BFA",
  textColor = "#F8FAFC",
  position = "bottom-right",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Bouncy entrance
  const scale = spring({
    frame,
    fps,
    config: { damping: 10, stiffness: 100, mass: 0.8 },
    from: 0,
    to: 1,
  });

  const glow = spring({
    frame: frame - 5,
    fps,
    config: { damping: 20, stiffness: 60 },
  });

  // Exit
  const exitStart = durationInFrames - 12;
  const fadeOut = interpolate(frame, [exitStart, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const opacity = Math.min(spring({ frame, fps, config: { damping: 20 } }), fadeOut);

  const positionStyles: React.CSSProperties =
    position === "center"
      ? { justifyContent: "center", alignItems: "center" }
      : position === "right"
      ? { justifyContent: "center", alignItems: "flex-end", paddingRight: 80 }
      : { justifyContent: "flex-end", alignItems: "flex-end", padding: 80 };

  return (
    <AbsoluteFill style={positionStyles}>
      <div
        style={{
          opacity,
          transform: `scale(${scale})`,
          textAlign: position === "center" ? "center" : "right",
        }}
      >
        <div
          style={{
            fontSize: 96,
            fontWeight: 800,
            color: accentColor,
            fontFamily: "Space Grotesk, Inter, system-ui, sans-serif",
            lineHeight: 1,
            textShadow: `0 0 ${interpolate(glow, [0, 1], [0, 30])}px ${accentColor}66, 0 4px 12px rgba(0,0,0,0.5)`,
          }}
        >
          {stat}
        </div>
        {label && (
          <div
            style={{
              fontSize: 22,
              fontWeight: 500,
              color: textColor,
              fontFamily: "Space Grotesk, Inter, system-ui, sans-serif",
              marginTop: 8,
              opacity: spring({
                frame: frame - 10,
                fps,
                config: { damping: 20 },
              }),
              textShadow: "0 2px 8px rgba(0,0,0,0.6)",
            }}
          >
            {label}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
