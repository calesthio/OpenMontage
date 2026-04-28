# Video Reference Analyst — Meta Skill

## When to Use

When the user provides a video URL (YouTube, Shorts, Instagram, TikTok, or any URL)
or a local video file as a REFERENCE — meaning "make me something like this," not
"edit this footage."

If the user says "edit this video" or "cut this into clips," route to the appropriate
footage-led pipeline (clip-factory, talking-head, hybrid) instead. This skill is for
REFERENCE-based production.

## Detection Signals

Trigger this skill when:
- User pastes a YouTube/Shorts/Instagram/TikTok URL
- User says "something like this," "inspired by," "in this style," "similar to"
- User uploads a video and says "I want one like this"
- User says "I saw this video and want to make something like it"

Do NOT trigger when:
- User provides footage and says "edit this" or "cut this" → use source_media_review
- User provides audio and says "make a video for this" → standard pipeline
- User just wants a transcript → use TranscriptFetcher directly

## Protocol

### Step 1: Analyze the Reference

Run VideoAnalyzer with `analysis_depth: "standard"`:

```python
video_analyzer.execute({
    "source": "<url or path>",
    "analysis_depth": "standard",
    "max_keyframes": 20
})
```

Read the resulting VideoAnalysisBrief. Before proceeding, present a summary to the
user. This is NOT a raw dump. It's a conversational interpretation, and it MUST be
structured by the 5 aspects so downstream stages can lift fields directly:

```
"I've watched the video. Here's what I see:

**Content:** [2-sentence summary of what the video is about]
**Style:** [1 sentence — pacing, visual treatment, energy]
**Structure:** [X scenes over Y seconds, pacing style]
**Motion:** [N of M scenes are motion clips / animated stills / static images.
This video uses [AI-generated video clips / still images with pan-zoom / a mix].]

**5-aspect breakdown (per shot or per shot-group):**
- Subject: [type, count, attributes; subject transitions across shots: revealing / disappearing / switching / complex-alternating; or N/A]
- Subject Motion: [actions in temporal order; interactions; or N/A]
- Scene: [overlays (text/graphics) listed separately; POV (drone/OTS/macro/etc.); setting; time of day; dynamics]
- Spatial Framing: [shot size; subject position; depth; height-relative; how it changes]
- Camera: [playback speed; lens; height; angle; focus/DoF; steadiness; movement]

**What makes it work:** [2-3 specific things — the hook technique, the pacing,
the visual transitions, the narration style]

Now let me check what I can do with your current setup..."
```

The 5-aspect block above is the **canonical form** that `proposal-director`, `script-director`, and `scene-director` will read. Do not collapse it back into prose — keep the labels.

**Motion classification is critical.** The VideoAnalysisBrief now includes per-scene
`motion_type` ("motion_clip", "animated_still", "static_image") and `flow_variance`.
Use this to determine the production approach:

- If most scenes are `motion_clip` → the reference uses **video generation** (Kling,
  MiniMax, etc.) → plan around video gen tools, not image gen
- If most scenes are `animated_still` → the reference uses **still images with
  Ken Burns / pan-zoom** → image gen + Remotion/FFmpeg composition is appropriate
- If mixed → note which sections use motion and which use stills

**Never guess** whether a reference uses images or video. Read the `motion_type` field.
Getting this wrong leads to proposing the wrong pipeline and wrong tool path.

**Vision analysis:** After presenting the structural data, examine the extracted
keyframes yourself. You ARE a multimodal model — look at the keyframe images and
enrich the VideoAnalysisBrief with:
- Per-frame descriptions (subjects, text, composition, color)
- Cross-frame visual continuity and style consistency
- Genre classification and production quality assessment
- Color palette extraction (dominant colors across keyframes)
- Typography style if on-screen text is present
- Transition patterns visible between sequential keyframes

Update the brief's `content_analysis`, `style_profile`, and `replication_guidance`
fields with your visual observations. This is where the analysis becomes truly
comprehensive — the tools provide structure; your vision provides understanding.

### 5-Aspect Structured Output (MANDATORY)

The analyst's report MUST break down the reference video into the **five aspects** from the CMU/Harvard CHAI study (also the canonical structure used in `skills/creative/video-gen-prompting.md`). A narrative-only summary is no longer sufficient — downstream stages (proposal, script, scene-director) ingest the 5-aspect form directly without re-parsing prose.

**Decision-tree captioning policy.** For each detected shot, walk all five aspects in order:

