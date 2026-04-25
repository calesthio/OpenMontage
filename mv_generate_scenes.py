"""
Missing You – Full Music Video
FAL scene generation: ~30 clips for 3-minute YouTube 16:9 video

Characters (consistent across ALL prompts):
  SOFIA 2000: 22-year-old woman, dark brown hair, bright eyes, natural makeup,
               light denim jacket or soft sweater, early 2000s casual style
  MARCUS 2000: 26-year-old man, dark curly hair, warm smile, slightly stubbled,
                casual button shirt open at collar, early 2000s style
  SOFIA 2025: same woman now 47, dark hair with subtle silver streaks,
               still beautiful but life-worn, melancholic, dark coat or sweater
  MARCUS 2025: same man now 51, salt-and-pepper hair, handsome but weathered,
                contemplative, grey coat or dark jacket

Visual styles:
  2000 scenes: warm golden tones, slight film grain, MiniDV/Super8 nostalgia,
               soft overexposure, intimate close framings
  2025 scenes: cool blue-grey, cinematic, overcast or rainy, wider lonelier shots
"""

import os, json, time, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(r"C:\Users\ari_v\Claude apps\Openmontage\.env")
os.environ["FAL_KEY"] = os.environ.get("FAL_KEY", "")

import fal_client

OUT_DIR = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\missing_you_mv\scenes")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "fal-ai/kling-video/v1.6/standard/text-to-video"

# Character anchors
S2000 = ("a 22-year-old woman Sofia with dark brown hair, bright warm eyes, "
          "light denim jacket, natural smile, early 2000s casual style")
M2000 = ("a 26-year-old man Marcus with dark curly hair, warm charismatic smile, "
          "slightly stubbled, open-collar button shirt, early 2000s casual style")
S2025 = ("a 47-year-old woman Sofia, dark hair with subtle silver streaks, "
          "still beautiful but life-worn and melancholic, dark wool coat")
M2025 = ("a 51-year-old man Marcus, salt-and-pepper hair, handsome but weathered, "
          "contemplative expression, dark grey jacket")

STYLE_2000 = ("warm golden tones, slight film grain, early 2000s MiniDV aesthetic, "
               "soft nostalgic lighting, intimate framing, 16:9 cinematic")
STYLE_2025 = ("cool blue-grey cinematic tones, overcast light, modern, "
               "melancholic atmosphere, rain or autumn, 16:9 widescreen")

NEG = ("blurry, cartoon, anime, painting, extra limbs, distorted face, "
        "ugly, watermark, text, bad quality, unrealistic, cgi look")

