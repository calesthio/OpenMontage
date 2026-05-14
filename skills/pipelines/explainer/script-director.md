# Script Director — Explainer Pipeline

## When to Use

You are the Script Writer for a generated explainer video. You have a `brief` artifact from the Idea Explorer. Your job is to write a narration script from scratch — there is no existing footage to transcribe.

The script is the backbone of the video. Every visual, every scene, every audio cue flows from what you write here. A mediocre script cannot be saved by great visuals.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/script.schema.json` | Artifact validation |
| Prior artifact | `proposal_packet` | Selected concept with title, hook, key_points, core_message, tone, narrative_structure, duration |
| Prior artifact | `research_brief` (optional but high-value) | Data points, audience insights, expert quotes — ground the script in real facts |
| Playbook | Active style playbook from `proposal_packet.selected_concept.suggested_playbook` | Voice style, pacing rules |
| Layer 3 | TTS provider skills (check `agent_skills` on the selected TTS tool) | TTS capabilities for speaker directions |

## Process

### Step 1: Absorb the Proposal and Research

Read the `proposal_packet.selected_concept` carefully. Extract:
- **Target duration** — this is your word budget (see timing table below)
- **Hook** — your opening must deliver on this promise
- **Key points** — these must all be covered in the script
- **Core message** — the one thing the viewer should remember
- **Tone** — shapes word choice, sentence length, formality
- **Target audience** — shapes complexity and assumed knowledge
- **Narrative structure** — the structural approach (myth_busting, journey, data_narrative, etc.)

Then read the `research_brief` for grounding material:
- **`data_points`** — specific statistics and facts to weave into the script. Use claims with `surprise_factor: "surprising"` or `"counterintuitive"` as retention anchors.
- **`audience_insights.misconceptions`** — if the narrative structure is `myth_busting`, these are your myth/reality pairs.
- **`audience_insights.common_questions`** — address these directly in the script where they naturally fit.
- **`expert_voices`** — quotable experts add authority. Use sparingly — one or two per script.
- **`trending.recent_developments`** — if timely, reference them to make the content feel current.

**The research_brief is your cheat sheet.** Every fact, every surprising stat, every misconception is pre-verified and sourced. Use them. A script that cites "73% of developers..." (from research) is more compelling than one that says "many developers..."

### Step 2: Deepen Research Where Needed

The Research Director has already done the heavy lifting — you have a `research_brief` full of sourced facts. Your job here is targeted:

1. **Verify and update**: If any data point from the research_brief feels stale or uncertain, re-search to confirm.
2. **Fill script-specific gaps**: The research gives you broad facts. You may need a specific analogy, a precise technical detail, or a better example for a particular section.
3. **Find the best explanation**: How do the best educators (3Blue1Brown, Kurzgesagt, Fireship, Veritasium) explain this concept? What analogies work?
4. **Source quotable moments**: If the research_brief's expert_voices section has useful quotes, use them. If not, search for one strong quote to anchor a key section.

**Do NOT duplicate the Research Director's work.** If the research_brief already has 6 data points, you don't need to find 6 more. Focus on script-level needs: the right word, the right analogy, the right sequence.

### Step 3: Plan the Narrative Arc

Before writing prose, plan the structure. Every explainer script follows a dramatic arc:

```
HOOK (0-5s)     → Grab attention. Question, bold claim, or surprising fact.
                   NEVER: "In this video, we'll learn about..."
                   NEVER: "Hey guys, welcome back..."

SETUP (5-15s)   → Why should the viewer care? Create a knowledge gap.
                   Show the problem or the question. Make them NEED the answer.

BUILD (15-Xs)   → Progressive revelation. Each section builds on the last.
                   Use "therefore / but" transitions, NOT "and then."
                   South Park rule: "This happened, THEREFORE that happened,
                   BUT then this complication arose..."

CLIMAX (X-5s before end) → The "aha" moment. Everything clicks into place.
                            This is the payoff for the setup's knowledge gap.

LANDING (last 5s) → Quick recap of core message + CTA.
                     Don't introduce new information here.
