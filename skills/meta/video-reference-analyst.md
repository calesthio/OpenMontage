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
user. This is NOT a raw dump. It's a conversational interpretation:

```
"I've watched the video. Here's what I see:

**Content:** [2-sentence summary of what the video is about]
**Style:** [1 sentence — pacing, visual treatment, energy]
**Structure:** [X scenes over Y seconds, pacing style]
**Motion:** [N of M scenes are motion clips / animated stills / static images.
This video uses [AI-generated video clips / still images with pan-zoom / a mix].]
**What makes it work:** [2-3 specific things — the hook technique, the pacing,
the visual transitions, the narration style]

Now let me check what I can do with your current setup..."
```

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

• Add FAL_KEY to .env → unlocks Kling 3.0, MiniMax, Wan (best for cinematic/sci-fi)
• Add REPLICATE_API_TOKEN → unlocks LTX Video (good for short clips)
• Proceed without video gen → I'll use stock footage + Remotion animations instead
  (different feel, but still works)

Which would you prefer?"
```

Read install_instructions from the registry for each unavailable tool — do NOT
hardcode key names or setup URLs.

### Step 3: Ask Critical Questions

Before proposing, gather what the VideoAnalysisBrief doesn't tell you:

1. "Do you want narration in your version, or visuals-only with music?"
2. "How long should your video be? The reference is [X] seconds."
3. "Is there a specific topic/subject you want, or should I riff on the
   same theme as the reference?"
4. "Any elements from the reference you specifically love or hate?"

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
- Composition: [Remotion (preferred when available) / FFmpeg (fallback only)]
- Motion: [video gen clips / Remotion spring animations on stills / etc.]

**Audio plan:**
- Narration: [yes/no, which TTS provider, voice style]
- Music: [library track / generated / none]
- Sound design: [any special audio needs]

**Duration:** [X seconds]
**Estimated cost:** $[X.XX] breakdown:
- Image generation: $X.XX (N images × $X.XX each via [provider])
- Video generation: $X.XX (N clips × $X.XX each via [provider])
- TTS narration: $X.XX (N words via [provider])
- Music: $X.XX ([source])
- Total: $X.XX

**Honest assessment:** [What this will look like realistically — don't oversell]
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

### Step 6: Enter Pipeline

After sample approval, enter the appropriate pipeline with:
- VideoAnalysisBrief as grounding context in the research/proposal stage
- User's chosen variant as the approved direction
- Sample feedback incorporated into the brief
- All creative differentiation decisions recorded in the decision_log

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
