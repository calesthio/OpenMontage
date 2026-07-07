// Shared CJK font fallback for every text-rendering scene/component.
//
// Every scene in this package previously declared Latin-only font stacks
// (Space Grotesk / Playfair Display / Inter, subsets: ["latin"]). On a
// render host with no CJK system font installed, any Chinese/Japanese/
// Korean text passed into these components falls through to whatever the
// browser's font-matching happens to pick — commonly tofu boxes, and on
// some hosts a visually-plausible-but-wrong glyph substitution. This is
// the same class of bug that pushed at least one production to bake
// brand text directly into an AI-generated image instead (see
// skills/pipelines/cinematic/asset-director.md's "no baked-in text" rule)
// — which trades a font problem for a much worse one, since diffusion
// image models routinely render incorrect-but-plausible-looking CJK
// characters.
//
// Noto Sans SC is loaded once here (real Unicode text, real glyphs,
// deterministic) and appended to each component's font-family stack, so
// CJK characters resolve to it via normal per-character font-fallback
// while Latin text keeps using the display font.
import { loadFont as loadNotoSansSC } from "@remotion/google-fonts/NotoSansSC";

const { fontFamily: notoSansSC } = loadNotoSansSC("normal", {
  weights: ["400", "700"],
  subsets: ["chinese-simplified", "latin"],
  // The chinese-simplified subset ships as ~200 chunked woff2 files (Google
  // serves CJK fonts pre-split by codepoint range). We load the full set
  // deliberately, since scene text is arbitrary generated copy, not a known
  // fixed character list — this silences the resulting per-chunk warning
  // rather than changing the (intentional) loading behavior.
  ignoreTooManyRequestsWarning: true,
});

export { notoSansSC };

/** Appends the bundled CJK fallback to a font-family stack. */
export function withCjkFallback(stack: string): string {
  return `${stack}, ${notoSansSC}`;
}
