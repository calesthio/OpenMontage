# Scene Director - Documentary Montage Pipeline

## When To Use

The brief exists. You now have to turn a thematic question into a
concrete list of SLOTS the retrieval layer can fill. Each slot is an
intention ("a silhouette at a doorway at dusk") plus the queries that
will find it in the real world (Pexels/Archive.org/NASA/Wikimedia/Unsplash).

This is the most creative stage in the pipeline. Retrieval is only as
good as the slot descriptions you write.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation |
| Prior artifact | `state.artifacts["idea"]["brief"]` | Thematic question, tone, duration, shape |
| Reference | `skills/pipelines/documentary-montage/executive-producer.md` | Cross-stage rules |
| Tools | none yet — this stage is pure planning | — |

## Mental Model

The scene director's job is NOT "pick clips". It is "describe what the
clips need to be plainly enough that CLIP can find them".

Think like a location scout, not a stock librarian.

- A stock librarian says: *"rain in the city montage, 15 clips"*.
- A location scout says: *"rain streaking sideways across a bus
  window at blue hour, passengers' faces in soft focus, traffic
  lights bleeding red and green through the glass"*.

The second one is what CLIP can actually rank. The first one is a
category label CLIP will match weakly and indiscriminately.

## Process

### 1. Turn The Shape Into A Beat Count

Read the brief's `duration_seconds` and `shape`. Derive the number of
slots. Use these defaults unless the tone says otherwise:

| Tone | Average hold | Slots per 60s |
|------|--------------|---------------|
| elegiac | 4.0s | ~15 |
| reverent | 3.5s | ~17 |
| dreamlike | 3.0s | ~20 |
| wry | 2.0s | ~30 |
| urgent | 1.2s | ~50 |

Then plan the arc according to shape:

- **list**: N uniform slots, no inflection.
- **before/after**: N/2 before slots + 1 pivot slot + N/2 after slots.
- **three-act**: setup (30%) → turn (40%) → release (30%).
- **single-image expansion**: 1 anchor image + N variations around it.

Write the beat count down before writing any slot.

### 2. Decompose The Thematic Question Into Concrete Beats

Take the ONE thematic question from the brief and answer it in
sensory language. Not themes — textures.

**Example — "What does rain show you about a city?"**

Bad decomposition (abstract, unsearchable):

- "establishing the mood of the city"
- "the feeling of being caught in weather"
- "the universality of rain"

Good decomposition (concrete, searchable):

- a single raindrop hitting dry asphalt in slow motion
- an umbrella opening in a doorway, a hand visible
- neon signs reflected upside-down in a puddle
- rain streaking across a bus window, passengers soft
- a taxi roof light pushing through heavy rain, long lens
- a storm drain swallowing leaves and water, overhead
- a street vendor pulling plastic over a produce cart
- steam rising off wet cobblestones under tungsten streetlight
- a child's rubber boot stamping into a puddle
- a lit apartment window seen through sheets of rain

Each of those is a SHOT. Each is CLIP-rankable. Each is also *a
different angle on the same idea*, which is what gives a list-shaped
montage its weight.

### 3. Write The Slot Description

Every slot carries a `description` field. This is the text CLIP will
embed and rank against. Write it like a good stock-footage tag string
— nouns and adjectives, no verbs of intention, no emotion words.

**Template:**

```
<subject>, <action/pose>, <environment>, <lighting>, <era/texture hint>
```

**Good:**

- `"a single raindrop hitting dry asphalt, close up, slow motion,
  warm streetlamp glow"`
- `"empty city sidewalk at night after rain, reflected neon,
  handheld, 1970s grain"`
- `"an umbrella opening in a doorway, hand visible, diffused
  afternoon light, shallow focus"`

**Bad:**

- `"the feeling of arriving home"` — emotion word, no subject
- `"a warm welcoming moment"` — adjective soup, no image
- `"someone going through a door in a symbolic way"` — intent, no shot

Rule of thumb: if you can't imagine a specific photograph from the
description, CLIP can't either.

### 4. Write 2-3 Queries Per Slot

The slot description is what CLIP ranks against. The queries are what
the `corpus_builder` uses to populate the candidate pool. These are
different jobs, so write them differently.

Give each slot a `queries` array with 2-3 entries:

1. **Literal query** — the most direct stock-search phrase. This is
   what a Pexels user would type. `"raindrop on asphalt slow motion"`.
2. **Lateral query** — the same idea from a different angle or scale.
   `"wet pavement close up"`.
3. **Association query** (optional, for hero slots) — an adjacent
   concept that might surface texture clips the literal query misses.
   `"first rain city street"`.

Short queries beat long queries for stock search engines. 2-5 words
each. No filler words.

### 5. Target Sources Per Slot (Era-Aware)

Read `brief.era_mix`. Assign each slot one or more `preferred_sources`
based on what footage lives where:

