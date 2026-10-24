import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { arabicFontFamily, isRTLText } from "../lib/rtlText";

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
  const isRTL = isRTLText(text);

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
        dir={isRTL ? "rtl" : "ltr"}
        style={{
          opacity,
          transform: `scale(${scale})`,
          fontSize,
          color,
          fontFamily: isRTL ? arabicFontFamily : "Inter, system-ui, sans-serif",
          wordSpacing: isRTL ? "0.25em" : "normal",
          fontWeight: 700,
          textAlign: "center",
          maxWidth: "80%",
          lineHeight: 1.3,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
