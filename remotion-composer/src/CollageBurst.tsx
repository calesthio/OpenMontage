import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  random,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React from "react";
import { loadFont as loadPlayfair } from "@remotion/google-fonts/PlayfairDisplay";

const { fontFamily: playfairFamily } = loadPlayfair("normal", {
  weights: ["400", "700"],
  subsets: ["latin"],
});
const { fontFamily: playfairItalic } = loadPlayfair("italic", {
  weights: ["400", "700"],
  subsets: ["latin"],
});

function resolveAsset(src: string): string {
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) return src;
  const clean = src.replace(/^file:\/\/\/?/, "");
  if (clean.startsWith("/") || /^[A-Za-z]:[\\/]/.test(clean)) {
    const posix = clean.replace(/\\/g, "/");
    // POSIX absolute paths already have a leading "/" — file:// + posix
    // gives exactly three slashes. Windows drive paths (C:/...) need the
    // extra slash added explicitly. Do not merge these branches — adding
    // "file:///" unconditionally double-slashes POSIX paths (file:////...).
    if (posix.startsWith("/")) {
      return `file://${posix}`;
    }
    return `file:///${posix}`;
  }
  return staticFile(clean);
}

export type CollageTransition =
  | "pop"
  | "slide-zoom"
  | "spin"
  | "shutter"
  | "glitch"
  | "swoop";

export interface CollageClip {
  src: string;
  kind: "image" | "video";
  inSeconds: number;
  outSeconds: number;
  x: number; // 0..1 center
  y: number; // 0..1 center
  widthPct: number; // 0..1 of frame width
  aspect?: number; // width/height, default 3/4 (portrait card)
  rotation: number; // degrees
  sourceInSeconds?: number;
  transition?: CollageTransition;
  hero?: boolean; // adds extra polish + flash boost
  seed?: number;
}

export interface CollageBurstProps {
  backgroundSrc: string;
  backgroundInSeconds?: number;
  curtainStartSeconds: number;
  curtainEndSeconds: number;
  clips: CollageClip[];
}