# ── SCENE DEFINITIONS ─────────────────────────────────────────────────────────
# Each scene: id, duration (5 or 10), prompt, era (2000/2025/both), notes
SCENES = [

    # ── INTRO ────────────────────────────────────────────────────────────────
    {
        "id": "intro_2025_sofia_wide",
        "dur": "5",
        "era": "2025",
        "label": "Intro 2025 – Sofia wide shot by rainy window",
        "prompt": (
            f"Wide medium shot of a 47-year-old woman with dark hair and subtle silver "
            "streaks, wearing a dark wool coat, standing alone by a large apartment "
            "window at night. Rain streaks down the glass. City lights glow softly "
            "below. She stands still, looking out, her back slightly turned to the "
            "camera. Slow, gentle camera drift forward. A quiet, establishing moment "
            "of solitude. No objects in hands. "
            f"{STYLE_2025}"
        ),
    },

    # ── CAFÉ ────────────────────────────────────────────────────────────────
    {
        "id": "cafe_2000_wide",
        "dur": "10",
        "era": "2000",
        "label": "Café 2000 – Wide shot, couple at window table",
        "prompt": (
            f"Wide shot of {S2000} and {M2000} sitting across from each other "
            "at a small café table by a rain-streaked window. Marcus is talking "
            "animatedly, Sofia laughs and covers her mouth. Warm café interior, "
            "coffee cups on table, soft amber light from outside. "
            f"{STYLE_2000}, slow subtle camera push-in"
        ),
    },
    {
        "id": "cafe_2000_marcus_talking",
        "dur": "5",
        "era": "2000",
        "label": "Café 2000 – MCU Marcus talking, Sofia reacts",
        "prompt": (
            f"Medium close-up of {M2000} sitting in a café, talking enthusiastically "
            "with hands gesturing. In the soft foreground out of focus, "
            "Sofia laughs across the table. Warm golden café lighting, "
            "coffee cup visible. "
            f"{STYLE_2000}"
        ),
    },
    {
        "id": "cafe_2000_sofia_laughing",
        "dur": "5",
        "era": "2000",
        "label": "Café 2000 – ECU Sofia laughing, eyes bright",
        "prompt": (
            f"Extreme close-up of {S2000} in a café, laughing genuinely, "
            "eyes crinkling with joy, looking at someone across the table. "
            "Warm golden backlight from café window, slightly soft focus background. "
            f"{STYLE_2000}"
        ),
    },
    {
        "id": "cafe_2025_sofia_alone",
        "dur": "10",
        "era": "2025",
        "label": "Café 2025 – Sofia alone at same table",
        "prompt": (
            f"Medium shot of {S2025} sitting alone at a small café table by a "
            "rain-streaked window, same table as before. She slowly stirs her coffee "
            "without drinking it, staring at the empty chair across from her. "
            "Cool grey daylight from window, quiet café. "
            f"{STYLE_2025}, very slow camera movement"
        ),
    },
    {
        "id": "cafe_2025_empty_chair",
        "dur": "5",
        "era": "2025",
        "label": "Café 2025 – POV: empty chair across the table",
        "prompt": (
            "Close-up shot of an empty chair across a café table from Sofia's "
            "point of view. A cold empty coffee cup sits untouched on the other side. "
            "Rain on the window behind the empty chair, grey light. "
            f"{STYLE_2025}, slightly shallow depth of field"
        ),
    },

    # ── STREET CORNER / RAIN ─────────────────────────────────────────────────
    {
        "id": "street_2000_jacket",
        "dur": "10",
        "era": "2000",
        "label": "Street 2000 – Couple huddled under umbrella in rain",
        "prompt": (
            f"Medium shot of {S2000} and {M2000} standing together on a city street "
            "in the rain, both huddled under one small umbrella — too small for two "
            "people. They press close together, laughing at how wet they are anyway. "
            "Rain splashes around them, warm streetlights glow on wet pavement. "
            "A happy, intimate moment in the rain. "
            f"{STYLE_2000}"
        ),
    },
    {
        "id": "street_2025_sofia_alone",
        "dur": "5",
        "era": "2025",
        "label": "Street 2025 – Sofia alone at same corner in rain",
        "prompt": (
            f"Medium shot of {S2025} standing alone at a city street corner in the "
            "rain at night. She hugs her own coat closed with both hands and stares "
            "down the street as if waiting for someone. Neon and streetlights reflect "
            "on the wet pavement. "
            f"{STYLE_2025}"
        ),
    },
    {
        "id": "street_2025_marcus_alone",
        "dur": "5",
        "era": "2025",
        "label": "Street 2025 – Marcus alone, pauses mid-walk",
        "prompt": (
            f"Medium shot of {M2025} walking along a wet city street at night, "
            "he suddenly slows and stops, turning slightly as if something caught his "
            "memory. He stands still for a moment, rain on his shoulders, "
            "looking at a corner or doorway with a distant expression. "
            f"{STYLE_2025}"
        ),
    },

    # ── RECORD STORE ─────────────────────────────────────────────────────────
    {
        "id": "record_2000",
        "dur": "10",
        "era": "2000",
        "label": "Record store 2000 – browsing shelves together",
        "prompt": (
            f"Inside a small cluttered record store, {M2000} and {S2000} are browsing "
            "through vinyl record sleeves on a shelf together. Marcus points at an album "
            "cover with excitement, Sofia leans in to look and smiles. Their hands "
            "flip through the sleeves naturally. Warm overhead lighting, "
            "posters on walls, cozy indie record shop atmosphere. "
            f"{STYLE_2000}"
        ),
    },
    {
        "id": "record_2025_sofia",
        "dur": "5",
        "era": "2025",
        "label": "Record store 2025 – Sofia pauses at same shelf",
        "prompt": (
            f"Medium close-up of a 47-year-old woman with dark brown hair and subtle "
            "silver streaks, wearing a dark wool coat, standing in a record store. "
            "She stops in front of a vinyl shelf. Her hand rests gently on the edge "
            "of the records. She stares at the shelf with a distant, melancholic "
            "expression as if remembering something. A quiet, still moment. "
            f"{STYLE_2025}"
        ),
    },

    # ── PARK BENCH ───────────────────────────────────────────────────────────
    {
        "id": "park_2000_reading",
        "dur": "10",
        "era": "2000",
        "label": "Park 2000 – Marcus reads aloud, Sofia listens",
        "prompt": (
            f"Wide shot of {M2000} and {S2000} sitting close on a wooden park bench "
            "surrounded by golden autumn leaves. Marcus reads aloud from a book, "
            "Sofia has her head on his shoulder, eyes closed, listening. "
            "Warm dappled sunlight through trees. Very still and peaceful. "
            f"{STYLE_2000}"
        ),
    },
    {
        "id": "park_2025_sofia_alone",
        "dur": "5",
        "era": "2025",
        "label": "Park 2025 – Sofia alone on winter bench",
        "prompt": (
            f"Wide shot of {S2025} sitting alone on the same wooden park bench, "
            "now in winter. Bare trees, grey sky, frost on the ground. "
            "She sits in the same spot where Marcus used to be, slightly hunched, "
            "looking at the empty space beside her. "
            f"{STYLE_2025}"
        ),
    },
    {
        "id": "park_2025_marcus_alone",
        "dur": "5",
        "era": "2025",
        "label": "Park 2025 – Marcus on a different bench, alone",
        "prompt": (
            f"Medium shot of {M2025} sitting on a park bench alone, autumn afternoon. "
            "He stares forward, elbows on knees, not really seeing what's in front "
            "of him. Fallen leaves around his feet. A quiet, internal moment. "
            f"{STYLE_2025}"
        ),
    },

    # ── DANCE BAR ────────────────────────────────────────────────────────────
    {
        "id": "dance_2000",
        "dur": "10",
        "era": "2000",
        "label": "Dance bar 2000 – Slow dance, eyes closed",
        "prompt": (
            f"Medium shot inside a dimly lit bar or small club, {M2000} and {S2000} "
            "slow dancing very close together, eyes closed, foreheads nearly touching. "
            "Warm amber bar lighting, blurred figures of others dancing around them. "
            "They are in their own world. "
            f"{STYLE_2000}"
        ),
    },
    {
        "id": "dance_2025_sofia_watching",
        "dur": "5",
        "era": "2025",
        "label": "Dance bar 2025 – Sofia watches couples from the edge",
        "prompt": (
            "Medium shot of one middle-aged woman standing alone at the edge of a "
            "dimly lit bar. She is clearly in her late 40s, visibly 47 years old, "
            "with dark hair that is heavily streaked with silver and grey throughout — "
            "prominent grey at the temples and crown, not subtle. Her face shows "
            "natural aging: fine lines around her eyes and mouth, life-worn features. "
            "She wears a dark wool coat. She holds a glass she doesn't drink, watching "
            "couples dancing with a quiet melancholic expression. Alone in a crowd. "
            "photorealistic, cinematic, middle-aged woman, grey hair, NOT young. "
            f"{STYLE_2025}"
        ),
    },
    {
        "id": "dance_2025_marcus_bar",
        "dur": "5",
        "era": "2025",
        "label": "Dance bar 2025 – Marcus alone at bar with drink",
        "prompt": (
            f"Medium close-up of {M2025} sitting alone at a bar counter, "
            "a drink in front of him. He isn't drinking. He stares at the bar top "
            "with a distant, contemplative expression. Bar atmosphere blurred behind. "
            f"{STYLE_2025}"
        ),
    },

    # ── INTIMATE MOMENTS 2000 (Fast-cut chorus material) ─────────────────────
    {
        "id": "intimate_2000_kiss",
        "dur": "5",
        "era": "2000",
        "label": "2000 – Natural brief kiss, candid moment",
        "prompt": (
            f"Close medium shot of {M2000} leaning in and giving {S2000} "
            "a brief, natural, candid kiss. Not staged — she's slightly surprised "
            "and then smiles. Warm soft light, intimate moment. "
            f"{STYLE_2000}, subtle slow motion"
        ),
    },
    {
        "id": "intimate_2000_running_rain",
        "dur": "5",
        "era": "2000",
        "label": "2000 – Running in rain together, laughing",
        "prompt": (
            f"Medium shot of {S2000} and {M2000} running together through rain "
            "on a city street at night, laughing loudly, completely soaked, "
            "not caring at all. Streetlights make the rain shine. Pure joy. "
            f"{STYLE_2000}"
        ),
    },
    {
        "id": "intimate_2000_walking_away",
        "dur": "5",
        "era": "2000",
        "label": "2000 – Walking away hand in hand",
        "prompt": (
            f"Wide shot from behind of {M2000} and {S2000} walking away together "
            "down a city street, their hands intertwined between them. "
            "Warm evening light, they lean slightly toward each other. "
            f"{STYLE_2000}, slow camera follows"
        ),
    },
    {
        "id": "intimate_2000_hands",
        "dur": "5",
        "era": "2000",
        "label": "2000 – ECU intertwined hands",
        "prompt": (
            "Extreme close-up of two young hands intertwined on a café table or park "
            "bench. His thumb brushes hers slightly. Warm golden light catches the "
            "skin. Very intimate, very still. "
            f"{STYLE_2000}"
        ),
    },

    # ── EMOTION CLOSE-UPS ────────────────────────────────────────────────────
    {
        "id": "ecus_2000_sofia_happy",
        "dur": "5",
        "era": "2000",
        "label": "ECU 2000 – Sofia's face, pure happiness",
        "prompt": (
            f"Extreme close-up of {S2000}'s face in warm golden light, "
            "her expression radiating pure happiness, looking at someone off-camera. "
            "Eyes bright, a full genuine smile. "
            f"{STYLE_2000}"
        ),
    },
    {
        "id": "ecus_2000_marcus_laughing",
        "dur": "5",
        "era": "2000",
        "label": "ECU 2000 – Marcus laughing, full of life",
        "prompt": (
            f"Extreme close-up of {M2000}'s face, mid-laugh, full of life and warmth. "
            "Looking at someone just off frame. Eyes crinkled, completely present. "
            f"{STYLE_2000}"
        ),
    },
    {
        "id": "ecus_2025_sofia_tears",
        "dur": "5",
        "era": "2025",
        "label": "ECU 2025 – Sofia, tears on cheek, direct to camera",
        "prompt": (
            f"Extreme close-up of {S2025}'s face, looking directly into the camera. "
            "A single tear on her cheek, she doesn't wipe it. Her expression is "
            "aching but composed — not breaking, just carrying something. "
            "Rain-wet skin, cool blue-grey light. "
            f"{STYLE_2025}"
        ),
    },
    {
        "id": "ecus_2025_marcus_window",
        "dur": "5",
        "era": "2025",
        "label": "ECU 2025 – Marcus at apartment window, rain on glass",
        "prompt": (
            f"Close-up of {M2025} standing at an apartment window at night. "
            "Rain streaks down the glass between him and the camera. "
            "He stares out without seeing, jaw slightly set, somewhere far away. "
            f"{STYLE_2025}"
        ),
    },
    {
        "id": "ecus_2025_sofia_photo",
        "dur": "5",
        "era": "2025",
        "label": "ECU 2025 – Sofia holds a photograph",
        "prompt": (
            f"Close-up of {S2025}'s hands holding a photograph. "
            "We see only the edges — not the content. Her fingers trace the border "
            "gently. She sets it face-down on a table. Quiet apartment light. "
            f"{STYLE_2025}"
        ),
    },
    {
        "id": "ecus_2025_marcus_phone",
        "dur": "5",
        "era": "2025",
        "label": "ECU 2025 – Marcus looks at old photos on phone",
        "prompt": (
            "Close-up of a 51-year-old man with salt-and-pepper hair, handsome but "
            "weathered face, wearing a dark grey jacket, sitting in a dark room. "
            "His face is lit only by his phone screen. He scrolls through old photos "
            "slowly. His expression is quiet pain. He stops on one and just looks. "
            f"{STYLE_2025}"
        ),
    },

    # ── ALONE MOMENTS 2025 ───────────────────────────────────────────────────
    {
        "id": "alone_2025_sofia_jacket",
        "dur": "5",
        "era": "2025",
        "label": "2025 – Sofia holds old jacket in her apartment",
        "prompt": (
            f"Medium close-up of {S2025} standing in her apartment, holding "
            "an old men's jacket — slightly too large for her. "
            "She holds it a moment, then sets it down on a chair quietly. "
            "Dim apartment light, evening. "
            f"{STYLE_2025}"
        ),
    },
    {
        "id": "alone_2025_marcus_bridge",
        "dur": "5",
        "era": "2025",
        "label": "2025 – Marcus on bridge at night, looking at water",
        "prompt": (
            f"Wide shot of {M2025} standing alone on a bridge at night, "
            "leaning on the railing, looking down at the dark water below. "
            "City lights reflect on the river. Rain on his shoulders. "
            "He is very small in the frame, the city vast around him. "
            f"{STYLE_2025}"
        ),
    },
    {
        "id": "alone_2025_marcus_insomnia",
        "dur": "5",
        "era": "2025",
        "label": "2025 – Marcus can't sleep, sits in dark apartment",
        "prompt": (
            f"Medium shot of {M2025} sitting on the edge of his bed in a dark "
            "apartment, lit only by streetlight through the window. "
            "He sits in silence, elbows on knees, head bowed slightly. "
            "Not sleeping. Just enduring. "
            f"{STYLE_2025}"
        ),
    },
    {
        "id": "alone_2025_sofia_walking_toward",
        "dur": "5",
        "era": "2025",
        "label": "2025 – Sofia walking toward camera in rain",
        "prompt": (
            f"Medium shot of {S2025} walking slowly toward the camera on a "
            "rain-soaked city street at night, neon reflections on wet pavement. "
            "She walks without hurry, her expression distant and melancholic. "
            "She looks up at the camera briefly. "
            f"{STYLE_2025}"
        ),
    },
    {
        "id": "alone_2025_sofia_walking_away",
        "dur": "5",
        "era": "2025",
        "label": "2025 – Sofia from behind, walks same street as 2000",
        "prompt": (
            f"Wide shot from behind of {S2025} walking alone down a city street "
            "at night in the rain. The same street where they once ran together. "
            "Her silhouette against distant streetlights, no hand to hold. "
            "Very slow walk, camera stays still. "
            f"{STYLE_2025}"
        ),
    },

    # ── BRIDGE ON RIVER 2000 (mirror of marcus_bridge) ───────────────────────
    {
        "id": "bridge_2000",
        "dur": "5",
        "era": "2000",
        "label": "2000 – Sofia and Marcus on same bridge, romantic",
        "prompt": (
            f"Medium shot of {S2000} leaning back against a bridge railing at night, "
            f"{M2000} facing her, hands on the railing on either side of her. "
            "City lights reflect on the river behind them. They're close, talking "
            "quietly, the world empty around them. Warm street glow. "
            f"{STYLE_2000}"
        ),
    },

    # ── OUTRO / FINAL ────────────────────────────────────────────────────────
    {
        "id": "outro_sofia_window",
        "dur": "10",
        "era": "2025",
        "label": "Outro – Sofia at window at night, looks out, then FADE",
        "prompt": (
            f"Wide medium shot of {S2025} standing at a large apartment window "
            "at night, her back mostly to us. Rain on the glass. City lights below. "
            "She places her hand on the cold glass slowly. Holds it there. "
            "Very still, very quiet. "
            f"{STYLE_2025}, slow camera pull back"
        ),
    },
]


