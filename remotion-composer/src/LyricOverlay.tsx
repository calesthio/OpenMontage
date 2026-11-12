import {
  AbsoluteFill,
  CalculateMetadataFunction,
  OffthreadVideo,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React from "react";
import { loadPlayfair } from "./lib/localFonts";
import { resolveAsset } from "./lib/resolveAsset";
import { Soundtrack } from "./CinematicRenderer";
import type { CinematicSoundtrack } from "./cinematic/types";

const { fontFamily: playfairItalic } = loadPlayfair("italic", ["400", "700"]);

const DEFAULT_FPS = 30;
const ALLOWED_FPS = [24, 25, 30, 50, 60];
const DEFAULT_DURATION_SECONDS = 28;
// The layout below was designed on a 1080-wide frame.
const DESIGN_WIDTH = 1080;

// Unknown or missing values fall back to 30, so existing props render as before.
const resolveFps = (fps: unknown): number =>
  typeof fps === "number" && ALLOWED_FPS.includes(fps) ? fps : DEFAULT_FPS;
// Animation constants were tuned in 30 fps frames; this keeps their wall-clock
// timing identical at any output fps. Unrounded: interpolate() accepts fractions.
const framesAt = (framesAt30: number, fps: number): number => (framesAt30 * fps) / DEFAULT_FPS;

export interface Lyric {
  text: string;
  inSeconds: number;
  outSeconds: number;
}

export type LyricOverlayProps = {
  videoSrc: string;
  lyrics: Lyric[];
  bottomY?: number; // 0..1, vertical center of subtitle band
  /** Output frame rate (24/25/30/50/60). Match the source to avoid judder. Defaults to 30. */
  fps?: number;
  /** Output length. Defaults to 28 s. */
  durationSeconds?: number;
  /** Seconds skipped at the start of the video. */
  videoTrimBeforeSeconds?: number;
  /** 0..1 volume of the video's own audio. Defaults to 1. */
  videoVolume?: number;
  /** Optional track played over the video, same shape as CinematicRenderer's. */
  soundtrack?: CinematicSoundtrack;
};

const LyricLine: React.FC<{ lyric: Lyric; nextInSeconds?: number; bottomY: number }> = ({
  lyric,
  nextInSeconds,
  bottomY,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  // The SHORT side, so a landscape frame keeps portrait's text size.
  const scale = Math.min(width, height) / DESIGN_WIDTH;
  const inFrame = lyric.inSeconds * fps;
  const outFrame = lyric.outSeconds * fps;

  const fadeInDur = framesAt(6, fps);
  const fadeOutDur = framesAt(8, fps);
  // A line's fade-out ends no later than the next line's in-time, so
  // back-to-back lines never stack.
  const fadeOutEnd =
    nextInSeconds === undefined ? outFrame + fadeOutDur : Math.min(outFrame + fadeOutDur, nextInSeconds * fps);
  const fadeOutStart = Math.max(inFrame, fadeOutEnd - fadeOutDur);
  if (frame < inFrame - framesAt(1, fps) || frame >= fadeOutEnd) return null;

  const fadeIn = interpolate(frame, [inFrame, inFrame + fadeInDur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut =
    fadeOutEnd > fadeOutStart
      ? interpolate(frame, [fadeOutStart, fadeOutEnd], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 1;
  const opacity = fadeIn * fadeOut;

  const yRise = interpolate(fadeIn, [0, 1], [10, 0]) * scale;

  const cream = "#F5E7C5";
  const gold = "rgba(255, 214, 150, 0.85)";

  // Line draws in from center outward beneath the text
  const lineProgress = interpolate(frame, [inFrame, inFrame + fadeInDur + framesAt(4, fps)], [0, 1], {
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
      {/* Subtle dark backdrop behind text for readability. It runs to the
          frame's bottom edge: ending it mid-frame left a hard line. */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: height * (1 - bottomY) + 160 * scale,
          background:
            "linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.55) 55%, rgba(0,0,0,0.75) 100%)",
          opacity,
        }}
      />
      <div
        style={{
          transform: `translateY(${yRise}px)`,
          textAlign: "center",
          padding: `0 ${60 * scale}px`,
          filter: `drop-shadow(0 0 ${18 * scale}px rgba(255, 200, 120, 0.22))`,
          position: "relative",
          zIndex: 2,
        }}
      >
        <div
          style={{
            fontFamily: playfairItalic,
            fontStyle: "italic",
            fontWeight: 400,
            fontSize: 54 * scale,
            lineHeight: 1.15,
            color: cream,
            letterSpacing: "0.01em",
            // Explicit line breaks in a lyric are kept.
            whiteSpace: "pre-line",
            textShadow: `0 ${2 * scale}px ${18 * scale}px rgba(0,0,0,0.85), 0 0 ${22 * scale}px rgba(0,0,0,0.5)`,
          }}
        >
          {lyric.text}
        </div>
        {/* Gold underline */}
        <div
          style={{
            marginTop: 18 * scale,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: 10 * scale,
          }}
        >
          <div
            style={{
              width: 90 * scale * lineProgress,
              height: 1.2 * scale,
              background: `linear-gradient(90deg, rgba(245,231,197,0) 0%, ${gold} 100%)`,
            }}
          />
          <div
            style={{
              width: 5 * scale,
              height: 5 * scale,
              borderRadius: 999,
              background: gold,
              opacity: lineProgress,
              boxShadow: `0 0 ${10 * scale}px ${gold}`,
            }}
          />
          <div
            style={{
              width: 90 * scale * lineProgress,
              height: 1.2 * scale,
              background: `linear-gradient(90deg, ${gold} 0%, rgba(245,231,197,0) 100%)`,
            }}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const calculateLyricOverlayMetadata: CalculateMetadataFunction<LyricOverlayProps> = async ({ props }) => {
  const fps = resolveFps(props.fps);
  const seconds =
    typeof props.durationSeconds === "number" && Number.isFinite(props.durationSeconds) && props.durationSeconds > 0
      ? props.durationSeconds
      : DEFAULT_DURATION_SECONDS;
  // Size is left to the composition defaults or the CLI's --width/--height.
  return { fps, durationInFrames: Math.max(1, Math.ceil(seconds * fps)) };
};

export const LyricOverlay: React.FC<LyricOverlayProps> = ({
  videoSrc,
  lyrics,
  bottomY = 0.88,
  videoTrimBeforeSeconds,
  videoVolume = 1,
  soundtrack,
}) => {
  const { fps } = useVideoConfig();
  const ordered = [...lyrics].sort((a, b) => a.inSeconds - b.inSeconds);
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <OffthreadVideo
        src={resolveAsset(videoSrc)}
        trimBefore={videoTrimBeforeSeconds !== undefined ? Math.round(videoTrimBeforeSeconds * fps) : undefined}
        volume={videoVolume}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
      {soundtrack ? (
        <Soundtrack
          src={soundtrack.src}
          volume={soundtrack.volume ?? 1}
          trimBeforeSeconds={soundtrack.trimBeforeSeconds}
          trimAfterSeconds={soundtrack.trimAfterSeconds}
          fadeInSeconds={soundtrack.fadeInSeconds ?? 0.3}
          fadeOutSeconds={soundtrack.fadeOutSeconds ?? 0.5}
        />
      ) : null}
      {ordered.map((l, i) => (
        <LyricLine key={i} lyric={l} nextInSeconds={ordered[i + 1]?.inSeconds} bottomY={bottomY} />
      ))}
    </AbsoluteFill>
  );
};
