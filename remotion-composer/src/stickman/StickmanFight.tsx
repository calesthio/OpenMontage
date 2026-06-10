import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
  random,
} from "remotion";
import { POSES, lerpPose, Pose } from "./poses";
import {
  KEYFRAMES,
  SHAKE_EVENTS,
  FLASH_EVENTS,
  IMPACT_BURSTS,
  TEXT_CARDS,
  WIDTH,
  HEIGHT,
  Keyframe,
} from "./timeline";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const easeFns: Record<string, (t: number) => number> = {
  linear: Easing.linear,
  easeInOut: Easing.inOut(Easing.ease),
  easeOut: Easing.out(Easing.cubic),
  easeIn: Easing.in(Easing.cubic),
  snap: Easing.out(Easing.back(1.2)),
};

function findSurroundingKeyframes(timeSec: number): [Keyframe, Keyframe, number] {
  for (let i = 0; i < KEYFRAMES.length - 1; i++) {
    const a = KEYFRAMES[i];
    const b = KEYFRAMES[i + 1];
    if (timeSec >= a.t && timeSec <= b.t) {
      const span = b.t - a.t || 1;
      const raw = (timeSec - a.t) / span;
      const fn = easeFns[b.ease] ?? Easing.linear;
      return [a, b, fn(Math.min(1, Math.max(0, raw)))];
    }
  }
  const last = KEYFRAMES[KEYFRAMES.length - 1];
  return [last, last, 0];
}

