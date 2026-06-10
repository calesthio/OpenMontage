// Pose library for the stickman fight cinematic.
// Coordinates are local to each fighter's hip origin.
// x: positive = "facing direction" (multiplied by facing sign in the renderer)
// y: positive = downward (SVG convention)

export interface LimbPoint {
  x: number;
  y: number;
}

export interface Pose {
  torsoLean: number; // degrees, rotates torso+head around hip
  headTilt: number; // additional head rotation
  headOffsetX: number;
  headOffsetY: number;
  armL: LimbPoint;
  armR: LimbPoint;
  legL: LimbPoint;
  legR: LimbPoint;
  scaleX: number;
  scaleY: number;
  hipOffsetX: number; // local lunge offset
  hipOffsetY: number; // local jump/crouch offset
}

export const BASE_POSE: Pose = {
  torsoLean: 0,
  headTilt: 0,
  headOffsetX: 0,
  headOffsetY: 0,
  armL: { x: 35, y: 95 },
  armR: { x: -35, y: 95 },
  legL: { x: 35, y: 110 },
  legR: { x: -35, y: 110 },
  scaleX: 1,
  scaleY: 1,
  hipOffsetX: 0,
  hipOffsetY: 0,
};

function pose(overrides: Partial<Pose>): Pose {
  return { ...BASE_POSE, ...overrides };
}