| Source | Strengths | Use when |
|--------|-----------|----------|
| `pexels` | Modern HD footage, clean shots, people, cities, nature | Default for modern/any era |
| `pixabay_video` | Large community library, nature, people, technology, lifestyle | Gap-fills when Pexels misses; broad general footage |
| `coverr` | Curated cinematic B-roll, nature, urban, abstract backgrounds | High-quality establishing shots, mood-setters, modern lifestyle |
| `mixkit` | Curated HD/4K by Envato, nature, business, technology | Premium-feel B-roll, clean nature footage, no attribution needed |
| `archive_org` | Prelinger home movies, mid-century educational film, 1940s-1980s texture | Vintage, wry, dreamlike, anything nostalgic |
| `nara` | U.S. National Archives — WWII, Cold War, Apollo, civil rights, presidential | Historical American documentary, military, government, space race |
| `loc` | Library of Congress — early cinema, newsreels, cultural recordings | Pre-1928 public domain footage, American history, folk traditions |
| `pond5_pd` | Pond5 Public Domain — WWI/WWII, early cinema, historical speeches | Archival/vintage footage, Méliès, Edison, newsreels |
| `videvo` | 90K+ free clips, nature, aerial, city, abstract, time-lapses | Large free library, complements Pexels with different contributors |
| `nasa` | Earth-from-orbit, astronomy, flight, scale imagery | Reverent, anything about scale, space, planet, flight |
| `esa` | European space missions, Hubble/Webb imagery, Earth observation | European space content, complements NASA for non-U.S. missions |
| `jaxa` | Japanese space missions, Hayabusa, ISS Kibo module, H-IIA rockets | Asian space content, unique angle on space exploration |
| `noaa` | Deep-sea ROV footage, marine life, coral reefs, weather, hurricanes | Ocean/underwater, unique deep-sea content, weather phenomena |
| `dareful` | Boutique 4K nature — mountains, forests, waterfalls, time-lapses | High-quality nature B-roll, consistent visual style, aerial shots |
| `wikimedia` | Commons photos and CC video, civic/documentary/public-event coverage | Public spaces, landmarks, protests, city texture, educational footage |
| `unsplash` | Polished editorial stills, lifestyle, product-adjacent photography | Modern still-image support shots when motion footage is thin |

If `era_mix = "vintage"`, bias slots toward `archive_org` and write
queries in period-appropriate vocabulary ("commuter", "housewife",
"suburb" not "influencer", "wfh", "coworking").

If `era_mix = "any"`, mix sources per slot — the scene director
decides which slot gets which source based on the beat's meaning.

#### Children's / Fairy-Tale Content

