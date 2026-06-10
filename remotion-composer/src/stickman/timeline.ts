// Fight choreography timeline for the 30-second stickman cinematic.
// All times are in seconds. FPS = 30.

export const FPS = 30;
export const DURATION_SECONDS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

export type Easing = "linear" | "easeInOut" | "easeOut" | "easeIn" | "snap";

export interface CameraState {
  zoom: number;
  x: number;
  y: number;
}

export interface Keyframe {
  t: number;
  poseA: string;
  poseB: string;
  hipA: [number, number];
  hipB: [number, number];
  facingA: 1 | -1;
  facingB: 1 | -1;
  camera: CameraState;
  ease: Easing;
}

// Canvas center is (WIDTH/2, HEIGHT*0.62) for the "ground line".
const GROUND_Y = HEIGHT * 0.66;

export const KEYFRAMES: Keyframe[] = [
  // Intro: both fighters off-screen
  {
    t: 0,
    poseA: "offstage",
    poseB: "offstage",
    hipA: [-300, GROUND_Y],
    hipB: [WIDTH + 300, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.0, x: 0, y: 0 },
    ease: "linear",
  },
  // Walk-in to center stage
  {
    t: 2.6,
    poseA: "idle_guard",
    poseB: "idle_guard",
    hipA: [WIDTH * 0.36, GROUND_Y],
    hipB: [WIDTH * 0.64, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.0, x: 0, y: 0 },
    ease: "easeOut",
  },
  // On guard, tense beat, slow push-in
  {
    t: 3.3,
    poseA: "on_guard_tense",
    poseB: "on_guard_tense",
    hipA: [WIDTH * 0.36, GROUND_Y],
    hipB: [WIDTH * 0.64, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.12, x: 0, y: -10 },
    ease: "easeInOut",
  },
  // A jabs forward
  {
    t: 3.9,
    poseA: "jab",
    poseB: "dodge_lean",
    hipA: [WIDTH * 0.36, GROUND_Y],
    hipB: [WIDTH * 0.66, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.18, x: -40, y: -20 },
    ease: "snap",
  },
  // B counters, lands hit on A's face (impact)
  {
    t: 4.6,
    poseA: "hit_recoil_face",
    poseB: "jab",
    hipA: [WIDTH * 0.34, GROUND_Y],
    hipB: [WIDTH * 0.64, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.35, x: 60, y: -30 },
    ease: "snap",
  },
  // Recover, reset to guard, camera pulls back
  {
    t: 6.0,
    poseA: "idle_guard",
    poseB: "idle_guard",
    hipA: [WIDTH * 0.36, GROUND_Y],
    hipB: [WIDTH * 0.64, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.05, x: 0, y: 0 },
    ease: "easeInOut",
  },
  // A throws a round kick, B blocks
  {
    t: 7.2,
    poseA: "kick_round",
    poseB: "block",
    hipA: [WIDTH * 0.37, GROUND_Y],
    hipB: [WIDTH * 0.64, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.2, x: 30, y: -10 },
    ease: "snap",
  },
  // Block recoil, brief reset
  {
    t: 7.7,
    poseA: "idle_guard",
    poseB: "block_recoil",
    hipA: [WIDTH * 0.36, GROUND_Y],
    hipB: [WIDTH * 0.65, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.1, x: 0, y: 0 },
    ease: "easeOut",
  },
  // B spinning back-kick, lands heavy on A's body (big impact + knockback)
  {
    t: 8.6,
    poseA: "hit_recoil_body_heavy",
    poseB: "kick_round",
    hipA: [WIDTH * 0.30, GROUND_Y - 6],
    hipB: [WIDTH * 0.62, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.45, x: -80, y: -30 },
    ease: "snap",
  },
  // Slow-motion stagger, dramatic hold
  {
    t: 11.0,
    poseA: "stagger",
    poseB: "idle_guard",
    hipA: [WIDTH * 0.27, GROUND_Y],
    hipB: [WIDTH * 0.62, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.5, x: -120, y: -40 },
    ease: "easeInOut",
  },
  // Both charge to center, camera whips to wide
  {
    t: 12.6,
    poseA: "idle_guard",
    poseB: "idle_guard",
    hipA: [WIDTH * 0.42, GROUND_Y],
    hipB: [WIDTH * 0.58, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.0, x: 0, y: 0 },
    ease: "easeIn",
  },
  // Mid-air clash (both jump-kick into each other) - massive impact
  {
    t: 13.7,
    poseA: "jump_kick_attacker",
    poseB: "jump_kick_defender",
    hipA: [WIDTH * 0.46, GROUND_Y],
    hipB: [WIDTH * 0.54, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.4, x: 0, y: -60 },
    ease: "snap",
  },
  // Both land, stagger back, dramatic pause
  {
    t: 15.2,
    poseA: "land_stagger",
    poseB: "land_stagger",
    hipA: [WIDTH * 0.38, GROUND_Y],
    hipB: [WIDTH * 0.62, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.08, x: 0, y: 0 },
    ease: "easeOut",
  },
  // Hold the pause
  {
    t: 16.3,
    poseA: "idle_guard",
    poseB: "idle_guard",
    hipA: [WIDTH * 0.38, GROUND_Y],
    hipB: [WIDTH * 0.62, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.1, x: 0, y: -10 },
    ease: "easeInOut",
  },
  // B flurry jab 1
  {
    t: 16.8,
    poseA: "flurry_recoil",
    poseB: "flurry_jab_b",
    hipA: [WIDTH * 0.36, GROUND_Y],
    hipB: [WIDTH * 0.63, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.25, x: 50, y: -20 },
    ease: "snap",
  },
  // B flurry jab 2
  {
    t: 17.3,
    poseA: "flurry_recoil",
    poseB: "flurry_jab_a",
    hipA: [WIDTH * 0.355, GROUND_Y],
    hipB: [WIDTH * 0.63, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.3, x: 60, y: -25 },
    ease: "snap",
  },
  // B flurry jab 3 (final, hardest)
  {
    t: 17.8,
    poseA: "hit_recoil_face",
    poseB: "flurry_jab_b",
    hipA: [WIDTH * 0.34, GROUND_Y],
    hipB: [WIDTH * 0.63, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.4, x: 70, y: -30 },
    ease: "snap",
  },
  // A staggers down to one knee
  {
    t: 19.2,
    poseA: "kneel",
    poseB: "idle_guard",
    hipA: [WIDTH * 0.34, GROUND_Y],
    hipB: [WIDTH * 0.62, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.2, x: -40, y: 20 },
    ease: "easeOut",
  },
  // Hold the kneel - dramatic low-angle beat
  {
    t: 20.6,
    poseA: "kneel",
    poseB: "idle_guard",
    hipA: [WIDTH * 0.34, GROUND_Y],
    hipB: [WIDTH * 0.62, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.25, x: -40, y: 30 },
    ease: "linear",
  },
  // A rises with a power-up surge
  {
    t: 21.8,
    poseA: "powerup",
    poseB: "idle_guard",
    hipA: [WIDTH * 0.36, GROUND_Y],
    hipB: [WIDTH * 0.62, GROUND_Y],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.15, x: 0, y: -10 },
    ease: "easeOut",
  },
  // A unleashes the finishing uppercut - massive flash
  {
    t: 22.7,
    poseA: "uppercut",
    poseB: "ko_fly",
    hipA: [WIDTH * 0.40, GROUND_Y],
    hipB: [WIDTH * 0.66, GROUND_Y - 40],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.6, x: 80, y: -60 },
    ease: "snap",
  },
  // B flies and lands
  {
    t: 24.6,
    poseA: "victory_pose",
    poseB: "ko_ground",
    hipA: [WIDTH * 0.40, GROUND_Y],
    hipB: [WIDTH * 0.78, GROUND_Y + 30],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 1.0, x: 0, y: 0 },
    ease: "easeOut",
  },
  // Final hero shot - victory pose, slow zoom out
  {
    t: 30,
    poseA: "victory_pose",
    poseB: "ko_ground",
    hipA: [WIDTH * 0.40, GROUND_Y],
    hipB: [WIDTH * 0.78, GROUND_Y + 30],
    facingA: 1,
    facingB: -1,
    camera: { zoom: 0.92, x: -20, y: 10 },
    ease: "easeInOut",
  },
];

