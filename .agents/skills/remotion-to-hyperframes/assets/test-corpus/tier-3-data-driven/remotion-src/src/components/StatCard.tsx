import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AnimatedNumber } from "./AnimatedNumber";

interface Props {
  label: string;
  value: number;
  color: string;
  delayInFrames: number;
}

export const StatCard: React.FC<Props> = ({ label, value, color, delayInFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const local = frame - delayInFrames;

  const scale = spring({
    frame: local,
    fps,
    config: { damping: 14, stiffness: 90, mass: 1 },
  });
  const opacity = interpolate(local, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width: 280,
        height: 220,
        background: "#1a1a1a",
        borderRadius: 16,
        border: `2px solid ${color}`,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        opacity,
        transform: `scale(${scale})`,
      }}
    >
      <div style={{ fontSize: 72, fontWeight: 800, color, lineHeight: 1 }}>
        {local >= 0 ? <AnimatedNumber from={0} to={value} durationInFrames={45} /> : 0}
      </div>
      <div
        style={{
          fontSize: 24,
          fontWeight: 500,
          color: "#9ca3af",
          marginTop: 16,
          textTransform: "uppercase",
          letterSpacing: "0.1em",
        }}
      >
        {label}
      </div>
    </div>
  );
};
