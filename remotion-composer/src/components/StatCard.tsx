import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { arabicFontFamily, isRTLText } from "../lib/rtlText";

interface StatCardProps {
  stat: string;
  subtitle?: string;
  statFontSize?: number;
  subtitleFontSize?: number;
  color?: string;
  accentColor?: string;
  backgroundColor?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  stat,
  subtitle,
  statFontSize = 128,
  subtitleFontSize = 36,
  color = "#FFFFFF",
  accentColor = "#F59E0B",
  backgroundColor = "#1F2937",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const isRTL = isRTLText(stat) || isRTLText(subtitle);
  const fontFamily = isRTL ? arabicFontFamily : "Inter, system-ui, sans-serif";
  const wordSpacing = isRTL ? "0.25em" : "normal";

  const scale = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 120 },
    from: 0.8,
    to: 1,
  });

  const subtitleOpacity = spring({
    frame: frame - 8,
    fps,
    config: { damping: 20 },
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: backgroundColor,
      }}
    >
      <div style={{ textAlign: "center" }} dir={isRTL ? "rtl" : "ltr"}>
        <div
          style={{
            transform: `scale(${scale})`,
            fontSize: statFontSize,
            color: accentColor,
            fontFamily,
            wordSpacing,
            fontWeight: 800,
            lineHeight: 1.1,
          }}
        >
          {stat}
        </div>
        {subtitle && (
          <div
            style={{
              opacity: subtitleOpacity,
              fontSize: subtitleFontSize,
              color,
              fontFamily,
              wordSpacing,
              fontWeight: 400,
              marginTop: 16,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
