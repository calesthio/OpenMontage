// Split text into user-perceived characters (grapheme clusters) for
// per-letter animation.
//
// `text.split("")` splits UTF-16 code units. Once each piece sits in its own
// inline-block span, an emoji becomes two lone surrogates (each drawn as a
// U+FFFD box) and a Thai vowel or tone mark is torn from its consonant (drawn
// on a dotted circle). Both showed up in real renders on 2026-11-11.

type GraphemeSegmenter = {
  segment(input: string): Iterable<{ segment: string }>;
};
type GraphemeSegmenterCtor = new (
  locales?: string,
  options?: { granularity: "grapheme" },
) => GraphemeSegmenter;

export function splitGraphemes(text: string): string[] {
  const Segmenter = (Intl as unknown as { Segmenter?: GraphemeSegmenterCtor })
    .Segmenter;
  if (Segmenter) {
    const segmenter = new Segmenter(undefined, { granularity: "grapheme" });
    return Array.from(segmenter.segment(text), (part) => part.segment);
  }
  // No Intl.Segmenter: split by code point and keep combining marks (and
  // emoji joiners/variation selectors) on the character they modify.
  const out: string[] = [];
  for (const codePoint of Array.from(text)) {
    const joinsPrevious =
      /\p{M}/u.test(codePoint) || codePoint === "‍" || out[out.length - 1]?.endsWith("‍");
    if (out.length > 0 && joinsPrevious) {
      out[out.length - 1] += codePoint;
    } else {
      out.push(codePoint);
    }
  }
  return out;
}
