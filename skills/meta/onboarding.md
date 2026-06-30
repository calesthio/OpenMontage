# Onboarding — Meta Skill

## When to Use

On the **very first interaction** with a user in a new session when the user has not yet specified a concrete production request — or when their request is vague ("make me a video", "what can you do?", "help me create something").

Skip this skill when the user arrives with a specific, actionable request like "Make a 60-second explainer about black holes." In that case, go directly to Rule Zero — which starts by running `skills/meta/intent-analyst.md` to route the request — then preflight and execute. The user already knows what they want.

**Handoff:** the moment an exploratory session turns into an actionable production request, stop orienting and run `intent-analyst` (Rule Zero step 1). Onboarding orients; intent-analyst routes.

**This skill transforms the agent from a passive executor into a creative partner.** Most users don't know what's possible. Your job is to show them — fast, clearly, and with copy-paste prompts they can try right now.

## Protocol

### Step 1: Run Preflight Discovery

Before saying anything creative, know what you're working with:

```bash
python -c "
from tools.tool_registry import registry
import json
registry.discover()
envelope = registry.support_envelope()
menu = registry.provider_menu()
print('=== ENVELOPE ===')
print(json.dumps(envelope, indent=2))
print('=== MENU ===')
print(json.dumps(menu, indent=2))
"
```

Parse the output into three buckets:

1. **Available** — tools with `status: AVAILABLE`
2. **Quick unlocks** — tools with `status: UNAVAILABLE` whose `install_instructions` reference an env var (1-minute fixes)
3. **Hardware unlocks** — tools requiring GPU or local model downloads

### Step 2: Determine the User's Setup Tier

Based on discovery, classify the setup:

| Tier | What's Available | Best Pipelines |
|------|-----------------|----------------|
| **Zero-key** | Piper TTS + Pexels/Pixabay stock (if keys added) + Remotion and/or HyperFrames + FFmpeg | Animated Explainer (stock visuals + free narration) |
| **Starter** | One configured image generation provider + free TTS + Remotion and/or HyperFrames | Animated Explainer, Animation (AI-generated visuals) |
| **Standard** | Image gen + TTS + music gen | Animated Explainer, Animation, Screen Demo, Hybrid |
| **Full** | Video gen + image gen + premium TTS + music | All pipelines including Cinematic, Avatar, Talking Head |
| **Full + GPU** | Cloud APIs + local video gen models | All pipelines with free local fallbacks |

**Composition runtimes** — both are first-class and surface as distinct
entries in the provider menu. Report each one's availability separately:

- **Remotion** requires Node.js + `npx` + `remotion-composer/` + `node_modules`.
  Best for React-based scene components (text cards, stat cards, charts),
  word-level captions, and the `TalkingHead` avatar composition.
- **HyperFrames** requires Node.js ≥ 22 + `npx` + FFmpeg. Consumed via
  `npx @hyperframes/cli` (no monorepo checkout required). Best for
  HTML/CSS/GSAP motion graphics — kinetic typography, product promos,
  launch reels, website-to-video workflows, registry blocks.

Name BOTH runtimes explicitly in the "Ready to go" summary when both are
available — not "Remotion" alone. A fresh-session agent that doesn't
mention HyperFrames by name will fail to present it at proposal time;
naming it here sets the expectation that the agent is runtime-agnostic.

If only one is available, note it in the summary and mention what the
other would unlock. If neither is available, tell the user their options
are FFmpeg-only (simple concat/trim) and what's needed to unlock HTML/React
composition.

**Do NOT pick a runtime during onboarding.** Runtime selection happens at
the proposal stage, after the agent understands the brief. During
onboarding you're reporting capabilities, not making production decisions.
See `AGENT_GUIDE.md` → "Present Both Composition Runtimes (HARD RULE)".

### Step 3: Greet and Orient

Present a **short, friendly capability summary**. Do NOT dump the raw provider menu. Instead, translate it into plain language.

**Template (adapt to actual discovery results):**

---

**Welcome to OpenMontage!** I'm your video production agent. Here's what I can do with your current setup:

**Ready to go:**
- [List 2-4 key capabilities in plain language, e.g., "Generate narration with free offline TTS (Piper)", "Create animated videos with spring transitions, captions, and charts (Remotion)", "Stock footage and images from Pexels"]

**Available pipelines:** [List the pipelines that work with their setup, with one-line descriptions]

