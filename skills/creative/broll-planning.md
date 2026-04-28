# B-Roll Planning for OpenMontage

> How to plan B-roll needs from a script, decide between stock and generated footage,
> construct effective search queries, and evaluate footage quality.

## When to Use

You are planning visual assets for a video and need supplementary footage (B-roll) to accompany
narration, establish context, or add visual variety. This skill teaches you when to reach for
stock footage vs. AI generation, and how to get good results from each.

## The Decision Matrix: Stock vs. Generated

| Scene Need | Prefer Stock | Prefer Generated |
|------------|-------------|-----------------|
| Real-world establishing shot (city, office, nature) | **Yes** — stock excels here | Only if no good stock match |
| People in realistic settings | **Yes** — generated humans often look uncanny | Only with high-quality models |
| Abstract concept visualization | No | **Yes** — AI can create what doesn't exist |
| Custom diagrams/infographics | No | **Yes** — use `diagram_gen` or `image_selector` |
| Branded/stylized imagery | No | **Yes** — AI matches your playbook style |
| Historical/archival footage | **Yes** — stock libraries have archives | No |
| Specific technical equipment | **Yes** — real photos are more credible | Only if equipment doesn't exist |
| Motion/action clips (waves, traffic, clouds) | **Yes** — stock video is perfect for this | AI video is catching up |
| Metaphorical imagery (growth, connection) | Either works | **Yes** — more creative control |

**Rule of thumb:** If the scene needs to look _real_, use stock. If it needs to look _specific to your concept_, generate it.

## Extracting B-Roll Needs from a Script

Walk the script section by section. For each section, ask:

1. **What is the narrator talking about?** — The subject suggests the visual.
2. **Is there an enhancement cue?** — The script writer may have embedded `[B-ROLL: ...]` cues.
3. **Does this section reference something concrete?** — "servers in a data center" → stock footage of servers.
4. **Does this section explain an abstract concept?** — "the algorithm weighs each factor" → generated diagram.
5. **How long is this section?** — Determines clip duration needed.

### Output: B-Roll Brief

For each identified need, create an entry:

```
Scene: s3 (15s-22s)
Need: Establishing shot of a modern data center
Source: stock
Keywords: ["data center", "server room", "rack servers blue light"]
Duration: 4-6 seconds
Orientation: landscape
Mood: cool, technological, clean
Fallback: AI-generated image of server racks
```

## Constructing Effective Stock Search Queries

### Query Construction Rules

1. **Be specific but not too specific.** "aerial city skyline sunset" works. "aerial shot of downtown San Francisco financial district at 6:47pm golden hour" returns nothing.

2. **Use 2-4 keywords.** Stock search is keyword-based, not semantic. More words = fewer results.

3. **Lead with the subject.** "ocean waves" not "beautiful calm serene ocean waves at dawn."

4. **Include the visual quality you need:**
   - Add "aerial" or "drone" for overhead shots
   - Add "close-up" or "macro" for detail shots
   - Add "timelapse" for time-lapse footage
   - Add "slow motion" for slow-mo clips

5. **Try synonyms on failure.** If "programmer coding" returns poor results, try "developer laptop" or "software engineer workspace."

### Query Templates by Scene Type

Add a **POV keyword** to every query. Stock libraries (Pexels, Pixabay, Storyblocks, Artgrid) explicitly index POV terms — drone, aerial, OTS (over-the-shoulder), macro, top-down, dashcam, FPV, handheld, locked-off — and adding the POV often unlocks better matches than refining the subject. The CMU/Harvard CHAI taxonomy treats POV as a first-class Scene aspect for the same reason: it changes which library shelf you're searching.

| Scene Type | Query Template | Example with POV |
|-----------|---------------|---------|
| Establishing | `[place] [time of day] [POV]` | "tokyo skyline night drone" |
| Activity | `[person] [action] [POV]` | "scientist microscope OTS" |
| Object | `[object] [style] [POV]` | "circuit board macro top-down" |
| Nature | `[element] [quality] [POV]` | "ocean waves aerial drone" |
| Abstract motion | `[movement] [style] [POV]` | "light trails timelapse locked-off" |
| Workplace | `[setting] [activity] [POV]` | "modern office meeting handheld" |

If the scene description doesn't already imply a POV, ask the script/scene director — don't default to "no POV." A wrong-POV match (handheld when the scene needs drone) is harder to fix than a wrong color grade.

## Evaluating Stock Footage Quality

When the stock tool returns results, evaluate before using:

### Image Criteria
- **Resolution:** Meets target (1080p minimum for video frames)
- **Relevance:** Actually depicts what the scene needs (not just keyword match)
- **Style compatibility:** Doesn't clash with the playbook's visual style
- **No watermarks:** Pexels/Pixabay are license-free, but verify
- **Composition:** Subject is well-framed, not cut off awkwardly
- **POV match:** Does the footage's actual POV (drone, OTS, macro, handheld, locked-off, etc.) match what the scene needs? A wrong POV — e.g., handheld when the scene wants drone — is **more costly to fix than a wrong color grade**. Reject and re-query rather than try to crop your way out of it.

### Video Criteria (all image criteria plus)
- **Duration:** At least as long as the scene needs (can trim, can't extend)
- **Motion:** Smooth, no jarring camera movement (unless that's the intent)
- **Frame rate:** Matches target output (24/30fps standard)
- **Audio:** Stock video audio is usually discarded — don't factor it in

### Scoring Heuristic

Rate each result 1-5:
- **5:** Perfect match, use immediately
- **4:** Good match, minor crop or trim needed
- **3:** Acceptable, would benefit from color grading to match playbook
- **2:** Marginal — try different keywords first
- **1:** Wrong — doesn't match the scene at all

**Threshold:** Use results scoring 3+. Below 3, refine the query or switch to generated.

## Failure Escalation

When stock search fails (no results or all score below 3):

1. **Retry with different keywords** — try synonyms, broader terms, or different angles
2. **Try the other stock provider** — Pexels and Pixabay have different libraries
3. **Switch to AI generation** — use `flux_image` or `openai_image` with the scene description
4. **Escalate to user** — "I couldn't find good stock footage for [scene]. Here are the best options: [show results]. Or I can generate an image instead. What do you prefer?"

The agent should only ask the user when both stock search AND generation fallback would produce suboptimal results. For most cases, the fallback chain handles it silently.

## Attribution Tracking

Both Pexels and Pixabay are free for commercial use with no required attribution.
However, best practice is to track sources in the asset manifest:

```json
{
  "id": "broll-scene-3",
  "type": "image",
  "source_tool": "pexels_image",
  "provider": "pexels",
  "attribution": {
    "photographer": "Joey Farina",
    "source_url": "https://www.pexels.com/photo/...",
    "license": "Pexels License"
  }
}
```

This data is available in the tool's response (`photographer`, `pexels_url` / `page_url`). Include it in the asset manifest for transparency.
