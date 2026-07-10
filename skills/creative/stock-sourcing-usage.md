# Stock Sourcing Usage for Balamonis Studio

> How to use the stock image and video tools effectively — query construction,
> provider selection, license awareness, and integration with the asset pipeline.

## Available Stock Tools

| Tool | Provider | Content | Cost | Rate Limit | Best For |
|------|----------|---------|------|-----------|----------|
| `pexels_image` | Pexels | Photos | Free | 200/hr | High-quality photography, diverse library |
| `pixabay_image` | Pixabay | Photos, illustrations, vectors | Free | 100/min | Category filtering, large library (5M+) |
| `pexels_video` | Pexels | Video clips | Free | 200/hr | HD/4K real-world footage |
| `pixabay_video` | Pixabay | Video clips | Free | 100/min | Category-filtered video, animation clips |

## Provider Selection Guide

### When to Use Pexels
- Need **high-quality photography** (curated, professional)
- Need **video** (larger video library than Pixabay)
- Want **orientation filtering** (landscape/portrait/square)
- Want **color filtering** (match playbook palette)
- Need results in **multiple languages** (28 locales)

### When to Use Pixabay
- Need **category-based filtering** (nature, business, science, etc.)
- Want **illustrations or vectors** in addition to photos
- Want **editor's choice** curated results
- Need **higher rate limits** (100/min vs 200/hr)
- Need **video type filtering** (film vs animation)

### Decision Flow
```
Need stock image?
├── Need specific category (science, business, etc.)? → pixabay_image
├── Need illustration/vector? → pixabay_image
├── Need color matching? → pexels_image
└── General photo? → pexels_image (higher quality curation)

Need stock video?
├── Need 4K? → pexels_video (supports 4K via size="large")
├── Need animation clips? → pixabay_video (video_type="animation")
├── Need category filter? → pixabay_video
└── General footage? → pexels_video (better HD quality)
```

## Input Parameters Guide

### pexels_image / pexels_video
```python
{
    "query": "city skyline sunset",      # Required: search term
    "orientation": "landscape",           # Optional: landscape/portrait/square
    "size": "large",                      # Optional: large/medium/small
    "color": "FF6B35",                    # Optional: hex without # or color name
    "per_page": 5,                        # Results per page (1-80)
    "download_size": "large2x",           # Image: original/large2x/large/medium
    "preferred_quality": "hd",            # Video: hd/sd
    "output_path": "assets/images/s3.jpg" # Where to save
}
```

### pixabay_image / pixabay_video
```python
{
    "query": "server room",              # Required: search term (max 100 chars)
    "image_type": "photo",               # Image: all/photo/illustration/vector
    "video_type": "film",                # Video: all/film/animation
    "orientation": "horizontal",          # all/horizontal/vertical
    "category": "computer",              # One of 20 categories
    "colors": "blue,gray",              # Comma-separated color names
    "editors_choice": true,              # Curated high-quality only
    "safesearch": true,                  # Always true for production
    "output_path": "assets/video/s5.mp4" # Where to save
}
```

## Gotchas and Best Practices

### 1. Pixabay URLs Expire
Pixabay download URLs contain embedded tokens that expire. **Always download immediately** after searching. The tools handle this automatically, but never cache Pixabay URLs for later use.

### 2. Pixabay Resolution Limit
Standard Pixabay API users get max 1280px wide images (`largeImageURL`). Full resolution requires approved API access. For most video production overlays, 1280px is sufficient.

### 3. Pexels Auth Header
Pexels uses a bare API key in the `Authorization` header (NOT `Bearer`). The tool handles this, but be aware if debugging.

### 4. Search Results Vary by Locale
Pexels supports 28 locales. If searching for culturally specific content, set the locale parameter.

### 5. Stock Images Are Deterministic
Unlike AI generation, searching "ocean waves" twice returns the same results. If the first result isn't good enough, try different keywords — don't retry the same query.

### 6. Duration Filtering for Video
Both stock video tools support `min_duration` and `max_duration` parameters. Use these to avoid downloading 30-second clips when you only need 4 seconds — it saves bandwidth and time.

## Integration with Asset Pipeline

Stock tools integrate exactly like generation tools. In the asset manifest:

```json
{
    "id": "broll-s3",
    "type": "image",
    "subtype": "broll",
    "path": "assets/images/broll-s3.jpg",
    "source_tool": "pexels_image",
    "scene_id": "scene-3",
    "cost_usd": 0.00,
    "metadata": {
        "photographer": "Joey Farina",
        "source_url": "https://www.pexels.com/photo/2014422/",
        "license": "Pexels License (free, no attribution required)"
    }
}
```

The Edit Director and Compose Director treat stock assets identically to generated ones — they just reference the file path from the manifest.

## Licensing Summary

| Provider | Commercial Use | Attribution | Restrictions |
|----------|---------------|-------------|-------------|
| Pexels | Yes, free | Not required (appreciated) | Cannot sell unaltered; cannot imply endorsement |
| Pixabay | Yes, free | Not required | Cannot sell unaltered; cannot create competing stock service |

Both are safe for all Balamonis Studio use cases. No licensing fees, no per-use royalties, no attribution obligations.
