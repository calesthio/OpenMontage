import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const TitleScene = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = spring({ frame, fps, config: { damping: 12, stiffness: 100, mass: 1 } });
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
          fontSize: 140,
          fontWeight: 800,
          color: "#ffffff",
          transform: `scale(${scale})`,
          letterSpacing: "0.05em",
        }}
      >
        Welcome
      </div>
    </AbsoluteFill>
  );
};

const ImageScene = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  const scale = interpolate(frame, [0, 60], [0.8, 1.0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0a0a0a",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <Img
        src={staticFile("square.png")}
        style={{
          width: 200,
          height: 200,
          opacity,
          transform: `scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};

const OutroScene = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: "clamp" });
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
          fontSize: 100,
          fontWeight: 600,
          color: "#ffffff",
          opacity,
        }}
      >
        Goodbye
      </div>
    </AbsoluteFill>
  );
};

export const MultiScene = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={60}>
      <TitleScene />
    </Sequence>
    <Sequence from={60} durationInFrames={60}>
      <ImageScene />
    </Sequence>
    <Sequence from={120} durationInFrames={60}>
      <OutroScene />
    </Sequence>
    <Audio src={staticFile("music.wav")} volume={0.5} />
  </AbsoluteFill>
);
