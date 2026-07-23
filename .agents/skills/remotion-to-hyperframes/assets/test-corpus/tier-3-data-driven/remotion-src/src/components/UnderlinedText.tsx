import { interpolate, useCurrentFrame } from "remotion";

interface Props {
  text: string;
  color: string;
}

export const UnderlinedText: React.FC<Props> = ({ text, color }) => {
  const frame = useCurrentFrame();
  // Underline scales from left over 0-30 frames.
  const underlineScaleX = interpolate(frame, [10, 40], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(frame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ position: "relative", display: "inline-block", opacity }}>
      <div
        style={{
          fontSize: 80,
          fontWeight: 600,
          color: "#ffffff",
          fontFamily: "Helvetica, Arial, sans-serif",
        }}
      >
        {text}
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          bottom: -8,
          width: "100%",
          height: 6,
          background: color,
          transform: `scaleX(${underlineScaleX})`,
          transformOrigin: "left center",
          borderRadius: 3,
        }}
      />
    </div>
  );
};
