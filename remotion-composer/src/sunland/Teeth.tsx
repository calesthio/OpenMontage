import React from "react";

/* Upper anterior teeth, drawn labially. The silhouette matters more than any
   amount of shading: a central incisor is narrow at the neck, widest in the
   middle third, and ends in a near-straight incisal edge with softened
   corners. Get that wrong and no gradient rescues it. */

export const CENTRAL =
  "M -34,2 C -40,22 -43,56 -42,80 C -41,98 -33,108 -19,111 L 19,111 " +
  "C 33,108 41,98 42,80 C 43,56 40,22 34,2 C 20,-4 -20,-4 -34,2 Z";
export const LATERAL =
  "M -25,6 C -30,24 -32,52 -31,72 C -30,88 -24,96 -13,99 L 13,99 " +
  "C 24,96 30,88 31,72 C 32,52 30,24 25,6 C 14,1 -14,1 -25,6 Z";

export const ToothDefs: React.FC = () => (
  <defs>
    {/* labial convexity: bright upper-left, falling away at the margins */}
    <radialGradient id="enamel" cx="36%" cy="24%" r="86%">
      <stop offset="0%" stopColor="#FFFFFF" />
      <stop offset="40%" stopColor="#FAF4EB" />
      <stop offset="74%" stopColor="#F2E8DA" />
      <stop offset="100%" stopColor="#E2D3BE" />
    </radialGradient>
    <radialGradient id="enamelBright" cx="36%" cy="24%" r="86%">
      <stop offset="0%" stopColor="#FFFFFF" />
      <stop offset="44%" stopColor="#FDFBF7" />
      <stop offset="78%" stopColor="#F6F1E9" />
      <stop offset="100%" stopColor="#E7E0D4" />
    </radialGradient>
    {/* the neck sits in shadow under the gum */}
    <linearGradient id="cervical" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="#B99C78" stopOpacity="0.55" />
      <stop offset="28%" stopColor="#B99C78" stopOpacity="0.12" />
      <stop offset="60%" stopColor="#B99C78" stopOpacity="0" />
    </linearGradient>
    {/* enamel is glass at the biting edge — it goes blue, not white */}
    <linearGradient id="incisal" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="#CFE0E6" stopOpacity="0" />
      <stop offset="66%" stopColor="#CBDDE4" stopOpacity="0.28" />
      <stop offset="100%" stopColor="#B6CDD8" stopOpacity="0.52" />
    </linearGradient>
    <linearGradient id="gumFade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="#F7EEE5" stopOpacity="1" />
      <stop offset="100%" stopColor="#F7EEE5" stopOpacity="0" />
    </linearGradient>
    <linearGradient id="gum" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="#D98C92" />
      <stop offset="55%" stopColor="#E7A3A6" />
      <stop offset="100%" stopColor="#D2777F" />
    </linearGradient>
    <linearGradient id="porcelain" x1="0.1" y1="0" x2="0.9" y2="1">
      <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.97" />
      <stop offset="45%" stopColor="#F2FAFC" stopOpacity="0.80" />
      <stop offset="100%" stopColor="#D5E6EC" stopOpacity="0.70" />
    </linearGradient>
  </defs>
);

/* one tooth: silhouette + form shading + cervical shadow + glassy edge */
export const Tooth: React.FC<{
  d: string; x: number; scale?: number; bright?: number; dim?: number;
}> = ({ d, x, scale = 1, bright = 0, dim = 0 }) => (
  <g transform={`translate(${x} 0) scale(${scale})`}>
    <path d={d} fill={bright > 0.5 ? "url(#enamelBright)" : "url(#enamel)"} />
    <path d={d} fill="url(#cervical)" />
    <path d={d} fill="url(#incisal)" />
    {/* specular band — narrow, offset, never centred */}
    <ellipse cx="-13" cy="34" rx="8.5" ry="25" fill="#FFFFFF" opacity={0.62 - dim * 0.4}
             transform="rotate(-7 -13 34)" />
    <path d={d} fill="none" stroke="#C9B295" strokeOpacity="0.45" strokeWidth="1.1" />
    {dim > 0 && <path d={d} fill="#A98A5F" opacity={dim * 0.26} />}
  </g>
);

/* gum arch with papillae between the teeth */
export const Gums: React.FC = () => (
  <g>
  <path
    d="M -230,-30 L 230,-30 L 230,10
       C 212,10 206,22 196,22 C 186,22 180,4 162,2
       C 142,0 134,20 122,20 C 110,20 104,-2 78,-4
       C 50,-6 44,18 26,18 L -26,18 C -44,18 -50,-6 -78,-4
       C -104,-2 -110,20 -122,20 C -134,20 -142,0 -162,2
       C -180,4 -186,22 -196,22 C -206,22 -212,10 -230,10 Z"
    fill="url(#gum)"
  />
  <rect x="-230" y="-30" width="460" height="22" fill="url(#gumFade)" />
  </g>
);

/* a veneer: the labial face only, thin, translucent, with a travelling sheen */
export const Veneer: React.FC<{ opacity: number; dy: number; sweep: number }> = ({
  opacity, dy, sweep,
}) => (
  <g opacity={opacity} transform={`translate(0 ${dy})`}>
    <defs>
      <linearGradient id="sheen" x1="0" y1="0" x2="1" y2="0.35">
        <stop offset={`${Math.max(0, sweep - 20)}%`} stopColor="#FFF" stopOpacity="0" />
        <stop offset={`${sweep}%`} stopColor="#FFF" stopOpacity="0.95" />
        <stop offset={`${Math.min(100, sweep + 20)}%`} stopColor="#FFF" stopOpacity="0" />
      </linearGradient>
      <clipPath id="vclip"><path d={CENTRAL} /></clipPath>
    </defs>
    <path d={CENTRAL} fill="url(#porcelain)" stroke="#FFFFFF" strokeWidth="1.8" strokeOpacity="0.95" />
    <rect x="-50" y="-16" width="100" height="140" fill="url(#sheen)" clipPath="url(#vclip)" />
  </g>
);
