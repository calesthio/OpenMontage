import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface TextCardProps {
  text: string;
  fontSize?: number;
  color?: string;
  backgroundColor?: string;
}

export const TextCard: React.FC<TextCardProps> = ({
  text,
  fontSize = 64,
  color = "#FFFFFF",
  backgroundColor = "#1F2937",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = spring({ frame, fps, config: { damping: 20 } });
  const scale = spring({
    frame,
    fps,
    config: { damping: 15, stiffness: 100 },
    from: 0.95,
    to: 1,
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: backgroundColor,
      }}
    >
      <div
        style={{
          opacity,
          transform: `scale(${scale})`,
          fontSize,
          color,
          fontFamily: "Inter, system-ui, sans-serif",
          fontWeight: 700,
          textAlign: "center",
          maxWidth: "80%",
          lineHeight: 1.3,
          whiteSpace: "pre-line",
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
