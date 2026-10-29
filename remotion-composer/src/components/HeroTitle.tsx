import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { arabicFontFamily, isRTLText } from "../lib/rtlText";

type HeroTitleProps = {
  title: string;
  subtitle?: string;
  /** Color of the leading accent characters and the underline. */
  accentColor?: string;
  /** Color of the remaining title characters. Pass the theme's textColor. */
  textColor?: string;
  /** Subtitle color. */
  subtitleColor?: string;
  /**
   * Scrim painted behind the title so it separates from whatever is underneath.
   * Defaults to a dark wash; a light theme must pass a light one, otherwise the
   * scrim darkens the backdrop and cancels out the theme's dark text.
   */
  scrimBackground?: string;
};

const DEFAULT_SCRIM =
  "radial-gradient(ellipse at center, rgba(15,23,42,0.35) 0%, rgba(15,23,42,0.55) 100%)";

export const HeroTitle: React.FC<HeroTitleProps> = ({
  title,
  subtitle,
  accentColor = "#22D3EE",
  textColor = "#F8FAFC",
  subtitleColor = "#A78BFA",
  scrimBackground = DEFAULT_SCRIM,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Arabic/Hebrew and other RTL scripts must not be split per-character: that
  // breaks Arabic letter joining (isolated-form glyphs) and, under flexbox,
  // reverses word order (flex lays children out LTR regardless of script).
  // Split by whole words instead — shaping survives, and `direction: rtl`
  // below makes the browser place them in correct reading order.
  const isRTL = isRTLText(title);
  const titleUnits = isRTL
    ? title.split(/(\s+)/).filter((u) => u.length > 0)
    : title.split("");
  const firstWordEnd = isRTL
    ? titleUnits.findIndex((u) => /\s/.test(u))
    : 8;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: scrimBackground,
      }}
    >
      <div style={{ textAlign: "center", maxWidth: "85%" }}>
        {/* Main title with per-character (LTR) or per-word (RTL) spring */}
        <div
          dir={isRTL ? "rtl" : "ltr"}
          style={{
            fontSize: 72,
            fontWeight: 800,
            fontFamily: isRTL
              ? arabicFontFamily
              : "Space Grotesk, Inter, system-ui, sans-serif",
            lineHeight: 1.2,
            display: "flex",
            justifyContent: "center",
            flexWrap: "wrap",
            gap: 0,
          }}
        >
          {titleUnits.map((unit, i) => {
            const delay = i * (isRTL ? 4 : 1.2);
            const unitSpring = spring({
              frame: frame - delay,
              fps,
              config: { damping: 12, stiffness: 150 },
            });
            const isSpace = /^\s+$/.test(unit);
            const isAccent =
              firstWordEnd === -1 ? true : i <= firstWordEnd;

            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  opacity: unitSpring,
                  transform: `translateY(${interpolate(unitSpring, [0, 1], [30, 0])}px)`,
                  color: isAccent ? accentColor : textColor, // Accent first word
                  whiteSpace: isSpace ? "pre" : undefined,
                  // Light word-spacing for Arabic display type — improves
                  // legibility/rhythm without letter-spacing, which would
                  // break Arabic letter joining.
                  minWidth: isSpace ? (isRTL ? "0.55em" : "0.3em") : undefined,
                }}
              >
                {unit}
              </span>
            );
          })}
        </div>

        {/* Subtitle */}
        {subtitle && (
          <div
            dir={isRTL ? "rtl" : "ltr"}
            style={{
              marginTop: 20,
              opacity: spring({
                frame: frame - titleUnits.length * (isRTL ? 4 : 1.2) - 5,
                fps,
                config: { damping: 20 },
              }),
              fontSize: 28,
              fontWeight: 400,
              color: subtitleColor,
              fontFamily: isRTL
                ? arabicFontFamily
                : "Space Grotesk, Inter, system-ui, sans-serif",
              letterSpacing: isRTL ? "normal" : "0.1em",
              textTransform: isRTL ? "none" : "uppercase",
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
            backgroundColor: accentColor,
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
