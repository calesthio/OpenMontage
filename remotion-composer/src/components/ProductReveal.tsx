import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  staticFile,
  Easing,
} from "remotion";

export interface ProductRevealProps {
  productImage: string;
  productName: string;
  price: string;
  tagline: string;
  closer: string;
  accentColor?: string;
}

export const ProductReveal: React.FC<ProductRevealProps> = ({
  productImage,
  productName,
  price,
  tagline,
  closer,
  accentColor = "#00D4FF",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // === PHASE 1: Product image scales in with glow (0-1.5s) ===
  const imgScale = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 80, mass: 0.8 },
  });

  const imgOpacity = interpolate(frame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Glow pulse
  const glowIntensity = interpolate(
    Math.sin(frame * 0.08),
    [-1, 1],
    [0.3, 0.7]
  );

  // Slow float
  const floatY = Math.sin(frame * 0.04) * 4;

  // === PHASE 2: Product name springs in letter by letter (1s delay) ===
  const nameDelay = fps * 1.2;
  const nameChars = productName.split("");

  // === PHASE 3: Price reveals (3s delay) ===
  const priceDelay = fps * 3.2;
  const priceSpring = spring({
    frame: frame - priceDelay,
    fps,
    config: { damping: 16, stiffness: 120 },
  });

  // === PHASE 4: Tagline fades in (4.2s delay) ===
  const taglineDelay = fps * 4.2;
  const taglineOpacity = interpolate(
    frame,
    [taglineDelay, taglineDelay + fps * 0.6],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // === PHASE 5: Closer fades in (5.5s delay) ===
  const closerDelay = fps * 5.5;
  const closerOpacity = interpolate(
    frame,
    [closerDelay, closerDelay + fps * 0.8],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // === PHASE 6: Shimmer across price (4.5s) ===
  const shimmerDelay = fps * 4.5;
  const shimmerPos = interpolate(
    frame,
    [shimmerDelay, shimmerDelay + fps * 1.0],
    [-100, 400],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.inOut(Easing.ease),
    }
  );

  // === FADE OUT at end (last 0.8s) ===
  const totalDuration = fps * 8;
  const fadeOut = interpolate(
    frame,
    [totalDuration - fps * 0.8, totalDuration],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse at 50% 35%, #1a1a2e 0%, #0a0a0f 60%, #000000 100%)",
        opacity: fadeOut,
      }}
    >
      {/* Ambient glow behind product */}
      <div
        style={{
          position: "absolute",
          top: "15%",
          left: "50%",
          transform: "translateX(-50%)",
          width: 400,
          height: 400,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accentColor}${Math.round(glowIntensity * 30).toString(16).padStart(2, "0")} 0%, transparent 70%)`,
          filter: "blur(50px)",
        }}
      />

      {/* Product image — centered in upper portion */}
      <div
        style={{
          position: "absolute",
          top: "8%",
          left: "50%",
          transform: `translateX(-50%) translateY(${floatY}px) scale(${interpolate(imgScale, [0, 1], [0.7, 1])})`,
          opacity: imgOpacity,
        }}
      >
        <div
          style={{
            width: 260,
            height: 260,
            borderRadius: 28,
            overflow: "hidden",
            boxShadow: `0 20px 60px rgba(0,0,0,0.6), 0 0 ${40 + glowIntensity * 30}px ${accentColor}22`,
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <Img
            src={staticFile(productImage)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        </div>
        {/* Reflection */}
        <div
          style={{
            width: 260,
            height: 60,
            borderRadius: "0 0 28px 28px",
            overflow: "hidden",
            marginTop: 4,
            opacity: 0.12,
            transform: "scaleY(-1)",
            filter: "blur(6px)",
            maskImage:
              "linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, transparent 100%)",
            WebkitMaskImage:
              "linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, transparent 100%)",
          }}
        >
          <Img
            src={staticFile(productImage)}
            style={{
              width: "100%",
              height: 260,
              objectFit: "cover",
              objectPosition: "bottom",
            }}
          />
        </div>
      </div>

      {/* Text content — stacked vertically, centered */}
      <div
        style={{
          position: "absolute",
          top: "56%",
          left: 0,
          right: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 0,
        }}
      >
        {/* Product name — letter by letter spring */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            flexWrap: "wrap",
            gap: 0,
            marginBottom: 20,
          }}
        >
          {nameChars.map((char, i) => {
            const charDelay = nameDelay + i * 1.0;
            const charSpring = spring({
              frame: frame - charDelay,
              fps,
              config: { damping: 14, stiffness: 160 },
            });

            // "Air" = first 3 chars get accent color
            const isAccent = i < 3;

            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  fontFamily:
                    "'SF Pro Display', 'Helvetica Neue', 'Inter', system-ui, sans-serif",
                  fontSize: 52,
                  fontWeight: 600,
                  letterSpacing: "0.02em",
                  color: isAccent ? accentColor : "#FFFFFF",
                  opacity: charSpring,
                  transform: `translateY(${interpolate(charSpring, [0, 1], [20, 0])}px)`,
                  whiteSpace: char === " " ? "pre" : undefined,
                  minWidth: char === " " ? "0.3em" : undefined,
                }}
              >
                {char}
              </span>
            );
          })}
        </div>

        {/* Price — block element, clearly on its own line */}
        <div
          style={{
            position: "relative",
            overflow: "hidden",
            marginBottom: 10,
          }}
        >
          <div
            style={{
              fontFamily:
                "'SF Pro Display', 'Helvetica Neue', 'Inter', system-ui, sans-serif",
              fontSize: 36,
              fontWeight: 300,
              color: "#FFFFFF",
              opacity: priceSpring,
              transform: `translateY(${interpolate(priceSpring, [0, 1], [15, 0])}px)`,
              letterSpacing: "0.05em",
              textAlign: "center",
            }}
          >
            {price}
          </div>
          {/* Shimmer across price text */}
          {frame >= shimmerDelay && frame <= shimmerDelay + fps * 1.0 && (
            <div
              style={{
                position: "absolute",
                left: shimmerPos,
                top: 0,
                width: 80,
                height: "100%",
                background:
                  "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)",
                filter: "blur(3px)",
                pointerEvents: "none",
              }}
            />
          )}
        </div>

        {/* Tagline */}
        <div
          style={{
            opacity: taglineOpacity,
            fontFamily:
              "'SF Pro Display', 'Helvetica Neue', 'Inter', system-ui, sans-serif",
            fontSize: 20,
            fontWeight: 300,
            color: "#777777",
            letterSpacing: "0.08em",
            marginBottom: 28,
          }}
        >
          {tagline}
        </div>

        {/* Closer */}
        <div
          style={{
            opacity: closerOpacity,
            fontFamily:
              "'SF Pro Display', 'Helvetica Neue', 'Inter', system-ui, sans-serif",
            fontSize: 26,
            fontWeight: 500,
            color: "#BBBBBB",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
          }}
        >
          {closer}
        </div>
      </div>
    </AbsoluteFill>
  );
};
