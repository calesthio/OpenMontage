# Creator Video Proposal Director

Present 2-3 concepts with a recommended production path. Each concept must state:

- The role of user-provided assets.
- Which scenes should use Seedance-compatible generation through `video_selector`, `runninghub_seedance_video`, `seedance_video`, or `seedance_replicate`.
- Which scenes can use text cards, stock, or imported media instead of generation.
- Whether the deferred digital-human API is out of scope for this run.

## Runtime Decision

You must lock `render_runtime` at proposal time and record a `render_runtime_selection` decision.

Present both Remotion and HyperFrames when both are available:

- Remotion: best for template-driven vertical edits, captions, title cards, and existing React scene components. Tradeoff: less bespoke for advanced HTML/GSAP motion.
- HyperFrames: best for kinetic typography and highly customized HTML/GSAP creator pieces. Tradeoff: more authoring effort and less reuse of the Remotion scene stack.

The lowercase runtime key is `hyperframes`; record that key when it is selected or rejected. Recommend the runtime that best matches the approved concept, but wait for user approval before proceeding. Also lock `composition_mode` as `templated` for the MVP unless the user explicitly asks for atelier.