> - **Subject:** type, attributes (count, age, role, costume, distinguishing features), multiple-subject disambiguation, transitions across shots (revealing / disappearing / switching / complex-alternating).
> - **Subject Motion:** actions in temporal order; group/interaction patterns (parallel, sequential, reactive); locomotion vs gesture vs facial.
> - **Scene:** **overlays separately** (text, lower thirds, graphics, watermark — call these out as their own layer, do not merge into setting) + POV (drone, aerial, OTS, macro, top-down, dashcam, FPV, handheld, locked-off) + setting + time of day + dynamics (weather, particles, crowd movement).
> - **Spatial Framing:** shot size (ECU/CU/MS/WS/EWS), subject position in frame, depth (foreground/midground/background usage), height-relative (above/at/below subject) — and how each of these **changes** across the shot if the camera or subject moves.
> - **Camera:** playback speed (real-time / slow-mo / time-lapse), lens distortion (anamorphic, fish-eye, tilt-shift), height (ground / eye / overhead), angle (high / low / Dutch), focus / DoF (rack focus, deep focus, shallow), steadiness (locked / handheld / gimbal), movement (push / pull / pan / tilt / dolly / truck / crane / orbit).
>
> **Mark any aspect explicitly as N/A** if it doesn't apply (e.g., "Subject: N/A — pure scenery shot," or "Scene overlays: N/A — no graphics"). **Silent omission is the most common analyst failure** and produces ambiguous downstream prompts.

See `skills/creative/video-gen-prompting.md` for primitive definitions and the canonical vocabulary used at every aspect.

### Step 2: Capability Audit

Run standard preflight:

```bash
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.support_envelope(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.capability_catalog(), indent=2))"
```

Map the reference video's requirements against available capabilities:

```
REFERENCE NEEDS          YOUR CAPABILITIES          GAP
─────────────────────    ─────────────────────      ──────────
Video clips (sci-fi)     Video gen: 0/12 configured BLOCKED without key
Narration (deep male)    TTS: ElevenLabs available  READY
Background music         Music: MusicGen available  READY
Composition engine       Remotion: available        READY (preferred)
                         FFmpeg: available          READY (fallback only)
```

**Composition engine priority:** Remotion is the **default** composition engine for
ALL final renders — video clips, images, animated scenes, mixed content. It embeds
video natively via `<OffthreadVideo>` and handles transitions, overlays, and profile
scaling in a single React render pass. FFmpeg is only used when Remotion is
unavailable, or for standalone operations (trim, transcode, subtitle burn) outside
the composition pipeline. **Never default to FFmpeg when Remotion is available.**

Be honest about gaps. If video generation is needed but unavailable, say so clearly:

```
"This reference uses generated sci-fi footage. Right now you don't have any video
generation providers configured. Here are your options:

• Add the gateway or provider key recommended by `provider_menu()` for video generation
• If multiple provider options are available, summarize the tradeoffs and recommend one based on the user's brief
• Proceed without video gen → I'll use stock footage + Remotion animations instead
  (different feel, but still works)

Which would you prefer?"
```

Read install_instructions from the registry for each unavailable tool — do NOT
hardcode key names, provider names, or setup URLs.

### Step 3: Ask Critical Questions

Before proposing, gather what the VideoAnalysisBrief doesn't tell you:

1. "Do you want narration in your version, or visuals-only with music?"
2. **If narration: lock the audio architecture now.** Ask:
   "How should the story be told? Options:
   • **Single narrator** — one voice tells the whole story (like a Pixar short)
   • **Character dialogue** — characters speak to each other, no narrator
   • **Narrator + character voices** — narrator drives the story, characters
     have occasional dialogue lines"
   This decision shapes the script, voice casting, and budget. It MUST be
   resolved before proposals — do not defer it to the script or compose stage.
3. "How long should your video be? The reference is [X] seconds."
4. "Is there a specific topic/subject you want, or should I riff on the
   same theme as the reference?"
5. "Any elements from the reference you specifically love or hate?"

Do NOT ask all at once. Lead with the most important gap. If the user's initial
message already answers some of these, skip those.

### Step 3b: Lightweight Research

**This step is mandatory.** Even with a clear reference video and user direction,
the agent must do targeted research before proposing concepts. Do NOT skip this
and rely solely on the reference analysis + your own knowledge.

Research scope (keep it focused — this is not the full research-director stage):

1. **Content landscape:** Search for 3-5 existing videos similar to what the user
   wants. What works? What's been overdone? What angles are fresh? This grounds
   your proposals in what's actually out there, not just what you imagine.

2. **Style/technique research:** Search for best practices relevant to the
   production approach:
   - If AI video gen: which models handle this subject best? Known prompting
     patterns? Character consistency techniques?
   - If animation: what animation styles suit this content?
   - If the reference has a distinctive technique: how is it achieved?