**Quick upgrades:** [If applicable — summarize the best 1-2 unlocks from `provider_menu()` based on the user's missing capabilities and actual install instructions. Do not hardcode `FAL_KEY` or any provider as the default suggestion.]

---

**Rules for this presentation:**
- Lead with what WORKS, not what's missing. The user should feel empowered, not inadequate.
- Keep it to 8-12 lines max. Don't overwhelm.
- Mention at most 2 quick-unlock suggestions. Don't nag about every missing key.
- Read actual `install_instructions` from the registry — do not hardcode provider names or key names.

### Step 4: Offer Starter Prompts

Based on the user's tier, present **3 ready-to-use prompts** they can copy right now. These should be prompts that will work well with their specific setup and produce impressive results.

**Zero-key prompts:**

> **Try this now:** "Make a 45-second animated explainer about why the sky is blue"
>
> This will research the topic, write a script, find stock visuals, generate narration with Piper, and compose an animated video with transitions and captions — all free.

> **Also try:** "I have a screen recording of a dashboard workflow — make it a polished product demo with captions and a voiceover" *(Screen Demo pipeline)*

> **Or:** "Turn this interview recording into 3 short clips for TikTok and YouTube Shorts" *(Clip Factory pipeline)*

**Starter-tier prompts (image gen available):**

> **Try this:** "Create an animated explainer about how CRISPR gene editing works, with AI-generated visuals"
>
> I'll use your configured image generator to create custom visuals for each scene — much more visually striking than stock.

> **Also try:** "Make a short documentary-style video about urban beekeeping — keep it grounded and textural, not flashy" *(Hybrid pipeline — source + generated support)*

> **Or:** "Create a classroom-ready video teaching photosynthesis to 8th graders — simple, clear, and engaging" *(Explainer pipeline — teacher mode)*

**Full-tier prompts (video gen available):**

> **Try this:** "Create a cinematic 30-second trailer for a sci-fi concept: humanity receives a warning from 1000 years in the future"
>
> I'll generate actual motion video clips, compose a soundtrack, and deliver a finished cinematic trailer. *(Cinematic pipeline)*

> **Also try:** "Make a 60-second avatar spokesperson video announcing a company rebrand" *(Avatar Spokesperson pipeline)*

> **Or:** "I recorded a founder update on my webcam — make it feel polished, confident, and premium without looking fake" *(Talking Head pipeline)*

**Reference-based prompts (all tiers):**

> **Have a video you love?** Paste a YouTube link and say "make me something like this"
> — I'll analyze the style, pacing, and structure, then propose 2-3 creative variants
> you can choose from. Works with YouTube, Shorts, Instagram Reels, and TikTok.
> All analysis runs locally and free — no API keys needed.

> **Got your own footage?** Drop in a video file and say "I want to make a video using
> this footage" — I'll transcribe it, detect scenes, and propose an edit plan.

**Rules for prompt suggestions:**
- Present exactly 3 prompts.
- The first prompt should be the most impressive thing their setup can produce.
- Each prompt should target a different pipeline or style.
- Include a brief note explaining what makes this prompt a good fit for their setup.
- Use blockquote formatting so prompts are visually distinct and easy to copy.
- Always include the reference-based prompts above — they work at every tier.

### Step 5: Explain the Workflow (Briefly)

After prompts, give a 2-3 sentence summary of what happens when they start:

"When you give me a prompt, I'll first research the topic with live web searches, then present you with concept options and cost estimates. You pick your favorite, and I'll produce the video stage by stage — asking for your approval at each creative decision. The final video lands in `projects/<name>/renders/`."

Do NOT explain the full architecture, three-layer knowledge system, or pipeline internals here. That's for the curious — point them to `AGENT_GUIDE.md` if they want to go deeper.

### Step 6: Handle Follow-Up Questions

Common questions and how to respond:

**"What does it cost?"**
- Zero-key path: $0
- With one paid image/video provider configured: typically $0.30–$1.50 per video depending on asset count
- Full setup: $1–$3 for most videos
- Always: "I'll show you exact cost estimates before spending anything."

**"Can you make [specific type]?"**
- Match to a pipeline. If it fits, say which pipeline and what tools you'd use.
- If it doesn't fit any pipeline, be honest — suggest the closest match and explain what would be different.

**"How long does it take?"**
- Explainer (zero-key): 5-15 minutes
- Explainer (with image gen): 10-20 minutes
- Cinematic (with video gen): 20-40 minutes
- "Most of the time is asset generation. The research and scripting stages are fast."

**"I just want to test it quickly"**
- Suggest the shortest zero-key prompt: "Try: 'Make a 30-second explainer about why leaves change color.' It'll use free tools and finish in about 5 minutes."

**"Show me what you can do"**
- Point to the demo video in the README, then offer the starter prompts from Step 4.

## Anti-Patterns

- **Don't dump the raw JSON** from `support_envelope()` or `provider_menu()` on the user. Translate it into plain language.
- **Don't list every tool.** Group by capability ("I can generate images with FLUX" not "I have flux_image, google_imagen, openai_image, recraft_image...").
- **Don't explain the architecture** unless asked. "Agent-first, instruction-driven" is interesting to developers, but the user came to make a video, not study the codebase.
- **Don't apologize for missing capabilities.** Frame as "here's what you have" and optionally "here's a quick upgrade." Never "unfortunately you don't have..."
- **Don't skip straight to production** if the user seems uncertain or exploratory. Take 30 seconds to orient them — it saves 10 minutes of confusion later.
- **Don't suggest prompts that require tools the user doesn't have.** Every prompt must be achievable with their current setup. Mark any that need specific keys clearly.