```

Map each of the brief's `key_points` to a specific section in the BUILD phase.

### Step 4: Write the Script

Write each section with these fields:

```json
{
  "id": "s1",
  "label": "Hook",
  "text": "Your database searches every single row. Every. Single. One. What if it didn't have to?",
  "start_seconds": 0,
  "end_seconds": 5,
  "speaker_directions": "Emphasize 'every single row' with measured pacing. Brief pause before the question.",
  "enhancement_cues": [
    {
      "type": "animation",
      "description": "Database table with rows highlighted one by one, slowing down as count increases",
      "timestamp_seconds": 1
    }
  ],
  "pronunciation_guides": []
}
```

#### Timing Estimation

| Pace | Words/minute | Use when |
|------|-------------|----------|
| Conversational | ~150 wpm | Default for most explainers |
| Contemplative | ~120 wpm | Complex topics, need processing time |
| Energetic | ~180 wpm | Short-form, high-energy, TikTok/Reels |
| Technical | ~130 wpm | Code walkthroughs, architecture deep-dives |

**Word budget by duration:**
- 30s video → ~65-75 words
- 60s video → ~130-150 words
- 90s video → ~195-225 words
- 120s video → ~260-300 words

Count your words. If you're 20%+ over budget, the TTS will either rush or exceed duration. Cut ruthlessly.

#### Speaker Directions

Write directions that TTS can actually implement. Reference ElevenLabs capabilities:

| Direction | TTS Implementation |
|-----------|-------------------|
| "Speak slowly, with emphasis" | Lower speed setting, stability boost |
| "Excited, picking up pace" | Higher speed, higher style setting |
| "Pause for 1 second" | SSML `<break time="1s"/>` |
| "Whisper" | SSML whisper tag (model-dependent) |
| "Emphasize THIS word" | Note for post-processing or SSML emphasis |

Avoid directions TTS can't do: "smile while speaking", "gesture toward screen", "look at camera."

#### Cover Policy and Direction

Decide whether the video needs a cover/poster frame while writing the script.
Do not ask the user for every routine project; apply the workflow rules below
and only escalate when the cover affects brand, external distribution, or a
page's first impression.

Default to `cover_policy.required: true` when:

- the video will be embedded on a page, list, knowledge base, install page, or
  product page where it appears static before playback;
- the video will be shared externally or in a feed;
- the video is marketing, education, tutorial, product demo, sales enablement,
  or an executive/meeting opener;
- the user explicitly mentions cover, poster, first frame, thumbnail, or
  "what shows before playback";
- the first rendered frame is likely to be black, blank, loading, transitional,
  or too weak to represent the video.

Default to `cover_policy.required: false` for internal drafts, technical smoke
tests, TTS auditions, motion tests, source-footage-only processing, and other
non-distribution intermediates.

Use `user_decision: "review_final_cover"` when the user should see the final
cover before delivery. Use `approve_before_publish` for brand-sensitive
external releases. Use `none` only when skipping the cover or when the workflow
can safely proceed without user review.

Then add `cover_direction` when a cover is required. It gives production a
clear first impression to design toward, while the publish stage picks or
generates the final cover after the completed video can be reviewed.

Add a top-level `cover_direction` object when the video will be distributed in
a feed, embedded on a landing page, or shown before playback:

```json
{
  "cover_policy": {
    "required": true,
    "reason": "Video will be embedded on a product page before playback",
    "user_decision": "review_final_cover",
    "first_frame_mode": "replace_first_frame",
    "triggers": ["page_embed", "product_marketing"]
  },
  "cover_direction": {
    "primary_message": "The one idea a viewer should understand before pressing play",
    "visual_anchor": "The strongest visual motif or frame family to build around",
    "title": "Short cover title",
    "subtitle": "Optional supporting line",
    "style_notes": "High-contrast glass UI, product name visible, no tiny text",
    "candidate_source": "generated_image",
    "avoid": ["generic stock imagery", "text-heavy layouts"]
  }
}
```

Treat this as creative intent. The publish stage may use the final render,
`cover_direction`, and platform needs to create a final poster image or replace
the video's first frame for static embeds. `candidate_source` is a planning
hint only; it may point to a rendered frame, generated image, generated video
frame, source-footage frame, or manual design.
#### Enhancement Cues

Every section should have at least one enhancement cue. These tell the Scene Planner and Asset Generator what visuals to create.

| Cue Type | When to Use | Example |
|----------|-------------|---------|
| `overlay` | Key term, definition, label | "Show 'embedding' definition overlay" |
| `diagram` | Process, architecture, flow | "Mermaid flowchart: query → encode → search → rank" |
| `stat_card` | Surprising number or comparison | "Display: 1ms vs 500ms search time" |
| `animation` | Concept that needs motion to understand | "Animate vectors moving through high-dimensional space" |
| `code_snippet` | Code example | "Show Python: `results = collection.query(embedding)`" |
| `broll` | Real-world context | "Show examples of apps using vector search" |

**Density rule**: At least one enhancement cue every 8-10 seconds. A 60-second video should have 6-8 cues minimum. Viewers disengage if the visual doesn't change.

#### Pronunciation Guides

For technical terms, acronyms, and non-English words:

```json
{"word": "FAISS", "phonetic": "FACE"},
{"word": "Qdrant", "phonetic": "kuh-DRANT"},
{"word": "cosine", "phonetic": "CO-sign"}
```

### Step 5: Validate Against Playbook

Read the active style playbook and verify:

| Playbook Field | Script Impact |
|----------------|---------------|
| `identity.pace` | Match word density. `contemplative` = fewer words, longer pauses |
| `audio.voice_style` | Shape tone of speaker directions |
| `motion.pacing_rules` | E.g., "hold establishing shots for 2s minimum" affects section timing |
| `identity.mood` | Word choice: `warm` uses casual language; `professional` uses precise language |

### Step 6: Self-Evaluate

Score your script (1-5):

| Criterion | Question |
|-----------|----------|
| **Hook power** | Would someone stop scrolling in the first 3 seconds? |
| **Word count accuracy** | Within ±10% of target for the duration? |
| **Narrative flow** | Does each section build on the last? "Therefore/but" not "and then"? |
| **Enhancement density** | At least one cue every 8-10 seconds? |
| **Jargon management** | Technical terms explained or have pronunciation guides? |
| **Climax payoff** | Does the aha moment deliver on the hook's promise? |
| **CTA relevance** | Is the call to action specific and actionable? |

If any dimension scores below 3, revise before submitting.

### Step 7: Submit

Call `handle_explainer_script(state, {"script": script_json})` to validate and persist.

### Mid-Production Fact Verification

If you encounter uncertainty during script writing:
- Use `web_search` to verify factual claims before committing them to the script
- Use `web_search` to find reference images for visual accuracy
- Log verification in the decision log: `category="visual_accuracy_check"`

Every factual claim in the script should be traceable to the `research_brief`.
If you make a claim that isn't in the research, do additional research and
add the source. Do not invent statistics, dates, or attributions.

## Common Pitfalls

- **Writing too many words**: The #1 failure. TTS pacing is fixed. If you write 250 words for a 60-second video, either the audio will be rushed or the video will be 100 seconds. Count your words.
- **Front-loading information**: The hook should create curiosity, not dump information. "HTTPS uses TLS 1.3 with AEAD ciphers" is a terrible opening. "The padlock icon doesn't mean what you think it means" is compelling.
- **Missing enhancement cues**: A script without visual direction is a podcast script. Every section needs at least one cue telling the visual team what to show.
- **Generic speaker directions**: "Read naturally" is useless. "Start measured and precise, then accelerate through the list to convey scale" is actionable.
- **Forgetting the audience**: A script for CTOs should use different words than one for high schoolers, even if covering the same concept.
- **No transitions between sections**: Each section should have a logical bridge to the next. The viewer should never think "wait, why are we talking about this now?"

## Example: Well-Written Section

```json
{
  "id": "s3",
  "label": "The Core Idea",
  "text": "Instead of matching keywords, vector databases convert everything — text, images, audio — into lists of numbers called embeddings. Similar things get similar numbers. So finding related content becomes a math problem: which numbers are closest?",
  "start_seconds": 15,
  "end_seconds": 28,
  "speaker_directions": "Measured pace through 'text, images, audio' with slight pause between each. Speed up slightly on 'similar things get similar numbers' — it should feel like a revelation. Brief pause before the final question.",
  "enhancement_cues": [
    {
      "type": "animation",
      "description": "Show text/image/audio icons transforming into number arrays (embeddings). Arrays cluster by similarity in a 2D space.",
      "timestamp_seconds": 16
    },
    {
      "type": "stat_card",
      "description": "Display: 'Everything becomes numbers. Similar things → similar numbers.'",
      "timestamp_seconds": 22
    }
  ],
  "pronunciation_guides": [
    {"word": "embeddings", "phonetic": "em-BED-ings"}
  ]
}
```
