import { AbsoluteFill } from "remotion";
import { UnderlinedText } from "../components/UnderlinedText";

interface Props {
  text: string;
}

export const OutroScene: React.FC<Props> = ({ text }) => (
  <AbsoluteFill
    style={{
      justifyContent: "center",
      alignItems: "center",
      fontFamily: "Helvetica, Arial, sans-serif",
    }}
  >
    <UnderlinedText text={text} color="#fbbf24" />
  </AbsoluteFill>
);