3. **Subject-matter research:** If the user's topic has factual content (science,
   history, how-things-work), gather 3-5 specific data points or facts that could
   make the video more interesting. Even for entertainment/comedy videos, research
   what makes similar content engaging (tropes, hooks, payoff patterns).

**How to present:** Don't dump raw research. Weave findings into your proposals:
- "I looked at similar channels — most food personification videos use X, so our
  twist of Y would stand out"
- "Kling handles anthropomorphic characters well when you use [specific technique]"
- "The top-performing 60-second comedy shorts all use a 3-beat structure: setup,
  escalation, unexpected payoff"

**Time budget:** 2-3 minutes of web search. This is a lightweight pass, not a
deep investigation. The full research-director stage runs later inside the
pipeline if needed.

### Step 4: Creative Proposals (2-3 variants)

MANDATORY: The agent must NEVER propose a carbon copy. The reference is inspiration,
not a template. Each proposal must have clear creative differentiation.

Use this structure for each variant:

```
## Option [A/B/C]: "[Title]"

**Inspired by:** [what it keeps from the reference — pacing, structure, tone]
**Creative twist:** [what it changes — angle, subject, visual treatment, hook]

**Visual plan:**
- Playbook: [closest match + customizations]
- Visual treatment: [how visuals will be created — which tools, which providers]
- Composition: [Remotion (default when available) / FFmpeg (fallback only)]
- Motion: [video gen clips / Remotion spring animations on stills / etc.]
- Clip duration strategy: [maximize clip duration to minimize API calls and cost.
  Most providers support 5s and 10s clips. Prefer 10s clips and consolidate
  adjacent scenes into single clips where narratively coherent. A 60s video
  needs 6×10s clips, not 12×5s — half the cost, fewer cuts, smoother motion.]

**Audio plan:**
- Audio architecture: [single narrator / character dialogue / narrator + characters]
- Voice casting: [voice name + ID for each role — narrator, character A, etc.]
- TTS provider: [selected from available providers via tts_selector preflight —
  Google Chirp3-HD (best value: near-free, expressive, 24kHz),
  ElevenLabs (voice cloning only), OpenAI gpt-4o-mini-tts (good with
  instructions param), Piper (offline/free). Do NOT hardcode a provider —
  run preflight to check what's configured and recommend the best available.
  **Default recommendation: Google Chirp3-HD** unless voice cloning is needed.]
- Music: [library track / generated / none]
- Sound design: [any special audio needs]

**Duration:** [X seconds]
**Estimated cost per provider option:**
Present a provider comparison table so the user can choose:
```
Provider        Quality    Speed      Cost (N clips)    Total
─────────      ────────   ─────      ──────────────    ─────
VEO 3.1        Highest    Slow       $X.XX             $X.XX
Kling Pro      High       Medium     $X.XX             $X.XX
Sora V2        High       Medium     $X.XX             $X.XX
LTX Distilled  Lower      Fastest    $X.XX             $X.XX
```
+ Image generation: $X.XX (N images × $X.XX each via [provider])
+ TTS narration: $X.XX (N words via [provider])
+ Music: $X.XX ([source])

**Do NOT pick the provider for the user.** Present the options with
costs, recommend one with a brief reason, and let them decide.

**Honest assessment:** [What this will look like realistically — don't oversell]

**Layer 3 skills:** [List the agent_skills from each tool that will be used.
  These MUST be read before writing any generation prompts. E.g.:
  - Video gen: `ai-video-gen` skill for provider-specific prompt patterns
  - Image gen: `flux-best-practices` for FLUX prompt engineering
  - TTS: `elevenlabs` or `openai-docs` for voice tuning
  Skipping Layer 3 skills is a governance violation.]
```

**Differentiation patterns:**

| Pattern | Example |
|---------|---------|
| **Same structure, different subject** | Reference: "How black holes work" → Ours: "How neutron stars work" with same pacing |
| **Same subject, different angle** | Reference: "Kubernetes explained" → Ours: "Kubernetes from a security engineer's POV" |
| **Same tone, different visual treatment** | Reference: stock footage + voiceover → Ours: animated motion graphics + voiceover |
| **Same content, different platform** | Reference: 10-min YouTube → Ours: 60-sec Shorts version with faster pacing |
| **Counter-take** | Reference: "Why AI will replace jobs" → Ours: "Why AI won't replace YOUR job" |

**Cost transparency is mandatory.** Each concept must include:
- Itemized cost estimate at the user's requested duration
- Cost broken down by: image gen, video gen, TTS, music, total
- Provider names for each cost line
- Honest note about what the budget buys vs. doesn't buy

**Recommendation:** Always recommend one option with a brief reason why. Don't leave
the user paralyzed with equal choices.