When the brief's `tone` or `target_audience` indicates children's
content (fairy tale, bedtime story, kids' explainer, animated story),
**switch the visual strategy from real footage to AI-generated fantasy
clips on Pixabay**.

Pixabay's community library contains thousands of AI-generated fantasy
animations (glowing forests, enchanted landscapes, magical creatures)
that dramatically outperform real footage for children's engagement.

**Query rewriting rules for children's content:**

| Slot intent | Real-footage query | Fantasy rewrite |
|-------------|-------------------|-----------------|
| Garden / nature | `garden flowers morning` | `enchanted fairy tale garden glowing magical` |
| Insects / creatures | `caterpillar leaf close up` | `fairy tale caterpillar magical forest glowing` |
| Transformation / cocoon | `chrysalis butterfly cocoon` | `magical chrysalis enchanted tree glowing` |
| Butterfly / flight | `butterfly flying sky` | `fantasy butterfly glowing magical wings` |
| Sunset / landscape | `sunset landscape golden` | `enchanted fantasy landscape magical sunset` |
| Rain / weather | `rain leaves gentle` | `fairy tale rain magical forest enchanted` |
| Night sky / stars | `milky way timelapse` | `fantasy night sky magical stars enchanted` |
| Ocean / water | `river water golden` | `magical underwater world fairy tale` |
| Mountains / aerial | `mountain peaks golden` | `fantasy mountain castle fairy tale magical` |
| Forest / trees | `forest path morning` | `fairy tale mushroom forest glowing enchanted` |

**Source routing:** Set `preferred_sources: ["pixabay_video"]` for ALL
slots. Pixabay is the only free source with a deep AI-generated fantasy
library. Do not mix real footage with fantasy — the style clash breaks
immersion for children.

**Keywords that surface AI fantasy content:** `fairy tale`, `fantasy`,
`enchanted`, `magical`, `glowing`, `dreamy`, `mystical`, `fairy`,
`enchanted forest`, `magical world`.

### 6. Mark Hero Slots

Every montage has 2-3 slots the whole piece depends on: the opening
image, the turn, the final image. Mark these with `hero: true` in the
slot metadata.

Hero slots get:

- longer holds (2-4s instead of the tone's default),
- bigger candidate pools at asset time (k=30 instead of k=10),
- more queries (3 instead of 2).

### 7. Leave Headroom For The Asset Stage

Don't over-specify. The asset director's job is to rank candidates
against your description. If you nail down the description AND the
exact clip, you've done the asset director's job badly and pre-empted
its creative choices.

Rule: describe the slot the way you would describe it to a research
assistant over the phone — specific enough to recognise, loose enough
to surprise you.

### 8. Record The Shot List

Use the `scene_plan.schema.json` artifact with one `scene` per slot.
For this pipeline, put documentary-montage-specific fields inside
`metadata` on each scene. The canonical shape:

```json
{
  "version": "1.0",
  "scenes": [
    {
      "id": "slot_01",
      "type": "broll",
      "description": "a single raindrop hitting dry asphalt, close up, slow motion, warm streetlamp glow",
      "start_seconds": 0.0,
      "end_seconds": 3.5,
      "narrative_role": "establish_context",
      "hero_moment": true,
      "texture_keywords": ["wet", "slow motion", "streetlamp"],
      "required_assets": [
        { "type": "video", "description": "raindrop on asphalt", "source": "source" }
      ]
    }
  ],
  "metadata": {
    "pipeline": "documentary-montage",
    "shape": "list",
    "tone": "elegiac",
    "thematic_question": "What does rain show you about a city?",
    "slots": [
      {
        "id": "slot_01",
        "description": "a single raindrop hitting dry asphalt, close up, slow motion, warm streetlamp glow",
        "hero": true,
        "preferred_sources": ["pexels", "archive_org"],
        "queries": [
          "raindrop on asphalt slow motion",
          "wet pavement close up",
          "first rain city street"
        ],
        "min_duration": 3.0,
        "target_hold_seconds": 3.5,
        "era_hint": "any"
      }
    ]
  }
}
```

The `scenes[]` array satisfies the schema. The `metadata.slots[]`
array is what the asset director actually reads — it carries the
retrieval-specific fields (`queries`, `preferred_sources`, `hero`,
`era_hint`) that `scene_plan.schema.json` doesn't know about.

### 9. Quality Gate

- Slot count matches the beat-count math from step 1.
- Every slot `description` follows the noun-and-adjective template —
  no emotion words, no verbs of intention.
- Every slot has 2-3 short queries (5 words or fewer each).
- At least 2 slots are marked `hero`.
- Sum of `target_hold_seconds` is within ±10% of `brief.duration_seconds`.
- If `era_mix = "vintage"`, at least 60% of slots list `archive_org`
  in `preferred_sources`.
- `metadata.thematic_question` echoes the brief verbatim (sanity check
  that you didn't drift).

## Common Pitfalls

- **Writing slot descriptions as intentions instead of images.** "A
  moment of hesitation before entering" is a screenplay direction, not
  a CLIP query. "A woman standing still on a porch, hand near the
  knob" is.
- **Category queries.** `"home"` and `"family"` match everything and
  nothing. Push for concrete nouns: door, mat, key, hall, shoe.
- **One-query slots.** The second query is cheap insurance — if the
  first query returns junk, the corpus still has something usable.
- **Forgetting duration math.** 90 elegiac seconds is ~15 holds of
  ~6s. If you wrote 40 slots, you've drafted an urgent piece by
  accident.
- **Skipping `era_hint` on a vintage brief.** Pexels will flood the
  corpus with 2020s HD footage and bury the Prelinger material.
- **Letting the thematic question drift.** If the brief says "coming
  home" and your slot list has three shots of airplanes, the piece
  will be about travel, not home. Re-read the brief after drafting.

## Worked Example — "A Minute in the Rain"

- Duration: 90s, elegiac tone → ~15 slots at ~6s each.
- Shape: list (catalogue of weather + city).
- Thematic question: "What does rain show you about a city?"

Sketch of slots (abbreviated):

1. **hero** single raindrop hitting dry asphalt, slow motion
2. umbrella opening in a doorway, diffused afternoon light
3. neon sign reflected upside-down in a puddle, handheld
4. rain streaking across a bus window, passengers soft focus
5. a taxi roof light pushing through heavy rain, long lens
6. storm drain swallowing leaves and water, overhead
7. a street vendor pulling plastic over a produce cart
8. wet cobblestone alley, steam rising, tungsten streetlamp
9. rooftop antennae against a grey sky, wide shot
10. a child's rubber boot stamping a puddle, low angle
11. **hero** a lit apartment window seen through sheets of rain
12. windshield wipers at night, colored city lights beyond
13. rain beading on a parked bicycle seat, macro
14. footprints filling with water on a tiled station floor
15. **hero** first patch of blue sky breaking through grey clouds

Each slot gets:

- `description` in the noun-and-adjective template,
- 2-3 short queries (e.g. slot 5: `"taxi heavy rain", "yellow cab
  wet street night", "city traffic downpour"`),
- `preferred_sources` (slots 1-6 → pexels+archive_org, slot 8 →
  archive_org for period texture, slot 11 → pexels),
- `hero: true` on slots 1, 11, 15,
- `target_hold_seconds` summing to ~90.

This is the artifact the asset director will run retrieval against.
