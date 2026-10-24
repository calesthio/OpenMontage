---
name: yt-shorts
description: >-
  Find the Shorts hiding inside a long video and write them, using the
  transcript to pick self-contained moments. Use for "cut this into shorts",
  "clip this", "repurpose this video", "what should I clip".
---

# yt-shorts

A Short cut out of a long video is not a clip of the best moment. [claim:yt-shorts-001]
It is a moment that **survives without the video around it**, which is a much smaller set. [claim:yt-shorts-002]

## Picking

Read the transcript and find spans of 20-55 seconds where all three are true: [claim:yt-shorts-003]

1. It opens on a complete thought. [claim:yt-shorts-004] If the first sentence needs the previous minute, it is not a Short. [claim:yt-shorts-005]
2. There is a turn in it - a claim, then something that complicates or proves it. [claim:yt-shorts-006]
3. It ends on a line, not a trail-off. [claim:yt-shorts-007]

Rank the candidates and show the user the top five with their timecodes and first line, so they can reject one without reading the whole transcript. [claim:yt-shorts-008]

## Writing each one

- **A NEW first line.** [claim:yt-shorts-009] The long video's line assumes context this viewer does not have. [claim:yt-shorts-010] Write the replacement and run it through `../yt-script/hookscore.py` (a hook-scoring tool, not a viral-score promise). [claim:yt-shorts-011]
- **On-screen text for the first two seconds**, different words from the spoken line. [claim:yt-shorts-012]
- **A loop point**: what the last line sets up so the first line answers it. [claim:yt-shorts-013]
- Vertical framing note - what gets cropped out of a 16:9 frame and whether that matters. [claim:yt-shorts-014]

## The gate

Nothing here publishes. [claim:yt-shorts-015] This skill writes and you publish. [claim:yt-shorts-016] Every output ends in a block the user copies, [claim:yt-shorts-017] and the last line of every run is the question: **ship it, or change it?** [claim:yt-shorts-018]
