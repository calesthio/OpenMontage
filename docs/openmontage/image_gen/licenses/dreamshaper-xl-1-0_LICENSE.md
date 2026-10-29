# License evidence: Lykon/dreamshaper-xl-1-0

**Retrieved:** 2026-10-23  
**Source:** https://huggingface.co/Lykon/dreamshaper-xl-1-0 (model README, raw main branch)  
**Recorded by:** S15 recipe freeze (docs/openmontage/image_gen/recipe_dreamshaper_xl_1_0.json)

**License (from model card frontmatter):** openrail++  
**Commercial use:** YES (OpenRAIL++ family; use-based restrictions apply)  
**Evidence URL:** https://huggingface.co/Lykon/dreamshaper-xl-1-0  
**API revision sha:** 41e6644752a8c9aa63930e6043c4fd83c7708420  
**Pipeline class:** StableDiffusionXLPipeline (diffusers config)

**Note:** the Lykon/dreamshaper-xl-1-0 repository contains no standalone LICENSE file
(siblings: README.md, model_index.json, scheduler/, vae/, unet/, text_encoder*,
tokenizer*). This file is the model README saved as the license evidence. The
openrail++ declaration is taken from the model card YAML frontmatter. OpenRAIL++
use-based restrictions apply (same family as stabilityai/stable-diffusion-xl-base-1.0;
see docs/openmontage/image_gen/LICENSE_EVIDENCE.md).

---

# Dreamshaper SDXL-1-0 (verbatim model README)

`lykon-models/dreamshaper-xl-1-0` is a Stable Diffusion model that has been fine-tuned on [stabilityai/stable-diffusion-xl-base-1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0).

Please consider supporting me: 
- on [Patreon](https://www.patreon.com/Lykon275)
- or [buy me a coffee](https://snipfeed.co/lykon)

## Diffusers

For more general information on how to run text-to-image models with 🧨 Diffusers, see [the docs](https://huggingface.co/docs/diffusers/using-diffusers/conditional_image_generation).

1. Installation

```
pip install diffusers transformers accelerate
```

2. Run
```py
from diffusers import AutoPipelineForText2Image, DEISMultistepScheduler
import torch

pipe = AutoPipelineForText2Image.from_pretrained('lykon-models/dreamshaper-xl-1-0', torch_dtype=torch.float16, variant="fp16")
pipe.scheduler = DEISMultistepScheduler.from_config(pipe.scheduler.config)
pipe = pipe.to("cuda")

prompt = "portrait photo of muscular bearded guy in a worn mech suit, light bokeh, intricate, steel metal, elegant, sharp focus, soft lighting, vibrant colors"

generator = torch.manual_seed(0)
image = pipe(prompt, num_inference_steps=25).images[0]  
image.save("./image.png")
```

![](./image.png)