def generate(scene):
    out = OUT_DIR / f"{scene['id']}.mp4"
    if out.exists() and out.stat().st_size > 200_000:
        print(f"  [cached] {scene['id']}")
        return str(out)

    print(f"  Generating ({scene['dur']}s): {scene['label']}")
    result = fal_client.subscribe(
        MODEL,
        arguments={
            "prompt": scene["prompt"],
            "negative_prompt": NEG,
            "duration": scene["dur"],
            "aspect_ratio": "16:9",
            "cfg_scale": 0.5,
        },
        with_logs=False,
    )
    url = result["video"]["url"]
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(out, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            if chunk: f.write(chunk)
    mb = out.stat().st_size / 1024 / 1024
    print(f"  Saved {out.name} ({mb:.1f} MB)")
    return str(out)


if __name__ == "__main__":
    print("=" * 65)
    print("Missing You – Full MV Scene Generation")
    print(f"Scenes: {len(SCENES)} | Model: {MODEL}")
    fives  = sum(1 for s in SCENES if s["dur"] == "5")
    tens   = sum(1 for s in SCENES if s["dur"] == "10")
    cost   = fives * 0.45 + tens * 0.90
    print(f"5s clips: {fives} | 10s clips: {tens} | Est. cost: ~${cost:.2f} USD")
    print("=" * 65)

    results = []
    for i, scene in enumerate(SCENES, 1):
        print(f"\n[{i}/{len(SCENES)}]")
        try:
            path = generate(scene)
            results.append({**scene, "path": path})
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

    manifest = OUT_DIR.parent / "scenes_manifest.json"
    manifest.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nManifest: {manifest}")
    print(f"Done: {len(results)}/{len(SCENES)} scenes")
