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

// ---------------------------------------------------------------------------
// Theme font registry (audit 2026-07-16, Wave 1)
//
// THEMES / playbook-derived ThemeConfigs declare fonts by name ("Inter",
// "IBM Plex Sans", "Noto Serif JP", …) but nothing ever LOADED them — only
// Space Grotesk / Playfair / Noto Sans SC had loadFont() calls, so on a
// render host every other theme font silently fell back to the system sans
// and theme "typography" was fiction. Components resolve theme font names
// through themeFont() below, which lazily loads the real Google Font on
// first use (memoized) and always appends the CJK fallback.
// ---------------------------------------------------------------------------

import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadSpaceGrotesk } from "@remotion/google-fonts/SpaceGrotesk";
import { loadFont as loadIBMPlexSans } from "@remotion/google-fonts/IBMPlexSans";
import { loadFont as loadIBMPlexMono } from "@remotion/google-fonts/IBMPlexMono";
import { loadFont as loadJetBrainsMono } from "@remotion/google-fonts/JetBrainsMono";
import { loadFont as loadFiraCode } from "@remotion/google-fonts/FiraCode";
import { loadFont as loadNotoSerifJP } from "@remotion/google-fonts/NotoSerifJP";
import { loadFont as loadNotoSans } from "@remotion/google-fonts/NotoSans";
import { loadFont as loadPlayfair } from "@remotion/google-fonts/PlayfairDisplay";

// Loader per theme-declarable font name. Importing a font module is cheap
// (metadata only); the network fetch happens on the loadFont() call, which
// runs at most once per name via the memo below. Options are inlined per
// call — each font package types its own weight/subset unions, so a shared
// options object doesn't typecheck.
const FONT_LOADERS: Record<string, () => string> = {
  "Inter": () => loadInter("normal", { weights: ["400", "500", "700"], subsets: ["latin"] }).fontFamily,
  "Space Grotesk": () => loadSpaceGrotesk("normal", { weights: ["400", "500", "700"], subsets: ["latin"] }).fontFamily,
  "IBM Plex Sans": () => loadIBMPlexSans("normal", { weights: ["400", "500", "700"], subsets: ["latin"] }).fontFamily,
  "IBM Plex Mono": () => loadIBMPlexMono("normal", { weights: ["400", "700"], subsets: ["latin"] }).fontFamily,
  "JetBrains Mono": () => loadJetBrainsMono("normal", { weights: ["400", "700"], subsets: ["latin"] }).fontFamily,
  "Fira Code": () => loadFiraCode("normal", { weights: ["400", "700"], subsets: ["latin"] }).fontFamily,
  "Playfair Display": () => loadPlayfair("normal", { weights: ["400", "700", "900"], subsets: ["latin"] }).fontFamily,
  "Noto Sans": () => loadNotoSans("normal", { weights: ["400", "500", "700"], subsets: ["latin"] }).fontFamily,
  "Noto Serif JP": () =>
    loadNotoSerifJP("normal", {
      weights: ["400", "700"],
      // The japanese subset is chunked like NotoSansSC — silence the
      // per-chunk warning, not the loading behavior.
      ignoreTooManyRequestsWarning: true,
    }).fontFamily,
};

const _loadedFonts = new Map<string, string>();

/**
 * Resolve a theme-declared font name to a genuinely loaded font-family stack
 * (with CJK fallback appended). Unknown names pass through as-is — they may
 * be a system font on the render host — still with the CJK fallback.
 */
export function themeFont(name: string | undefined | null, fallbackStack: string): string {
  if (!name) return withCjkFallback(fallbackStack);
  let family = _loadedFonts.get(name);
  if (family === undefined) {
    const loader = FONT_LOADERS[name];
    family = loader ? loader() : name;
    _loadedFonts.set(name, family);
  }
  return withCjkFallback(family);
}
