import { AbsoluteFill } from "remotion";
import { StatCard } from "../components/StatCard";

interface Stat {
  label: string;
  value: number;
  color: string;
}

interface Props {
  stats: Stat[];
}

export const StatsScene: React.FC<Props> = ({ stats }) => (
  <AbsoluteFill
    style={{
      justifyContent: "center",
      alignItems: "center",
      gap: 48,
      flexDirection: "row",
      fontFamily: "Helvetica, Arial, sans-serif",
    }}
  >
    {stats.map((stat, i) => (
      <StatCard
        key={stat.label}
        label={stat.label}
        value={stat.value}
        color={stat.color}
        delayInFrames={i * 12}
      />
    ))}
  </AbsoluteFill>
);
