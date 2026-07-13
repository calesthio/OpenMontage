# Publish Director — Product-Motion Pipeline

## When to Use

Final stage (human-gated). The render is approved. You package the
deliverable.

## Process

1. **Export package** under `projects/<id>/renders/export/`:
   - the final MP4 (and a platform-cropped variant if the proposal promised
     one),
   - `metadata.json`: title, description, tags — name the product and its
     core promise accurately; the description may cite the featured screens.
     No claims the video doesn't show.
   - thumbnail concept: the strongest snapshot still (usually the hero
     screen's most-assembled frame) with a one-line framing note.
2. **Chapter markers** from the scene timing map (one per featured screen)
   when the target platform supports them.
3. **Attribution/licensing**: music/SFX provenance from the asset_manifest
   (provider, generation prompts) recorded in the publish log — SaaS launch
   videos get reused; the license trail must travel with the file.
4. Validate `publish_log`, checkpoint `awaiting_human`, present the package
   contents, **end your turn**.