export const POSES: Record<string, Pose> = {
  offstage: pose({}),

  idle_guard: pose({
    armL: { x: 80, y: -110 },
    armR: { x: -45, y: -85 },
    legL: { x: 35, y: 110 },
    legR: { x: -30, y: 112 },
  }),

  on_guard_tense: pose({
    torsoLean: 4,
    armL: { x: 90, y: -120 },
    armR: { x: -50, y: -95 },
    legL: { x: 45, y: 108 },
    legR: { x: -25, y: 114 },
    hipOffsetY: -4,
  }),

  jab: pose({
    torsoLean: 10,
    armL: { x: 175, y: -110 },
    armR: { x: -45, y: -90 },
    legL: { x: 60, y: 104 },
    legR: { x: -15, y: 116 },
    hipOffsetX: 18,
  }),

  dodge_lean: pose({
    torsoLean: -22,
    headTilt: -18,
    headOffsetY: -6,
    armL: { x: 70, y: -100 },
    armR: { x: -55, y: -90 },
    legL: { x: 55, y: 108 },
    legR: { x: -45, y: 114 },
    hipOffsetX: -14,
  }),

  hit_recoil_face: pose({
    torsoLean: -28,
    headTilt: -42,
    headOffsetX: -10,
    headOffsetY: -10,
    armL: { x: -70, y: -55 },
    armR: { x: 95, y: -35 },
    legL: { x: 50, y: 105 },
    legR: { x: -25, y: 116 },
    scaleX: 1.05,
    scaleY: 0.94,
    hipOffsetX: -16,
  }),

  kick_round: pose({
    torsoLean: -18,
    headTilt: -6,
    armL: { x: -80, y: -95 },
    armR: { x: 85, y: -75 },
    legL: { x: -10, y: 116 },
    legR: { x: 165, y: 10 },
    hipOffsetY: -22,
  }),

  block: pose({
    torsoLean: 6,
    armL: { x: 75, y: -95 },
    armR: { x: 60, y: -125 },
    legL: { x: 45, y: 108 },
    legR: { x: -35, y: 114 },
  }),

  block_recoil: pose({
    torsoLean: -8,
    armL: { x: 65, y: -90 },
    armR: { x: 50, y: -118 },
    legL: { x: 55, y: 105 },
    legR: { x: -45, y: 116 },
    hipOffsetX: -10,
    scaleX: 1.02,
    scaleY: 0.98,
  }),

  hit_recoil_body_heavy: pose({
    torsoLean: -38,
    headTilt: -20,
    headOffsetX: -14,
    armL: { x: -90, y: -40 },
    armR: { x: 110, y: -20 },
    legL: { x: 70, y: 95 },
    legR: { x: 100, y: 75 },
    scaleX: 1.12,
    scaleY: 0.85,
    hipOffsetX: -85,
    hipOffsetY: -10,
  }),

  stagger: pose({
    torsoLean: -12,
    headTilt: -10,
    armL: { x: 25, y: 80 },
    armR: { x: -30, y: 85 },
    legL: { x: 50, y: 108 },
    legR: { x: -55, y: 112 },
    hipOffsetX: -30,
    hipOffsetY: -4,
  }),

  jump_kick_attacker: pose({
    torsoLean: 14,
    headTilt: 6,
    armL: { x: -60, y: -120 },
    armR: { x: -90, y: -90 },
    legL: { x: -40, y: 70 },
    legR: { x: 175, y: -10 },
    hipOffsetX: 60,
    hipOffsetY: -150,
  }),

  jump_kick_defender: pose({
    torsoLean: -16,
    headTilt: -10,
    armL: { x: -90, y: -85 },
    armR: { x: -60, y: -120 },
    legL: { x: 165, y: -5 },
    legR: { x: -40, y: 75 },
    hipOffsetX: -60,
    hipOffsetY: -150,
  }),

  land_stagger: pose({
    torsoLean: -6,
    armL: { x: 60, y: -60 },
    armR: { x: -60, y: -55 },
    legL: { x: 70, y: 100 },
    legR: { x: -70, y: 100 },
    hipOffsetY: -6,
  }),

  flurry_jab_a: pose({
    torsoLean: 12,
    armL: { x: 180, y: -125 },
    armR: { x: -50, y: -90 },
    legL: { x: 55, y: 106 },
    legR: { x: -20, y: 116 },
    hipOffsetX: 16,
  }),

  flurry_jab_b: pose({
    torsoLean: 10,
    armR: { x: 180, y: -90 },
    armL: { x: -50, y: -125 },
    legL: { x: 55, y: 106 },
    legR: { x: -20, y: 116 },
    hipOffsetX: 16,
  }),

  flurry_recoil: pose({
    torsoLean: -22,
    headTilt: -30,
    headOffsetX: -8,
    headOffsetY: -8,
    armL: { x: -55, y: -50 },
    armR: { x: 80, y: -30 },
    legL: { x: 55, y: 104 },
    legR: { x: -35, y: 116 },
    scaleX: 1.03,
    scaleY: 0.96,
    hipOffsetX: -18,
  }),

  kneel: pose({
    torsoLean: 35,
    headTilt: 18,
    headOffsetY: 30,
    armL: { x: 40, y: 40 },
    armR: { x: -10, y: 60 },
    legL: { x: 5, y: 60 },
    legR: { x: -75, y: 100 },
    hipOffsetY: 70,
  }),

  powerup: pose({
    torsoLean: -4,
    headTilt: -12,
    headOffsetY: -8,
    armL: { x: 110, y: -210 },
    armR: { x: -110, y: -210 },
    legL: { x: 45, y: 108 },
    legR: { x: -45, y: 108 },
    scaleX: 1.06,
    scaleY: 1.1,
    hipOffsetY: -10,
  }),

  uppercut: pose({
    torsoLean: -14,
    headTilt: -10,
    armL: { x: 70, y: -240 },
    armR: { x: -55, y: -85 },
    legL: { x: 55, y: 105 },
    legR: { x: -20, y: 118 },
    hipOffsetX: 22,
    hipOffsetY: -28,
  }),

  ko_fly: pose({
    torsoLean: -65,
    headTilt: -50,
    headOffsetX: -20,
    armL: { x: -120, y: -10 },
    armR: { x: 130, y: 20 },
    legL: { x: 110, y: 40 },
    legR: { x: 140, y: 90 },
    scaleX: 0.95,
    scaleY: 0.92,
    hipOffsetX: -160,
    hipOffsetY: -120,
  }),

  ko_ground: pose({
    torsoLean: 82,
    headTilt: 70,
    headOffsetX: -40,
    headOffsetY: 30,
    armL: { x: -130, y: 30 },
    armR: { x: 90, y: 60 },
    legL: { x: 130, y: 30 },
    legR: { x: 150, y: 70 },
    hipOffsetX: -200,
    hipOffsetY: 120,
  }),

  victory_pose: pose({
    torsoLean: 0,
    headTilt: 6,
    headOffsetY: -6,
    armL: { x: 130, y: -230 },
    armR: { x: -130, y: -230 },
    legL: { x: 50, y: 110 },
    legR: { x: -50, y: 110 },
    scaleX: 1.04,
    scaleY: 1.06,
  }),
};

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function lerpPoint(a: LimbPoint, b: LimbPoint, t: number): LimbPoint {
  return { x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t) };
}

export function lerpPose(a: Pose, b: Pose, t: number): Pose {
  return {
    torsoLean: lerp(a.torsoLean, b.torsoLean, t),
    headTilt: lerp(a.headTilt, b.headTilt, t),
    headOffsetX: lerp(a.headOffsetX, b.headOffsetX, t),
    headOffsetY: lerp(a.headOffsetY, b.headOffsetY, t),
    armL: lerpPoint(a.armL, b.armL, t),
    armR: lerpPoint(a.armR, b.armR, t),
    legL: lerpPoint(a.legL, b.legL, t),
    legR: lerpPoint(a.legR, b.legR, t),
    scaleX: lerp(a.scaleX, b.scaleX, t),
    scaleY: lerp(a.scaleY, b.scaleY, t),
    hipOffsetX: lerp(a.hipOffsetX, b.hipOffsetX, t),
    hipOffsetY: lerp(a.hipOffsetY, b.hipOffsetY, t),
  };
}
