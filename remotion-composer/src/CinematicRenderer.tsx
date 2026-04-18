import React from "react";
import { loadFont } from "@remotion/google-fonts/SpaceGrotesk";
import {
  AbsoluteFill,
  Audio,
  CalculateMetadataFunction,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

function resolveAsset(src: string): string {
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) {
    return src;
  }
  const clean = src.replace(/^file:\/\/\/?/, "");
  if (clean.startsWith("/") || /^[A-Za-z]:[/\\]/.test(clean)) {
    return `file:///${clean.replace(/\\/g, "/")}`;
  }
  return staticFile(clean);
}
import { CinematicRendererProps, CinematicTone, CinematicVideoScene } from "./cinematic/types";
import { CaptionOverlay } from "./components/CaptionOverlay";

const FPS = 30;

const { fontFamily } = loadFont("normal", {
  weights: ["400", "500", "700"],
  subsets: ["latin"],
});

const toneGradient = (tone: CinematicTone) => {
  switch (tone) {
    case "steel":
      return "linear-gradient(180deg, rgba(6,12,18,0.18) 0%, rgba(2,4,8,0.48) 100%)";
    case "void":
      return "linear-gradient(180deg, rgba(2,4,8,0.14) 0%, rgba(0,0,0,0.56) 100%)";
    case "neutral":
      return "linear-gradient(180deg, rgba(10,10,12,0.16) 0%, rgba(0,0,0,0.42) 100%)";
    case "cold":
    default:
      return "linear-gradient(180deg, rgba(8,16,24,0.18) 0%, rgba(2,4,8,0.42) 100%)";
  }
};

const MissingAssetPlaceholder: React.FC<{ label: string; tone: CinematicTone }> = ({
  label,
  tone,
}) => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#020407",
        justifyContent: "center",
        alignItems: "center",
        color: "#5b6f80",
        fontFamily,
        fontSize: 22,
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        textAlign: "center",
        padding: 64,
      }}
    >
      <div
        style={{
          padding: "18px 28px",
          border: "1px dashed rgba(140, 170, 200, 0.35)",
          borderRadius: 6,
          background: toneGradient(tone),
        }}
      >
        {label}
      </div>
    </AbsoluteFill>
  );
};

const SceneVideo: React.FC<{ scene: CinematicVideoScene }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();
  const fadeInFrames = scene.fadeInFrames ?? 10;
  const fadeOutFrames = scene.fadeOutFrames ?? 10;
  const fadeOutStart = Math.max(fadeInFrames, durationInFrames - fadeOutFrames);
  const fadeInOpacity =
    fadeInFrames === 0
      ? 1
      : interpolate(frame, [0, fadeInFrames], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
  const fadeOutOpacity =
    fadeOutFrames === 0
      ? 1
      : interpolate(frame, [fadeOutStart, durationInFrames], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
  const opacity = Math.min(fadeInOpacity, fadeOutOpacity);

  const scale = interpolate(frame, [0, durationInFrames], [1.015, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const trimBefore =
    scene.trimBeforeSeconds !== undefined
      ? Math.round(scene.trimBeforeSeconds * fps)
      : undefined;
  const trimAfter =
    scene.trimAfterSeconds !== undefined
      ? Math.round(scene.trimAfterSeconds * fps)
      : undefined;

  if (!scene.src) {
    return (
      <AbsoluteFill style={{ opacity }}>
        <MissingAssetPlaceholder
          label={`Video asset missing — ${scene.id}`}
          tone={scene.tone ?? "cold"}
        />
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#020407", opacity }}>
      <OffthreadVideo
        muted
        src={resolveAsset(scene.src)}
        trimBefore={trimBefore}
        trimAfter={trimAfter}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
          filter:
            scene.filter ?? "contrast(1.06) saturate(0.88) brightness(0.92)",
        }}
      />
      <AbsoluteFill
        style={{
          background: toneGradient(scene.tone ?? "cold"),
          mixBlendMode: "multiply",
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at center, transparent 52%, rgba(0,0,0,0.52) 100%)",
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(255,255,255,0.02) 0%, transparent 8%, transparent 92%, rgba(255,255,255,0.02) 100%)",
          opacity: 0.6,
        }}
      />
    </AbsoluteFill>
  );
};

const SignalTexture: React.FC<{
  accent: string;
  intensity: number;
  lineCount: number;
}> = ({ accent, intensity, lineCount }) => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {new Array(lineCount).fill(true).map((_, index) => {
        const pulse = Math.max(0, Math.sin(frame * 0.06 + index * 0.85));
        const opacity = (0.025 + pulse * 0.07) * intensity;
        const width = 18 + ((index * 37) % 56);
        const top = 140 + index * 42;
        const left = index % 2 === 0 ? 0 : 1920 - width;

        return (
          <div
            key={index}
            style={{
              position: "absolute",
              top,
              left,
              width,
              height: 1,
              background: accent,
              boxShadow: `0 0 16px ${accent}`,
              opacity,
            }}
          />
        );
      })}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "repeating-linear-gradient(180deg, rgba(255,255,255,0.028) 0px, rgba(255,255,255,0.028) 1px, transparent 2px, transparent 6px)",
          opacity: 0.12 * intensity,
        }}
      />
    </AbsoluteFill>
  );
};