// ---------------------------------------------------------------------------
// One-off effects: shake, flash, particle bursts, text cards
// ---------------------------------------------------------------------------

export interface ShakeEvent {
  time: number;
  duration: number;
  intensity: number;
}

export const SHAKE_EVENTS: ShakeEvent[] = [
  { time: 4.6, duration: 0.3, intensity: 10 },
  { time: 7.2, duration: 0.18, intensity: 5 },
  { time: 8.6, duration: 0.45, intensity: 18 },
  { time: 13.7, duration: 0.5, intensity: 24 },
  { time: 16.8, duration: 0.18, intensity: 8 },
  { time: 17.3, duration: 0.18, intensity: 8 },
  { time: 17.8, duration: 0.35, intensity: 14 },
  { time: 22.7, duration: 0.7, intensity: 30 },
];

export interface FlashEvent {
  time: number;
  duration: number;
  peakOpacity: number;
  color: string;
}

export const FLASH_EVENTS: FlashEvent[] = [
  { time: 4.6, duration: 0.18, peakOpacity: 0.35, color: "#ffffff" },
  { time: 8.6, duration: 0.22, peakOpacity: 0.5, color: "#ffe9c2" },
  { time: 13.7, duration: 0.28, peakOpacity: 0.7, color: "#ffffff" },
  { time: 17.8, duration: 0.18, peakOpacity: 0.4, color: "#ffffff" },
  { time: 22.7, duration: 0.45, peakOpacity: 1.0, color: "#fff6e0" },
];