### Step 4b: Layer 3 Skill Gate (MANDATORY)

**Before ANY asset generation** (sample or full production), the agent MUST:

1. Read the **Layer 2 skill** for each tool from `skills/` directory (usage guidance, input schemas, best practices)
2. Check the `agent_skills` field on every tool that will be used
3. Read each referenced **Layer 3 skill** in `.agents/skills/` (provider-specific prompting)
4. Apply the provider-specific prompting guidance to all generation prompts

**NEVER read tool source code (*.py) to understand how to use a tool.**
Skills exist precisely so the agent doesn't need to read implementation code.
Layer 2 skills describe *what* and *when*. Layer 3 skills describe *how*.

This is NOT optional. The AGENT_GUIDE says: *"Layer 3 is not optional.
Every generation tool has an agent_skills field. Read them before writing
prompts."*

Example checklist before generating:
```
Tool              agent_skills              Read?
────────────      ────────────────────      ─────
video_selector    ai-video-gen              [ ]
flux_image        flux-best-practices       [ ]
elevenlabs_tts    elevenlabs, text-to-speech [ ]
video_compose     remotion-best-practices   [ ]
```

Do NOT proceed to Step 5 until all relevant Layer 3 skills are read.
The difference between a generic prompt and a skill-informed prompt is
the difference between "usable" and "cinematic."

### Step 5: Sample-First Production (MANDATORY)

After the user picks a variant, ALWAYS say:

```
"Great choice. Before I commit to the full [X]-second video, I'll produce a
10-15 second sample first — the opening hook + one middle scene. This lets you
hear the voice, see the visual style, and feel the pacing before we go all-in.

Estimated sample cost: $[X.XX]
Shall I proceed with the sample?"
```

The sample is NOT optional. Even if the user says "just do the whole thing," push
back gently:

```
"I'd really recommend the sample first — it's a tiny fraction of the cost and
lets us catch any style mismatches early. If you love it, I'll proceed to the
full video immediately."
```

Only skip the sample if the user insists after being advised.

**Sample contents:**
- 1-2 representative scenes (the hook + one middle scene)
- Actual TTS narration with chosen voice
- Actual generated/stock visuals
- Music bed snippet
- Subtitle style preview

**Sample checkpoint:**
Present the sample with: "Here's a preview. Does this feel right? Things I can
adjust: voice, visual style, pacing, music, colors."

Iterate on sample feedback until approved. Store samples at:
`projects/<name>/assets/sample/sample_v{N}.mp4`

### Step 6: Enter Pipeline (HARD REDIRECT)

After sample approval, the agent MUST enter the pipeline. This is not optional.

**Mandatory steps:**
1. Read the pipeline manifest: `pipeline_defs/animation.yaml` (or whichever
   pipeline matches the production type)
2. Execute **stage by stage** in order — research → proposal → script →
   scene_plan → assets → edit → compose → publish
3. Before EACH stage, read its director skill from
   `skills/pipelines/<pipeline>/<stage>-director.md`
4. Produce the required artifacts at each stage
5. Hit every checkpoint where `checkpoint_required: true`
6. Get user approval where `human_approval_default: true`

**Do NOT collapse stages.** Do not jump from "user approved proposal" to
"generate all assets." The pipeline stages exist to enforce quality gates,
artifact dependencies, and review checkpoints. Skipping them is a governance
violation.

**Context to carry into the pipeline:**
- VideoAnalysisBrief as grounding context in the research/proposal stage
- User's chosen variant as the approved direction
- Sample feedback incorporated into the brief
- All creative differentiation decisions recorded in the decision_log
- Audio architecture and voice casting decisions from Step 3
- Layer 3 skills already read from Step 4b

The pipeline takes over from here. The VideoAnalysisBrief travels alongside the
standard artifacts, providing reference grounding at every stage.

## Multiple Reference Videos

When the user provides multiple reference URLs:

1. Analyze each video separately (run VideoAnalyzer on each)
2. Present a comparative summary: "Video A does X well, Video B does Y well"
3. In proposals, note which elements are inspired by which reference
4. The VideoAnalysisBrief for the primary reference travels with the pipeline;
   secondary references are noted in the research_brief

## Error Handling

| Failure | Action |
|---------|--------|
| URL download fails | Report error, suggest: try another URL, provide local file, or proceed without reference |
| No captions available | Download video, transcribe with Whisper locally |
| Scene detection fails | Fall back to uniform frame sampling |
| All analysis fails | Ask user to describe the reference video verbally, proceed with standard creative intake |

Never silently skip analysis steps. If something fails, tell the user what happened
and what the impact is on the analysis quality.