const TitleCard: React.FC<{
  text: string;
  accent: string;
  intensity: number;
  titleFontSize: number;
  titleWidth: number;
  signalLineCount: number;
}> = ({
  text,
  accent,
  intensity,
  titleFontSize,
  titleWidth,
  signalLineCount,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const reveal = spring({
    fps,
    frame,
    config: { damping: 18, stiffness: 90 },
  });

  const exit = interpolate(
    frame,
    [durationInFrames - 12, durationInFrames],
    [1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );

  const y = interpolate(reveal, [0, 1], [18, 0]);
  const letterSpacing = interpolate(reveal, [0, 1], [0.3, 0.18]);
  const flareOpacity =
    0.18 + Math.max(0, Math.sin(frame * 0.08)) * 0.14 * intensity;

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(circle at 50% 42%, rgba(16,28,40,0.9) 0%, rgba(3,5,8,1) 58%, rgba(0,0,0,1) 100%)",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <SignalTexture
        accent={accent}
        intensity={intensity}
        lineCount={signalLineCount}
      />
      <div
        style={{
          position: "absolute",
          width: 880,
          height: 2,
          background: accent,
          boxShadow: `0 0 28px ${accent}`,
          opacity: flareOpacity,
          transform: "translateY(-126px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 880,
          height: 2,
          background: accent,
          boxShadow: `0 0 28px ${accent}`,
          opacity: flareOpacity * 0.7,
          transform: "translateY(126px)",
        }}
      />
      <div
        style={{
          opacity: reveal * exit,
          transform: `translateY(${y}px)`,
          fontFamily,
          fontWeight: 700,
          fontSize: titleFontSize,
          lineHeight: 1.06,
          letterSpacing: `${letterSpacing}em`,
          textAlign: "center",
          color: "#f3f6fa",
          textTransform: "uppercase",
          width: titleWidth,
          textShadow: "0 0 22px rgba(255,255,255,0.08)",
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

const Soundtrack: React.FC<{
  src: string;
  volume: number;
  trimBeforeSeconds?: number;
  trimAfterSeconds?: number;
  fadeInSeconds: number;
  fadeOutSeconds: number;
}> = ({
  src,
  volume,
  trimBeforeSeconds,
  trimAfterSeconds,
  fadeInSeconds,
  fadeOutSeconds,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();

  const fadeInFrames = Math.max(1, Math.round(fadeInSeconds * fps));
  const fadeOutFrames = Math.max(1, Math.round(fadeOutSeconds * fps));
  const trimBefore =
    trimBeforeSeconds !== undefined
      ? Math.round(trimBeforeSeconds * fps)
      : undefined;
  const trimAfter =
    trimAfterSeconds !== undefined
      ? Math.round(trimAfterSeconds * fps)
      : undefined;

  const fadeIn = interpolate(frame, [0, fadeInFrames], [0, volume], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - fadeOutFrames, durationInFrames],
    [volume, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );

  if (!src) {
    return null;
  }

  return (
    <Audio
      src={resolveAsset(src)}
      trimBefore={trimBefore}
      trimAfter={trimAfter}
      volume={() => Math.min(fadeIn, fadeOut)}
    />
  );
};

export const calculateCinematicMetadata: CalculateMetadataFunction<CinematicRendererProps> =
  async ({ props }) => {
    const totalSeconds =
      props.scenes.length === 0
        ? 30
        : Math.max(
            ...props.scenes.map((scene) => scene.startSeconds + scene.durationSeconds),
          );

    return {
      durationInFrames: Math.max(1, Math.ceil(totalSeconds * FPS)),
      fps: FPS,
      width: 1920,
      height: 1080,
    };
  };

export const CinematicRenderer: React.FC<CinematicRendererProps> = ({
  scenes,
  titleFontSize = 78,
  titleWidth = 1320,
  signalLineCount = 18,
  soundtrack,
  music,
  captions,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000000" }}>
      {/* Layer 1: Narration audio */}
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
      {/* Layer 2: Music bed (separate track, ducked) */}
      {music ? (
        <Soundtrack
          src={music.src}
          volume={music.volume ?? 0.15}
          trimBeforeSeconds={music.trimBeforeSeconds}
          trimAfterSeconds={music.trimAfterSeconds}
          fadeInSeconds={music.fadeInSeconds ?? 2}
          fadeOutSeconds={music.fadeOutSeconds ?? 3}
        />
      ) : null}
      {/* Layer 3: Video scenes */}
      {scenes.map((scene) => (
        <Sequence
          key={scene.id}
          from={Math.round(scene.startSeconds * FPS)}
          durationInFrames={Math.round(scene.durationSeconds * FPS)}
        >
          {scene.kind === "video" ? (
            <SceneVideo scene={scene} />
          ) : (
            <TitleCard
              text={scene.text}
              accent={scene.accent ?? "#86d8ff"}
              intensity={scene.intensity ?? 1}
              titleFontSize={titleFontSize}
              titleWidth={titleWidth}
              signalLineCount={signalLineCount}
            />
          )}
        </Sequence>
      ))}
      {/* Layer 4: TikTok-style captions */}
      {captions?.words ? (
        <CaptionOverlay
          words={captions.words}
          wordsPerPage={captions.wordsPerPage ?? 5}
          fontSize={captions.fontSize ?? 48}
          color={captions.color ?? "#F8FAFC"}
          highlightColor={captions.highlightColor ?? "#FBBF24"}
          backgroundColor={captions.backgroundColor ?? "rgba(0, 0, 0, 0.6)"}
        />
      ) : null}
    </AbsoluteFill>
  );
};