function lerpNum(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

// ---------------------------------------------------------------------------
// Stick figure rig
// ---------------------------------------------------------------------------

interface FighterProps {
  pose: Pose;
  hip: [number, number];
  facing: 1 | -1;
  color: string;
  highlightColor: string;
}

const Fighter: React.FC<FighterProps> = ({ pose, hip, facing, color, highlightColor }) => {
  const [hipX, hipY] = hip;
  const headRadius = 26;
  const torsoLength = 95;

  // Torso end point (shoulders), rotated by torsoLean around the hip.
  const torsoAngleRad = (pose.torsoLean * Math.PI) / 180;
  const shoulderX = -Math.sin(torsoAngleRad) * torsoLength;
  const shoulderY = -Math.cos(torsoAngleRad) * torsoLength;

  const headAngleRad = ((pose.torsoLean + pose.headTilt) * Math.PI) / 180;
  const headCx = shoulderX + Math.sin(headAngleRad) * (headRadius + 4) + pose.headOffsetX;
  const headCy = shoulderY - Math.cos(headAngleRad) * (headRadius + 4) + pose.headOffsetY;

  const limb = (point: { x: number; y: number }) => ({
    x: point.x * facing,
    y: point.y,
  });

  const armL = limb(pose.armL);
  const armR = limb(pose.armR);
  const legL = limb(pose.legL);
  const legR = limb(pose.legR);

  const stroke = color;
  const strokeWidth = 11;

  return (
    <g
      transform={`translate(${hipX + pose.hipOffsetX * facing}, ${
        hipY + pose.hipOffsetY
      }) scale(${pose.scaleX}, ${pose.scaleY})`}
    >
      {/* Legs */}
      <line x1={0} y1={0} x2={legL.x} y2={legL.y} stroke={stroke} strokeWidth={strokeWidth} strokeLinecap="round" />
      <line x1={0} y1={0} x2={legR.x} y2={legR.y} stroke={stroke} strokeWidth={strokeWidth} strokeLinecap="round" />

      {/* Torso */}
      <line x1={0} y1={0} x2={shoulderX} y2={shoulderY} stroke={stroke} strokeWidth={strokeWidth + 2} strokeLinecap="round" />

      {/* Arms */}
      <line x1={shoulderX} y1={shoulderY} x2={shoulderX + armL.x} y2={shoulderY + armL.y} stroke={stroke} strokeWidth={strokeWidth} strokeLinecap="round" />
      <line x1={shoulderX} y1={shoulderY} x2={shoulderX + armR.x} y2={shoulderY + armR.y} stroke={stroke} strokeWidth={strokeWidth} strokeLinecap="round" />

      {/* Head */}
      <circle cx={headCx} cy={headCy} r={headRadius} fill={highlightColor} stroke={stroke} strokeWidth={strokeWidth - 3} />
    </g>
  );
};

// ---------------------------------------------------------------------------
// Background arena
// ---------------------------------------------------------------------------

const Arena: React.FC<{ groundY: number }> = ({ groundY }) => {
  return (
    <>
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1b1037" />
          <stop offset="55%" stopColor="#3a1d5c" />
          <stop offset="100%" stopColor="#7c2f5e" />
        </linearGradient>
        <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#241433" />
          <stop offset="100%" stopColor="#0c0716" />
        </linearGradient>
        <radialGradient id="moonGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fff7d6" stopOpacity={0.9} />
          <stop offset="100%" stopColor="#fff7d6" stopOpacity={0} />
        </radialGradient>
      </defs>
      <rect x={-400} y={-400} width={WIDTH + 800} height={HEIGHT + 800} fill="url(#sky)" />
      <circle cx={WIDTH * 0.78} cy={HEIGHT * 0.18} r={220} fill="url(#moonGlow)" />
      <circle cx={WIDTH * 0.78} cy={HEIGHT * 0.18} r={70} fill="#fff7d6" opacity={0.85} />
      {/* distant mountains */}
      <polygon
        points={`-200,${groundY} 250,${groundY - 220} 600,${groundY - 80} 1000,${groundY - 260} 1450,${groundY - 100} 1900,${groundY - 240} 2200,${groundY}`}
        fill="#190f2b"
        opacity={0.8}
      />
      {/* ground */}
      <rect x={-400} y={groundY} width={WIDTH + 800} height={HEIGHT - groundY + 400} fill="url(#ground)" />
      {/* ground line glow */}
      <rect x={-400} y={groundY - 4} width={WIDTH + 800} height={8} fill="#ff7a59" opacity={0.55} />
    </>
  );
};

// ---------------------------------------------------------------------------
// Particle burst (impact)
// ---------------------------------------------------------------------------

const ImpactParticles: React.FC<{ x: number; y: number; progress: number; scale: number; color: string }> = ({
  x,
  y,
  progress,
  scale,
  color,
}) => {
  const count = 14;
  const particles = Array.from({ length: count }).map((_, i) => {
    const angle = (i / count) * Math.PI * 2 + random(`angle-${i}`) * 0.6;
    const dist = interpolate(progress, [0, 1], [0, 90 + 140 * scale]);
    const px = x + Math.cos(angle) * dist;
    const py = y + Math.sin(angle) * dist;
    const opacity = interpolate(progress, [0, 0.15, 1], [1, 1, 0]);
    const size = interpolate(progress, [0, 1], [10 * scale, 1]);
    return { px, py, opacity, size, key: i };
  });

  return (
    <>
      {particles.map((p) => (
        <circle key={p.key} cx={p.px} cy={p.py} r={Math.max(0, p.size)} fill={color} opacity={Math.max(0, p.opacity)} />
      ))}
    </>
  );
};

// ---------------------------------------------------------------------------
// Speed lines (for high-impact moments)
// ---------------------------------------------------------------------------

const SpeedLines: React.FC<{ opacity: number }> = ({ opacity }) => {
  if (opacity <= 0) return null;
  const lines = Array.from({ length: 18 }).map((_, i) => {
    const cx = WIDTH / 2;
    const cy = HEIGHT / 2;
    const angle = (i / 18) * Math.PI * 2;
    const innerR = 200;
    const outerR = 1400;
    const x1 = cx + Math.cos(angle) * innerR;
    const y1 = cy + Math.sin(angle) * innerR;
    const x2 = cx + Math.cos(angle) * outerR;
    const y2 = cy + Math.sin(angle) * outerR;
    return { x1, y1, x2, y2, key: i };
  });
  return (
    <svg
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
    >
      {lines.map((l) => (
        <line key={l.key} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke="#ffffff" strokeWidth={3} opacity={opacity * 0.5} />
      ))}
    </svg>
  );
};

// ---------------------------------------------------------------------------
// Text card overlay
// ---------------------------------------------------------------------------

const TextCardOverlay: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const t = frame / fps;
  return (
    <>
      {TEXT_CARDS.map((card, i) => {
        if (t < card.from || t > card.to) return null;
        const fadeIn = interpolate(t, [card.from, card.from + 0.35], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const fadeOut = interpolate(t, [card.to - 0.4, card.to], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const opacity = Math.min(fadeIn, fadeOut);
        const scale = interpolate(t, [card.from, card.from + 0.35], [0.85, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const fontSize = card.size === "huge" ? 200 : 96;
        return (
          <AbsoluteFill
            key={i}
            style={{
              alignItems: "center",
              justifyContent: "center",
              opacity,
            }}
          >
            <div
              style={{
                fontFamily: "Arial Black, Impact, sans-serif",
                fontWeight: 900,
                fontSize,
                letterSpacing: 12,
                color: "#fff7e0",
                textShadow:
                  "0 0 30px rgba(255,150,60,0.9), 0 0 60px rgba(255,90,30,0.6), 0 6px 0 rgba(0,0,0,0.5)",
                transform: `scale(${scale})`,
              }}
            >
              {card.text}
            </div>
          </AbsoluteFill>
        );
      })}
    </>
  );
};

// ---------------------------------------------------------------------------
// Main composition
// ---------------------------------------------------------------------------

export const StickmanFight: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const [kfA, kfB, progress] = findSurroundingKeyframes(t);

  const poseA = lerpPose(POSES[kfA.poseA], POSES[kfB.poseA], progress);
  const poseB = lerpPose(POSES[kfA.poseB], POSES[kfB.poseB], progress);

  const hipA: [number, number] = [
    lerpNum(kfA.hipA[0], kfB.hipA[0], progress),
    lerpNum(kfA.hipA[1], kfB.hipA[1], progress),
  ];
  const hipB: [number, number] = [
    lerpNum(kfA.hipB[0], kfB.hipB[0], progress),
    lerpNum(kfA.hipB[1], kfB.hipB[1], progress),
  ];

  const camZoom = lerpNum(kfA.camera.zoom, kfB.camera.zoom, progress);
  const camX = lerpNum(kfA.camera.x, kfB.camera.x, progress);
  const camY = lerpNum(kfA.camera.y, kfB.camera.y, progress);

  // Camera shake
  let shakeX = 0;
  let shakeY = 0;
  for (const ev of SHAKE_EVENTS) {
    if (t >= ev.time && t <= ev.time + ev.duration) {
      const localT = (t - ev.time) / ev.duration;
      const decay = 1 - localT;
      const seedX = random(`shakeX-${ev.time}-${frame}`);
      const seedY = random(`shakeY-${ev.time}-${frame}`);
      shakeX += (seedX - 0.5) * 2 * ev.intensity * decay;
      shakeY += (seedY - 0.5) * 2 * ev.intensity * decay;
    }
  }

  // Flash overlay
  let flashOpacity = 0;
  let flashColor = "#ffffff";
  for (const ev of FLASH_EVENTS) {
    if (t >= ev.time && t <= ev.time + ev.duration) {
      const localT = (t - ev.time) / ev.duration;
      const o = interpolate(localT, [0, 0.25, 1], [ev.peakOpacity, ev.peakOpacity, 0]);
      if (o > flashOpacity) {
        flashOpacity = o;
        flashColor = ev.color;
      }
    }
  }

  // Speed-line opacity for the biggest hits
  let speedLineOpacity = 0;
  for (const ev of FLASH_EVENTS) {
    if (ev.peakOpacity >= 0.6 && t >= ev.time && t <= ev.time + ev.duration * 1.5) {
      const localT = (t - ev.time) / (ev.duration * 1.5);
      speedLineOpacity = Math.max(speedLineOpacity, interpolate(localT, [0, 1], [1, 0]));
    }
  }

  const groundY = HEIGHT * 0.66;

  return (
    <AbsoluteFill style={{ backgroundColor: "#0c0716", overflow: "hidden" }}>
      <svg
        width={WIDTH}
        height={HEIGHT}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ position: "absolute", inset: 0 }}
      >
        <g
          transform={`translate(${WIDTH / 2}, ${HEIGHT / 2}) scale(${camZoom}) translate(${
            -WIDTH / 2 + camX + shakeX
          }, ${-HEIGHT / 2 + camY + shakeY})`}
        >
          <Arena groundY={groundY} />
          <Fighter pose={poseA} hip={hipA} facing={kfB.facingA} color="#f5f1e8" highlightColor="#ffe9c2" />
          <Fighter pose={poseB} hip={hipB} facing={kfB.facingB} color="#9be8ff" highlightColor="#dffaff" />

          {/* Impact particle bursts */}
          {IMPACT_BURSTS.map((burst, i) => {
            if (t < burst.time || t > burst.time + burst.duration) return null;
            const progressBurst = (t - burst.time) / burst.duration;
            return (
              <ImpactParticles
                key={i}
                x={burst.x}
                y={burst.y}
                progress={progressBurst}
                scale={burst.scale}
                color={burst.color}
              />
            );
          })}
        </g>
      </svg>

      <SpeedLines opacity={speedLineOpacity} />

      {/* Flash */}
      {flashOpacity > 0 && (
        <AbsoluteFill style={{ backgroundColor: flashColor, opacity: flashOpacity }} />
      )}

      {/* Vignette */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)",
          pointerEvents: "none",
        }}
      />

      <TextCardOverlay frame={frame} fps={fps} />
    </AbsoluteFill>
  );
};