// ----------------------------------------------------------------------------
// Opening text — elegant serif card that lives in the pre-reveal black, then
// fades out as the curtain opens.
// ----------------------------------------------------------------------------
const OpeningText: React.FC<{
  lineOne: string;
  lineTwo: string;
  fadeInStart: number;
  fadeInEnd: number;
  fadeOutStart: number;
  fadeOutEnd: number;
}> = ({ lineOne, lineTwo, fadeInStart, fadeInEnd, fadeOutStart, fadeOutEnd }) => {
  const frame = useCurrentFrame();
  if (frame < fadeInStart || frame > fadeOutEnd) return null;

  const fadeIn = interpolate(frame, [fadeInStart, fadeInEnd], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(frame, [fadeOutStart, fadeOutEnd], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = fadeIn * fadeOut;

  // Slight rise on entry, slight drift on exit
  const yIn = interpolate(fadeIn, [0, 1], [18, 0]);
  const yOut = interpolate(fadeOut, [0, 1], [-10, 0]);
  const y = yIn + yOut;

  // Line draws in from center outward
  const lineProgress = interpolate(frame, [fadeInStart, fadeInEnd + 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cream = "#F5E7C5";
  const gold = "rgba(255, 214, 150, 0.9)";

  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        paddingTop: "8%",
        opacity,
      }}
    >
      <div
        style={{
          transform: `translateY(${y}px)`,
          textAlign: "center",
          filter: `drop-shadow(0 0 22px rgba(255, 200, 120, 0.3))`,
        }}
      >
        {/* Decorative rule */}
        <div
          style={{
            width: 160 * lineProgress,
            height: 1.5,
            background: `linear-gradient(90deg, rgba(245,231,197,0) 0%, ${gold} 50%, rgba(245,231,197,0) 100%)`,
            margin: "0 auto 28px",
          }}
        />
        <div
          style={{
            fontFamily: playfairFamily,
            fontWeight: 400,
            fontSize: 46,
            color: cream,
            letterSpacing: "0.01em",
            lineHeight: 1.35,
            textShadow: "0 2px 18px rgba(0,0,0,0.7)",
          }}
        >
          {lineOne}
        </div>
        <div
          style={{
            fontFamily: playfairItalic,
            fontStyle: "italic",
            fontWeight: 400,
            fontSize: 78,
            color: cream,
            letterSpacing: "0.005em",
            lineHeight: 1.15,
            marginTop: 14,
            textShadow: "0 2px 22px rgba(0,0,0,0.75)",
          }}
        >
          {lineTwo}
        </div>
        {/* Small jewel divider */}
        <div
          style={{
            marginTop: 30,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: 14,
            opacity: lineProgress,
          }}
        >
          <div
            style={{
              width: 60,
              height: 1,
              background: `linear-gradient(90deg, rgba(245,231,197,0) 0%, ${gold} 100%)`,
            }}
          />
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: 999,
              background: gold,
              boxShadow: `0 0 14px ${gold}`,
            }}
          />
          <div
            style={{
              width: 60,
              height: 1,
              background: `linear-gradient(90deg, ${gold} 0%, rgba(245,231,197,0) 100%)`,
            }}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ----------------------------------------------------------------------------
// White flash — brief burst when a card lands. Rendered at composition level.
// ----------------------------------------------------------------------------
const CardFlash: React.FC<{ atFrame: number; strength?: number }> = ({
  atFrame,
  strength = 0.4,
}) => {
  const frame = useCurrentFrame();
  if (frame < atFrame - 1 || frame > atFrame + 6) return null;
  const t = (frame - atFrame) / 6;
  const opacity = Math.max(0, (1 - t) * strength);
  return (
    <AbsoluteFill
      style={{
        backgroundColor: "white",
        opacity,
        pointerEvents: "none",
        mixBlendMode: "screen",
      }}
    />
  );
};

// ----------------------------------------------------------------------------
// CollageCard — picks an entry transition by `clip.transition` and plays video
// starting at its in-time via <Sequence>.
// ----------------------------------------------------------------------------
const CollageCard: React.FC<{ clip: CollageClip; frameW: number; frameH: number }> = ({
  clip,
  frameW,
  frameH,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const inFrame = clip.inSeconds * fps;
  const outFrame = clip.outSeconds * fps;
  if (frame < inFrame - 2 || frame > outFrame + 8) return null;

  const rel = frame - inFrame;
  const relOut = frame - outFrame;
  const seed = clip.seed ?? 0;
  const transition = clip.transition ?? "pop";

  // Common spring value 0→1 over ~18f for entrance
  const entry = spring({
    frame: rel,
    fps,
    config: { damping: 10, stiffness: 130, mass: 0.85 },
    durationInFrames: 20,
  });

  const exit = spring({
    frame: relOut,
    fps,
    config: { damping: 14, stiffness: 200, mass: 0.8 },
    durationInFrames: 12,
  });

  const isExiting = frame >= outFrame;

  // Base transform values derived from transition
  let scale = 1;
  let rot = clip.rotation;
  let offX = 0;
  let offY = 0;
  let opacity = 1;
  let clipPathCss: string | undefined;
  let blur = 0;

  if (!isExiting) {
    const e = entry;
    const inv = 1 - e;
    switch (transition) {
      case "pop":
        scale = e;
        opacity = e;
        break;
      case "slide-zoom": {
        const dir = (seed % 4); // 0=left, 1=right, 2=top, 3=bottom
        const slide = frameW * 0.6 * inv;
        if (dir === 0) offX = -slide;
        else if (dir === 1) offX = slide;
        else if (dir === 2) offY = -slide;
        else offY = slide;
        scale = 0.7 + 0.3 * e;
        opacity = e;
        blur = inv * 8;
        break;
      }
      case "spin": {
        scale = e;
        rot = clip.rotation + (1 - e) * (seed % 2 === 0 ? 540 : -540);
        opacity = e;
        break;
      }
      case "shutter": {
        scale = 0.92 + 0.08 * e;
        opacity = e > 0.1 ? 1 : 0;
        const pct = Math.round(inv * 50);
        clipPathCss = `inset(${pct}% 0 ${pct}% 0 round 14px)`;
        break;
      }
      case "glitch": {
        scale = 0.85 + 0.15 * e;
        opacity = e;
        // High-frequency jitter first ~8f then settles
        const jitterAmt = Math.max(0, 1 - rel / 8);
        offX = (random(`gx${seed}-${Math.floor(rel / 1)}`) - 0.5) * 40 * jitterAmt;
        offY = (random(`gy${seed}-${Math.floor(rel / 1)}`) - 0.5) * 40 * jitterAmt;
        rot = clip.rotation + (random(`gr${seed}-${Math.floor(rel / 2)}`) - 0.5) * 16 * jitterAmt;
        break;
      }
      case "swoop": {
        // arc in from a corner
        const fromX = (seed % 2 === 0 ? -1 : 1) * frameW * 0.55;
        const fromY = -frameH * 0.3;
        offX = fromX * inv;
        offY = fromY * inv;
        scale = 0.6 + 0.4 * e;
        rot = clip.rotation + inv * (seed % 2 === 0 ? -35 : 35);
        opacity = e;
        break;
      }
    }
  } else {
    // Exit: quick shrink + fade
    const o = exit;
    scale = 1 - 0.7 * o;
    opacity = 1 - o;
    rot = clip.rotation + o * (seed % 2 === 0 ? -8 : 8);
  }

  // Gentle idle breathing while held
  const idle = Math.sin((rel - 20) / 14 + seed) * 0.012;
  const held = !isExiting && rel > 20;
  const idleScale = held ? 1 + idle : 1;

  const aspect = clip.aspect ?? 3 / 4; // default portrait
  const w = frameW * clip.widthPct;
  const h = w / aspect;
  const cx = clip.x * frameW;
  const cy = clip.y * frameH;

  // Source offset for videos — Sequence starts at inFrame so OffthreadVideo
  // naturally begins playback on card entry.
  const startFromFrames = Math.round((clip.sourceInSeconds ?? 0) * fps);

  const borderWidth = clip.hero ? 10 : 8;
  const glowColor = clip.hero ? "rgba(255, 210, 140, 0.5)" : "rgba(255,255,255,0.05)";

  const cardContent =
    clip.kind === "image" ? (
      <Img
        src={resolveAsset(clip.src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          display: "block",
        }}
      />
    ) : (
      <Sequence from={inFrame} layout="none">
        <OffthreadVideo
          src={resolveAsset(clip.src)}
          startFrom={startFromFrames}
          muted
          playbackRate={1}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            display: "block",
          }}
        />
      </Sequence>
    );

  return (
    <div
      style={{
        position: "absolute",
        left: cx - w / 2,
        top: cy - h / 2,
        width: w,
        height: h,
        transform: `translate(${offX}px, ${offY}px) rotate(${rot}deg) scale(${scale * idleScale})`,
        transformOrigin: "center center",
        opacity,
        filter: blur > 0 ? `blur(${blur}px)` : undefined,
        willChange: "transform",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: 16,
          overflow: "hidden",
          boxShadow: clip.hero
            ? "0 40px 100px rgba(0,0,0,0.7), 0 0 90px rgba(255,200,120,0.55), 0 8px 18px rgba(0,0,0,0.55)"
            : "0 24px 60px rgba(0,0,0,0.6), 0 8px 18px rgba(0,0,0,0.4)",
          border: `${borderWidth}px solid #FAFAF5`,
          backgroundColor: "#FAFAF5",
          clipPath: clipPathCss,
        }}
      >
        {cardContent}
        {/* Subtle inner vignette on hero cards for depth */}
        {clip.hero && (
          <AbsoluteFill
            style={{
              pointerEvents: "none",
              background:
                "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.4) 100%)",
            }}
          />
        )}
        {/* Warm film edge glow for hero */}
        {clip.hero && (
          <AbsoluteFill
            style={{
              pointerEvents: "none",
              boxShadow: `inset 0 0 60px ${glowColor}`,
            }}
          />
        )}
      </div>
    </div>
  );
};

