# BGM Montage Idea Director

## Deliverable

Create the standard OpenMontage brief and obtain approval before the
composition stage. The brief must state the theme, target duration, output
ratio, local versus online material strategy, intended distribution mode, and
the desired musical register.

This pipeline is specialized: BGM Montage owns beat analysis, reference
grammar, material matching, shot assignment, rendering, and programmatic QA
inside one bounded tool call. Do not invent separate Python orchestration
stages or duplicate its timeline logic in the brief.

## Decisions to lock

1. Identify the music file and confirm it is readable.
2. Choose 9:16, 16:9, 1:1, 4:5, or an explicit canvas.
3. Choose source_provider=local-library for offline work; otherwise record
   the provider and the user's distribution intent.
4. Record whether agent_visual_review is required or off. The default is
   required.
5. Keep references, source manifests, and local-library rights evidence in
   the project so the compose stage can audit them.

Do not mark the brief ready if the music path, duration, ratio, or rights mode
is ambiguous.
