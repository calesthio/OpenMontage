# Asset Director — Product Scene Images

## Inputs

Required: `scene_plan`.

## Generation

For every selected style, call `seedream_ark_image` with `count=3`, the exact
storyboard prompt, the original product image, and:

`assets/images/<style>/batch-001/scene_<style>_<1..3>.png`

Announce provider `ark`, model, three-candidate batch, and cost status first.
Do not generate styles the user did not select. Do not add text or logos.
Every regenerated batch uses the next `batch-NNN` directory; never overwrite an
already reviewed batch.

## Review

Inspect every image for:

- product shape, proportions, color, label, and packaging;
- natural scene integration;
- clear subject and acceptable composition;
- no invented product claims.

If the product drifted, stop and do not proceed to video. Present 4 choices:

1. Select candidate 1, 2, or 3.
2. Regenerate all three for this style.
3. Adjust one prompt detail.
4. Change style.

## Artifact

Write the updated `asset_manifest`, including the approved candidate per style
and all source metadata. 停止并等待用户审批，不要继续生成视频。
