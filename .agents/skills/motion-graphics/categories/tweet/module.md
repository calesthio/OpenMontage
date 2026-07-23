# tweet — category module (search-driven)

**Search a tweet → animate the tweet card.** Grounded in a real post (RWA). ~4–8s.

## Source (Step 2)

RWA `search_tweets` (specific query, or a given tweet URL/id) → tweet: author, handle, avatar, text, timestamp, metrics (likes/reposts). `asset_needs`: `{ kind: tweet, query|source, treatment: none }`. Freeze the avatar + any embedded media.

## Vocabulary / leans on

- Block: registry **`x-post`** (animated X/Twitter post card overlay with engagement metrics) — reuse it directly.
- Primitives: card slide/scale-in · text type-on / line reveal · avatar pop · metrics **count-up** · optional emphasis on a keyword.

## Build (reuse-first)

`npx hyperframes add x-post` → fill author / handle / avatar / text / metrics from the resolved tweet; animate the card in, type-on the text (or line-by-line reveal), count-up the metrics. Frozen project-local avatar/media (never a remote URL). `export: alpha-overlay` if it's meant to sit over other footage.
