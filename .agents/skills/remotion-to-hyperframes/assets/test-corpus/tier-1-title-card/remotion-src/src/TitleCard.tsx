import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

export const TitleCard = () => {
  const frame = useCurrentFrame();

  // Fade in 0-15, hold 15-75, fade out 75-90.
  const opacity = interpolate(frame, [0, 15, 75, 90], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0a0a0a",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "Helvetica, Arial, sans-serif",
      }}
    >
      <div
        style={{
          fontSize: 160,
          fontWeight: 800,
          color: "#ffffff",
          opacity,
          letterSpacing: "0.05em",
        }}
      >
        HELLO
      </div>
    </AbsoluteFill>
  );
};
