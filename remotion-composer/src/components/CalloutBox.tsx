import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { withCjkFallback } from "../fonts";

type CalloutType = "info" | "warning" | "tip" | "quote";

interface CalloutBoxProps {
  text: string;
  type?: CalloutType;
  icon?: string;
  title?: string;
  borderColor?: string;
  backgroundColor?: string;
  textColor?: string;
  fontFamily?: string;
  fontSize?: number;
  titleFontSize?: number;
  containerBackgroundColor?: string;
}

const TYPE_DEFAULTS: Record<
  CalloutType,
  { icon: string; border: string; bg: string }
> = {
  info: { icon: "\u2139\uFE0F", border: "#2563EB", bg: "#EFF6FF" },
  warning: { icon: "\u26A0\uFE0F", border: "#F59E0B", bg: "#FFFBEB" },
  tip: { icon: "\uD83D\uDCA1", border: "#10B981", bg: "#ECFDF5" },
  quote: { icon: "\u201C", border: "#9CA3AF", bg: "#F9FAFB" },
};

export const CalloutBox: React.FC<CalloutBoxProps> = ({
  text,
  type = "info",
  icon,
  title,
  borderColor,
  backgroundColor,
  textColor = "#1F2937",
  fontFamily = withCjkFallback("Inter, system-ui, sans-serif"),
  fontSize = 32,
  titleFontSize = 38,
  containerBackgroundColor = "#FFFFFF",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const defaults = TYPE_DEFAULTS[type];
  const resolvedBorder = borderColor || defaults.border;
  const resolvedBg = backgroundColor || defaults.bg;
  const resolvedIcon = icon || defaults.icon;

  // Slide-in from left with slight bounce
  const slideX = spring({
    frame,
    fps,
    config: { damping: 13, stiffness: 90 },
    from: -80,
    to: 0,
  });

  const opacity = spring({
    frame,
    fps,
    config: { damping: 18 },
  });

  // Scale bounce (subtle overshoot)
  const scale = spring({
    frame,
    fps,
    config: { damping: 11, stiffness: 100 },
    from: 0.96,
    to: 1,
  });

  // Icon entrance — slightly delayed
  const iconScale = spring({
    frame: frame - 5,
    fps,
    config: { damping: 10, stiffness: 120 },
    from: 0.5,
    to: 1,
  });
  const iconOpacity = spring({
    frame: frame - 5,
    fps,
    config: { damping: 20 },
  });

  // Text fade in — staggered after box
  const textOpacity = spring({
    frame: frame - 8,
    fps,
    config: { damping: 20 },
  });

  // Border accent draw (height grows top to bottom)
  const borderDraw = spring({
    frame: frame - 3,
    fps,
    config: { damping: 14, stiffness: 80 },
  });

  // Quote type uses italic styling
  const isQuote = type === "quote";

  return (
    <AbsoluteFill
      style={{
        background: containerBackgroundColor,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          opacity,
          transform: `translateX(${slideX}px) scale(${scale})`,
          width: "72%",
          maxWidth: 1380,
          position: "relative",
        }}
      >
        {/* Main box */}
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "flex-start",
            backgroundColor: resolvedBg,
            borderRadius: 12,
            padding: "40px 48px",
            overflow: "hidden",
            position: "relative",
            boxShadow: "0 2px 12px rgba(0,0,0,0.06)",
          }}
        >
          {/* Left border accent */}
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              width: 6,
              height: `${borderDraw * 100}%`,
              backgroundColor: resolvedBorder,
              borderRadius: "12px 0 0 12px",
            }}
          />

          {/* Icon */}
          <div
            style={{
              fontSize: isQuote ? 72 : 48,
              lineHeight: 1,
              marginRight: 28,
              flexShrink: 0,
              opacity: iconOpacity,
              transform: `scale(${iconScale})`,
              color: isQuote ? resolvedBorder : undefined,
              fontFamily: isQuote ? "Georgia, serif" : undefined,
              fontWeight: isQuote ? 700 : undefined,
              marginTop: isQuote ? -12 : 0,
            }}
          >
            {resolvedIcon}
          </div>

          {/* Content */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 12,
              flex: 1,
              opacity: textOpacity,
            }}
          >
            {title && (
              <div
                style={{
                  fontFamily,
                  fontWeight: 700,
                  fontSize: titleFontSize,
                  color: resolvedBorder,
                  lineHeight: 1.3,
                }}
              >
                {title}
              </div>
            )}
            <div
              style={{
                fontFamily: isQuote ? withCjkFallback("Georgia, serif") : fontFamily,
                fontWeight: isQuote ? 400 : 400,
                fontStyle: isQuote ? "italic" : "normal",
                fontSize,
                color: textColor,
                lineHeight: 1.6,
              }}
            >
              {text}
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