export const CollageBurst: React.FC<CollageBurstProps> = ({
  backgroundSrc,
  backgroundInSeconds = 0,
  curtainStartSeconds,
  curtainEndSeconds,
  clips,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const curtainStart = curtainStartSeconds * fps;
  const curtainEnd = curtainEndSeconds * fps;

  const t = interpolate(frame, [curtainStart, curtainEnd], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const panelShift = ease * (width / 2 + 40);

  const seamOpacity = frame < curtainStart ? 0.65 + 0.35 * Math.sin(frame / 3) : 0;
  const seamGlow = frame < curtainStart ? 0.6 + 0.4 * Math.sin(frame / 4) : 0;

  const bgStartFrame = Math.max(0, curtainStart - 6);
  const bgVisible = frame >= bgStartFrame;

  // Slow cinematic zoom
  const bgZoom = interpolate(frame, [curtainStart, curtainStart + 900], [1.05, 1.18], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Screen shake intensity — spikes briefly around each clip entry
  let shakeX = 0;
  let shakeY = 0;
  for (const c of clips) {
    const entryFrame = c.inSeconds * fps;
    const dist = frame - entryFrame;
    if (dist >= 0 && dist < 6) {
      const falloff = 1 - dist / 6;
      const amp = (c.hero ? 12 : 5) * falloff;
      shakeX += (random(`sx-${entryFrame}-${dist}`) - 0.5) * amp;
      shakeY += (random(`sy-${entryFrame}-${dist}`) - 0.5) * amp;
    }
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#0a0a0a" }}>
      {/* ---------- Hazy muted background ---------- */}
      {bgVisible && (
        <AbsoluteFill
          style={{
            transform: `scale(${bgZoom})`,
            filter: "saturate(0.35) brightness(0.55) contrast(0.95) blur(6px)",
            opacity: 0.55,
          }}
        >
          <OffthreadVideo
            src={resolveAsset(backgroundSrc)}
            startFrom={Math.round(backgroundInSeconds * fps)}
            muted
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              display: "block",
            }}
          />
        </AbsoluteFill>
      )}

      {/* Dirty-gold / grey atmospheric wash layered over bg */}
      {bgVisible && (
        <AbsoluteFill
          style={{
            pointerEvents: "none",
            background:
              "radial-gradient(ellipse at 50% 40%, rgba(180,150,110,0.18) 0%, rgba(30,28,24,0.75) 70%, rgba(5,5,5,0.95) 100%)",
            mixBlendMode: "multiply",
          }}
        />
      )}

      {/* Grainy noise via CSS — subtle film texture */}
      {bgVisible && (
        <AbsoluteFill
          style={{
            pointerEvents: "none",
            opacity: 0.22,
            background:
              "repeating-conic-gradient(rgba(255,255,255,0.04) 0deg 1deg, rgba(0,0,0,0) 1deg 2deg)",
            mixBlendMode: "overlay",
          }}
        />
      )}

      {/* ---------- Curtain ---------- */}
      <AbsoluteFill>
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "50%",
            height: "100%",
            backgroundColor: "#050505",
            transform: `translateX(${-panelShift}px)`,
            boxShadow: "inset -30px 0 60px rgba(0,0,0,0.9)",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 0,
            right: 0,
            width: "50%",
            height: "100%",
            backgroundColor: "#050505",
            transform: `translateX(${panelShift}px)`,
            boxShadow: "inset 30px 0 60px rgba(0,0,0,0.9)",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 0,
            left: "50%",
            width: 8,
            height: "100%",
            transform: "translateX(-50%)",
            background:
              "linear-gradient(180deg, rgba(255,220,160,0) 0%, rgba(255,220,160,1) 50%, rgba(255,220,160,0) 100%)",
            opacity: Math.max(0, seamOpacity - ease * 1.2),
            filter: `blur(${2 + 6 * seamGlow}px)`,
            boxShadow: `0 0 ${50 + 80 * seamGlow}px rgba(255, 200, 120, 0.95)`,
          }}
        />
      </AbsoluteFill>

      {/* ---------- Opening text (pre-reveal, on black) ---------- */}
      <OpeningText
        lineOne="When you realize your daughters"
        lineTwo="deserve these lines"
        fadeInStart={Math.round(0.3 * fps)}
        fadeInEnd={Math.round(0.9 * fps)}
        fadeOutStart={Math.round(1.8 * fps)}
        fadeOutEnd={Math.round(2.6 * fps)}
      />

      {/* ---------- Foreground shake wrapper ---------- */}
      <AbsoluteFill style={{ transform: `translate(${shakeX}px, ${shakeY}px)` }}>
        {clips.map((clip, i) => (
          <CollageCard key={i} clip={clip} frameW={width} frameH={height} />
        ))}
      </AbsoluteFill>

      {/* ---------- Flash bursts layered on each clip entry ---------- */}
      {clips.map((c, i) => (
        <CardFlash
          key={`f${i}`}
          atFrame={c.inSeconds * fps}
          strength={c.hero ? 0.55 : 0.22}
        />
      ))}

      {/* Frame top/bottom vignette for focus */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0) 14%, rgba(0,0,0,0) 86%, rgba(0,0,0,0.5) 100%)",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
