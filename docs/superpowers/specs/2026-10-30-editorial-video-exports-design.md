# Editorial Video Formats and Style — Design

**Intent:** Make OpenMontage produce an original, evidence-led newsroom explainer in the visual grammar of the Pollar films, with one or both phone-vertical and desktop-HD deliverables selectable before production.

## Goals

- Add an approval-stage multi-select for `social_vertical` (9:16, 1080×1920; Reels/TikTok/Shorts) and `youtube_landscape` (16:9, 1920×1080). Both are checked for new proposals; the user may deselect either, but not both.
- Render each selected profile as its own aspect-specific MP4 from the same approved script, timeline, narration and assets. Record every file in the existing `render_report.outputs` array.
- Add a separate reusable editorial-data-explainer playbook: flat near-black field, muted light text, one restrained yellow highlight, maps/satellite evidence, diagrams, timelines, progressive reveals, measured pacing and restrained audio.
- Preserve existing playbooks and Backlot behavior. An opt-in flat background setting applies only to the new style; declared chart palettes flow through both renderers.

## Non-goals and boundaries

- No Backlot controls/API; production choices stay in the existing proposal approval flow.
- No new TTS provider, API key, or model download. Recommend a voice path separately: Pollar identifies ElevenLabs but does not publish its voice ID; this implementation does not clone a voice or copy its brand.
- No AI-generated depictions presented as documentary evidence. Keep original branding, script, maps and data presentation.
- No automatic crop of a landscape master to make the vertical deliverable; render each target at its selected dimensions.

## Approaches considered

1. **Proposal multi-select + existing renderer, selected.** The user chooses targets in the approval proposal; the composer calls the existing single-profile renderer once per target and collects the results. This matches OpenMontage's agent-first workflow and keeps the observer board read-only.
2. **Backlot as an export editor, rejected.** Real persisted controls require a write-capable UI/API and change Backlot's documented role as a read-only observer.
3. **Render once, crop for the second target, rejected.** Cropping a landscape scene can discard labels, maps and chart content; the two aspect ratios need their own layout passes.

## Production and compatibility decisions

- Register a generic `social_vertical` profile instead of treating TikTok's platform duration/file-size limits as universal social limits. Reuse the existing `youtube_landscape` profile for desktop HD.
- Store selected profiles in `proposal_packet.production_plan.output_profiles`, with a non-empty, unique enum list. Old proposals without the field retain their current single-target behavior.
- Write distinct, profile-named files under the project's `renders/` directory. Each render reuses approved media and the same edit decisions, while composition is laid out/rendered for that profile's aspect ratio.
- Remotion and HyperFrames consume the new playbook's declared chart palette and flat-background treatment; playbooks without that setting keep their existing ambient background.
- The new playbook is recommended for `animated-explainer`; existing playbooks remain unchanged.

## Evidence and voice guidance

The reference Reel captions identify @pollar.news. Their matching Pollar films are [the Finland satellite investigation](https://pollar.news/en/films/forest) (2:54) and [the Yandex data-centre explainer](https://pollar.news/en/films/bet) (2:47). I inspected their downloaded site versions and ran OpenMontage's local reference analyzer. Both use data-specific visual sequences rather than generic generated news footage; exact font, music, effects, and voice ID are not documented. Pollar's [AI policy](https://pollar.news/en/ai-policy) names ElevenLabs as its synthetic-voice provider.

For a first voice audition, use the already integrated Google Chirp 3 HD route; Google's current pricing page lists up to 1 million characters of free usage, then $30 per million characters, with billing enabled. The bundled local Piper route costs $0 per generation but the project marks it as less expressive. ElevenLabs is the closest provider match to Pollar, but its Free plan has no commercial license; use a paid plan for monetized/commercial publishing. Do not claim an exact voice match without an identified, authorized voice.

## Acceptance

- The proposal visibly offers both checked output choices and accepts either or both, rejecting an empty selection.
- Selected profiles yield separate files at exactly 1080×1920 and/or 1920×1080; report entries name the format and dimensions.
- The new playbook renders a flat near-black field in Remotion and provides equivalent flat-background/chart tokens to HyperFrames.
- Existing playbooks without `background_effect: flat` retain their ambient background treatment.
- The new playbook loads and validates; existing playbooks and historical single-target runs remain valid.
- The existing `remotion-composer/package-lock.json` user modification remains untouched.
