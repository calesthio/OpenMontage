# Idea Director — Explainer Pipeline

## When to Use

You are the Idea Explorer for a generated explainer video. The user has provided a **topic or idea** (not raw footage). Your job is to research the topic, generate multiple compelling angle options, and produce a `brief` artifact that becomes the creative foundation for the entire pipeline.

This is the most important stage — a weak brief produces a weak video regardless of how good the tools are. Invest time here.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/brief.schema.json` | Artifact validation |
| Playbooks | `styles/*.yaml` | Visual/audio style options |
| Skills | `skills/meta/skill-creator.md` | If you encounter unfamiliar domain |

## Process

### Step 1: Understand the Request

Before doing anything, clarify the user's intent:

- **Topic**: What is the core subject? (e.g., "vector databases", "how HTTPS works", "why the sky is blue")
- **Audience**: Who is this for? (developers, general public, students, executives)
- **Platform**: Where will this be published? (YouTube, TikTok, Instagram, LinkedIn) — this constrains duration and style
- **Duration**: Target length. Defaults by platform: TikTok 30-60s, Instagram Reels 60-90s, YouTube 60-180s, LinkedIn 60-120s
- **Tone**: Casual, professional, educational, provocative, playful

If the user's request is vague (e.g., "make a video about AI"), ask targeted questions. Never guess when you can ask.

### Step 2: Research the Topic

**This step is mandatory.** Do not skip it. The research dossier is what separates a generic explainer from a compelling one.

Use web search to investigate:

1. **Existing content landscape**: Search YouTube and blogs for existing explainer videos on this topic. What angles have been covered? What's missing? What's been done to death?
2. **Trending discussions**: Search Reddit, X/Twitter, Hacker News, Stack Overflow for what people are currently asking or debating about this topic. What misconceptions exist? What surprises people?
3. **Key facts and data**: Find 3-5 surprising statistics, quotes, or facts that could anchor the video. Cite your sources.
4. **Visual inspiration**: How have the best creators visualized this concept? What analogies work? What diagrams are commonly used?
5. **Audience knowledge gaps**: What do most people get wrong about this topic? Where does the "aha moment" live?

**Output of this step**: A mental research dossier. You don't need to write it all down, but reference specific findings in your angle options.

### Step 3: Generate Angle Options

Generate **at least 3 genuinely different angles**. Not rewordings — structurally different approaches to the same topic.

For each angle, specify:

| Field | What | Quality Bar |
|-------|------|-------------|
| `name` | Short title (5-8 words) | Specific, not generic. "Why Vector Search Beats SQL LIKE" not "About Vector Databases" |
| `hook` | Opening line/question (under 15 words) | Must create curiosity or surprise in one sentence |
| `narrative_structure` | How the story unfolds | One of: analogy, problem-solution, journey, debate, myth-busting, timeline, comparison |
| `visual_approach` | Primary visual style | e.g., "animated diagrams with vector space visualizations" |
| `suggested_playbook` | Best-matching style playbook | Reference available playbooks in `styles/` |
| `target_audience` | Who this angle serves best | Specific: "mid-level developers evaluating databases" not "developers" |
| `why_this_works` | Rationale | Reference your research — why is this angle compelling right now? |

**Angle diversity checklist:**
- [ ] At least one angle is technical/detailed
- [ ] At least one angle is intuitive/accessible (uses analogy or story)
- [ ] At least one angle is provocative/surprising (challenges assumptions)
- [ ] No two angles use the same narrative structure
- [ ] Each angle suggests a different visual approach

### Step 4: Present to User and Select

Present all angle options clearly. Let the user:
- Select one as-is
- Ask you to combine elements from multiple angles
- Describe a custom direction entirely

If the user provides a custom direction, use it — but apply the research and quality bar from Steps 2-3.

### Step 5: Assemble the Brief

Build the `brief` artifact with all required and relevant optional fields:

```json
{
  "version": "1.0",
  "title": "...",
  "hook": "...",
  "key_points": ["...", "...", "..."],
  "core_message": "...",
  "cta": "...",
  "tone": "...",
  "style": "...",
  "target_audience": "...",
  "target_platform": "youtube|instagram|tiktok|linkedin|generic",
  "target_duration_seconds": 60,
  "reference_material": ["..."],
  "angle_options": [
    {"name": "...", "description": "..."},
    {"name": "...", "description": "..."},
    {"name": "...", "description": "..."}
  ],
  "selected_angle": "..."
}
```

**Field quality bar:**

| Field | Excellent | Mediocre |
|-------|-----------|----------|
| `title` | "How Vector Databases Find Your Data in 1ms" | "Vector Databases Explained" |
| `hook` | "Your database searches every single row. What if it didn't have to?" | "Today we'll learn about vector databases" |
| `key_points` | Concrete, specific claims the video will prove | Vague topics like "how it works" |
| `core_message` | One sentence the viewer should remember tomorrow | Absent or too broad |
| `cta` | Actionable and relevant: "Try building a similarity search with 10 lines of Python" | Generic: "Like and subscribe" |
| `tone` | Matches audience and platform | Mismatched (e.g., corporate tone on TikTok) |

### Step 6: Self-Evaluate

Before submitting, score your brief on this rubric (1-5 each):

| Criterion | Question |
|-----------|----------|
| **Hook strength** | Would someone stop scrolling for this? Does it create an information gap? |
| **Specificity** | Are key_points concrete claims, not vague topics? |
| **Research depth** | Does the brief reference real data, trends, or insights from Step 2? |
| **Audience fit** | Is the tone, complexity, and duration right for the target audience? |
| **Playbook match** | Does the selected style genuinely fit the content? |
| **Uniqueness** | Does this angle offer something the existing content landscape doesn't? |

If any dimension scores below 3, iterate before submitting. The reviewer will check the same criteria.

### Step 7: Submit

Call `handle_explainer_idea(state, {"brief": brief_json})` to validate and persist.

## Playbook Selection Guide

| Content Type | Recommended Playbooks | Why |
|--------------|----------------------|-----|
| Technical architecture | `minimalist-diagram` | Clean diagrams, whiteboard feel |
| Business/SaaS concept | `clean-professional` | Polished, trustworthy |
| Social media / quick explainer | `flat-motion-graphics` | Eye-catching, data-driven |
| Storytelling / narrative | Warm playbooks (Ghibli, Watercolor) | Emotional connection |
| Developer tutorial | `minimalist-diagram` or custom | Focus on code/diagrams |

If no existing playbook fits, describe the desired style in `brief.style` and the pipeline can create a custom playbook later.

## Common Pitfalls

- **Skipping research**: The #1 failure mode. Without research, angles are generic and hooks are weak.
- **Reworded angles**: Three variations of "explain how X works" are not three angles. Change the narrative structure.
- **Wrong duration for platform**: A 3-minute explainer doesn't work on TikTok. A 30-second video can't explain Kubernetes.
- **Ignoring the audience**: A video for CTOs needs different framing than one for junior developers, even on the same topic.
- **Vague key_points**: "How vector databases work" is a topic, not a key point. "Vector databases use high-dimensional math to find similar items in milliseconds" is a key point.

## Examples

### Good Angle Set (Topic: "How HTTPS Works")

**Angle 1: The Spy Analogy**
- Hook: "Every time you visit a website, you're having a secret conversation. Here's how."
- Structure: Analogy (spy/espionage metaphor)
- Visual: Animated characters passing secret messages
- Playbook: `flat-motion-graphics`
- Audience: General public, non-technical

**Angle 2: The Handshake Deep Dive**
- Hook: "The TLS handshake takes 100 milliseconds and involves 4 messages. Here's what each one does."
- Structure: Timeline/process walkthrough
- Visual: Technical diagram with packet animations
- Playbook: `minimalist-diagram`
- Audience: CS students, junior developers

**Angle 3: The Myth Buster**
- Hook: "The padlock icon doesn't mean what you think it means."
- Structure: Myth-busting (challenge assumption, then reveal truth)
- Visual: Split-screen before/after misconception
- Playbook: `clean-professional`
- Audience: Business professionals, security-aware users

### Bad Angle Set (same topic)

- Angle 1: "HTTPS Explained" — generic, no hook
- Angle 2: "How HTTPS Works" — same thing, reworded
- Angle 3: "Understanding HTTPS" — still the same, no structural difference

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
