---
name: valid_skill
version: "1.0"
inputs:
  topic:
    type: string
    required: true
outputs:
  result: string
steps:
  - id: do_thing
    tool: some_tool
    inputs: { topic: "${inputs.topic}" }
---

# Valid Skill

Prose body untouched by frontmatter parsing.
