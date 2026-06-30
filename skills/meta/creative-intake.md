# Creative Intake

Before the research stage, gather user intent through targeted questions.
Do NOT start production on a vague brief.

## Input: intent_map

By the time you run, `intent-analyst` (Rule Zero step 1) has usually already produced an
`intent_map` with `explicit_intents`, `implicit_intents`, routed pipeline(s), and a list of
`open_ambiguities`. **Consume it:** treat `open_ambiguities` as your question list, and do
NOT re-decompose the request or re-derive intents that are already captured. Your job here
is only to close the gaps intent-analyst flagged — not to repeat the routing analysis.

## Required Questions (ask conversationally, not as a survey)

1. **Purpose**: What is this video FOR? (educate, sell, inspire, document, entertain)
2. **Audience**: Who will watch it? (age, expertise, context — "my team" vs "YouTube public")
3. **Platform**: Where will it live? (YouTube, internal Slack, social media, presentation, website)
4. **Tone**: What should it FEEL like? (serious, playful, cinematic, raw, warm, provocative)
5. **References**: Any videos you admire or want this to feel like?
6. **Outcome**: What should the viewer DO or FEEL after watching?
7. **Constraints**: Budget ceiling? Timeline? Must-include content?

## How to Ask

Don't dump all 7 questions at once. Start with purpose and audience,
then let the conversation flow. Fill in gaps naturally.

If the user gives a detailed brief, skip questions they've already answered.

Identify what the user has already told you. If they said "I want a
cinematic brand film for Instagram," you already have purpose (inspire/sell),
platform (Instagram), and tone (cinematic). Ask what's missing.

## Handling Vague Briefs

When the user says something like "make me a video about X":

1. Acknowledge the topic — show you understood.
2. Ask the single most important missing question first (usually purpose or audience).
3. Based on their answer, ask the next most important gap.
4. Stop asking when you have enough to start research. You don't need perfect answers — research will fill in details.

## Handling Detailed Briefs

When the user provides a multi-paragraph brief or a document:

1. Summarize what you understood (1-2 sentences).
2. Call out any gaps: "I have a clear picture of the audience and tone, but I'd love to know — is there a specific outcome you're hoping for?"
3. Confirm the platform and constraints if not stated.

## Output

Produce an `intake_brief` (informal, not schema-validated) that the
research stage uses as its starting context. Include:

- Direct quotes from the user where their language reveals intent
- Explicit answers to each of the 7 questions (mark any that were inferred vs stated)
- Any reference videos/images the user mentioned
- Constraints that must be honored (budget, timeline, must-include)

The intake_brief is passed as context to the research-director, not as a
formal artifact. It exists to prevent the research stage from inventing
intent that the user never expressed.

## Handling Reference Video Input

When the user provides a video URL or file as their starting point:

1. **Read the video-reference-analyst skill** (`skills/meta/video-reference-analyst.md`)
   and follow its protocol. Do not proceed with standard creative intake.

2. The VideoAnalysisBrief replaces the need for most intake questions — it provides
   tone, structure, pacing, audience signals, and style information directly from the
   reference.

3. The remaining intake questions are:
   - What topic/subject for YOUR version? (if different from reference)
   - How long?
   - Narration yes/no?
   - Budget ceiling?

4. Do NOT ask "what should it feel like?" — the reference video IS the answer to that
   question. Extract tone from the VideoAnalysisBrief instead.

## What NOT To Do

- Do not present a numbered survey. This is a conversation, not a form.
- Do not ask questions the user already answered in their initial message.
- Do not delay production unnecessarily — if the brief is clear, move on.
- Do not invent answers for questions the user didn't address. Mark them as "not specified" and let the research stage handle ambiguity.
- Do not assume the user wants an explainer. Many users want cinematic, animation, or source-led work. Listen for signals.
