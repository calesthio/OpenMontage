# Music Director — Royalty-Free Candidate Selection

## Inputs

Required: approved videos and `product_copy`.

## Candidate Search

For each selected style call `pixabay_music` with
`operation="search"` and `max_results=3`. Query the approved style, for example
“elegant luxury product commercial” or “fresh natural lifestyle commercial”.

Present title, artist, duration, and license for all three candidates. Do not
download before selection and never auto-select the first result.

After the user chooses, call `operation="download"` with only that candidate's
Pixabay URL, `candidate_index`, title, artist, and duration. Write it under
`assets/music/<style>/selected.mp3`.

## Review

Confirm the track length, license, and project path. Present:

1. Use candidate 1, 2, or 3.
2. Search three new candidates.
3. Use user-supplied licensed music.
4. Stop and preserve the approved video/copy packages without final music muxing.

Create the draft `product_delivery` with all candidate metadata and the selected
track. 停止并等待用户审批，不要自动合成或替换候选音乐。
