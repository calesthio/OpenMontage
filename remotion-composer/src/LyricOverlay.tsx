import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React from "react";
import { loadFont as loadPlayfair } from "@remotion/google-fonts/PlayfairDisplay";

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

export interface Lyric {
  text: string;
  inSeconds: number;
  outSeconds: number;
}

export interface LyricOverlayProps {
  videoSrc: string;
  lyrics: Lyric[];
  bottomY?: number; // 0..1, vertical center of subtitle band
}

const LyricLine: React.FC<{ lyric: Lyric; bottomY: number }> = ({ lyric, bottomY }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const inFrame = lyric.inSeconds * fps;
  const outFrame = lyric.outSeconds * fps;
  if (frame < inFrame - 1 || frame > outFrame + 8) return null;

  const fadeInDur = 6;
  const fadeOutDur = 8;

  const fadeIn = interpolate(frame, [inFrame, inFrame + fadeInDur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(frame, [outFrame, outFrame + fadeOutDur], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = fadeIn * fadeOut;

  const yRise = interpolate(fadeIn, [0, 1], [10, 0]);

  const cream = "#F5E7C5";
  const gold = "rgba(255, 214, 150, 0.85)";

  // Line draws in from center outward beneath the text
  const lineProgress = interpolate(frame, [inFrame, inFrame + fadeInDur + 4], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-end",
        paddingBottom: height * (1 - bottomY),
        opacity,
      }}
    >
      {/* Subtle dark backdrop behind text for readability */}
      <div
        style={{
          position: "absolute",
          bottom: height * (1 - bottomY) - 80,
          left: 0,
          right: 0,
          height: 240,
          background:
            "linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.55) 55%, rgba(0,0,0,0.75) 100%)",
          opacity,
        }}
      />
      <div
        style={{
          transform: `translateY(${yRise}px)`,
          textAlign: "center",
          padding: "0 60px",
          filter: "drop-shadow(0 0 18px rgba(255, 200, 120, 0.22))",
          position: "relative",
          zIndex: 2,
        }}
      >
        <div
          style={{
            fontFamily: playfairItalic,
            fontStyle: "italic",
            fontWeight: 400,
            fontSize: 54,
            lineHeight: 1.15,
            color: cream,
            letterSpacing: "0.01em",
            textShadow: "0 2px 18px rgba(0,0,0,0.85), 0 0 22px rgba(0,0,0,0.5)",
          }}
        >
          {lyric.text}
        </div>
        {/* Gold underline */}
        <div
          style={{
            marginTop: 18,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div
            style={{
              width: 90 * lineProgress,
              height: 1.2,
              background: `linear-gradient(90deg, rgba(245,231,197,0) 0%, ${gold} 100%)`,
            }}
          />
          <div
            style={{
              width: 5,
              height: 5,
              borderRadius: 999,
              background: gold,
              opacity: lineProgress,
              boxShadow: `0 0 10px ${gold}`,
            }}
          />
          <div
            style={{
              width: 90 * lineProgress,
              height: 1.2,
              background: `linear-gradient(90deg, ${gold} 0%, rgba(245,231,197,0) 100%)`,
            }}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const LyricOverlay: React.FC<LyricOverlayProps> = ({
  videoSrc,
  lyrics,
  bottomY = 0.88,
}) => {
  const { durationInFrames } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <OffthreadVideo src={resolveAsset(videoSrc)} />
      {lyrics.map((l, i) => (
        <LyricLine key={i} lyric={l} bottomY={bottomY} />
      ))}
    </AbsoluteFill>
  );
};
