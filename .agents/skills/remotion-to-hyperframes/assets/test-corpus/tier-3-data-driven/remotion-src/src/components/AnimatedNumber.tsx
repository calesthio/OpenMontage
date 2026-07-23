import { interpolate, useCurrentFrame } from "remotion";

interface Props {
  from: number;
  to: number;
  durationInFrames: number;
}

/**
 * Counts from `from` to `to` over `durationInFrames` with easeOut.
 * Driven entirely by useCurrentFrame — deterministic.
 */
export const AnimatedNumber: React.FC<Props> = ({ from, to, durationInFrames }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // Ease-out cubic — fast start, slow finish, matches the ramp on data dashboards.
  const eased = 1 - (1 - t) ** 3;
  const value = Math.round(from + (to - from) * eased);
  return <>{value.toLocaleString()}</>;
};