export interface ImpactBurst {
  time: number;
  duration: number;
  x: number; // canvas-relative x at the moment of impact
  y: number;
  scale: number;
  color: string;
}

export const IMPACT_BURSTS: ImpactBurst[] = [
  { time: 4.6, duration: 0.5, x: WIDTH * 0.38, y: GROUND_Y - 220, scale: 1.0, color: "#ffd28a" },
  { time: 8.6, duration: 0.6, x: WIDTH * 0.34, y: GROUND_Y - 90, scale: 1.4, color: "#ffb27a" },
  { time: 13.7, duration: 0.7, x: WIDTH * 0.5, y: GROUND_Y - 160, scale: 1.8, color: "#ffffff" },
  { time: 17.8, duration: 0.5, x: WIDTH * 0.37, y: GROUND_Y - 220, scale: 1.1, color: "#ffd28a" },
  { time: 22.7, duration: 0.9, x: WIDTH * 0.5, y: GROUND_Y - 280, scale: 2.4, color: "#fff2cf" },
];

export interface TextCard {
  text: string;
  subtext?: string;
  from: number;
  to: number;
  size: "title" | "huge";
}

export const TEXT_CARDS: TextCard[] = [
  { text: "ROUND ONE", from: 0, to: 2.6, size: "title" },
  { text: "K.O.!", from: 22.7, to: 25.0, size: "huge" },
  { text: "VICTORY", from: 26.5, to: 30, size: "title" },
];

// SFX timeline reference (consumed by the audio synthesis script, not the renderer)
export interface SfxEvent {
  time: number;
  type:
    | "bell"
    | "whoosh"
    | "hit_light"
    | "hit_block"
    | "hit_heavy"
    | "hit_clash"
    | "hit_ko"
    | "powerup";
}

export const SFX_EVENTS: SfxEvent[] = [
  { time: 0.05, type: "bell" },
  { time: 3.9, type: "whoosh" },
  { time: 4.6, type: "hit_light" },
  { time: 7.2, type: "hit_block" },
  { time: 8.6, type: "hit_heavy" },
  { time: 12.6, type: "whoosh" },
  { time: 13.7, type: "hit_clash" },
  { time: 16.8, type: "hit_light" },
  { time: 17.3, type: "hit_light" },
  { time: 17.8, type: "hit_heavy" },
  { time: 21.8, type: "powerup" },
  { time: 22.7, type: "hit_ko" },
  { time: 29.3, type: "bell" },
];
