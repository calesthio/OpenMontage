"""
Missing You × Seedance 2.0 — Scene Generator

Uses Seedance 2.0 reference-to-video with:
  @Image1 = Sofia (young or old depending on era)
  @Image2 = Marcus (young or old depending on era)
  @Audio1 = Song segment (beat-sync guidance)

Pipeline:
  1. python mv_generate_chars.py          — generate 4 character ref images
  2. (review chars)
  3. python mv_generate_scenes.py --refs-only   — test 3 anchor clips
  4. (review anchors)
  5. python mv_generate_scenes.py               — full generation

Cost estimate: ~$48 USD (Fast tier, 34 clips)
"""

import os, json, argparse, requests, subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(r"C:\Users\ari_v\Claude apps\Openmontage\.env")
os.environ["FAL_KEY"] = os.environ.get("FAL_KEY", "")
import fal_client

# ── Paths ──────────────────────────────────────────────────────────────────────
MV_DIR     = Path(r"C:\Users\ari_v\Claude apps\Openmontage\output\missing_you_seedance")
CHARS_DIR  = MV_DIR / "chars"
SCENES_DIR = MV_DIR / "scenes"
AUDIO_IN   = r"C:\Users\ari_v\Downloads\Missing you P1.4 RADIO.mp3"

MV_DIR.mkdir(parents=True, exist_ok=True)
SCENES_DIR.mkdir(parents=True, exist_ok=True)

# Seedance 2.0 — Fast tier (cheaper, 5s/10s only)
# Switch to "bytedance/seedance-2.0/reference-to-video" for full 4-15s range
MODEL = "bytedance/seedance-2.0/fast/reference-to-video"

# ── Character reference IDs ────────────────────────────────────────────────────
# Each era maps to the right character images
# Seedance @Image1 = primary char, @Image2 = secondary char (if present in scene)
CHAR_REFS = {
    "sofia_2000":  "sofia_2000.png",
    "sofia_2025":  "sofia_2025.png",
    "marcus_2000": "marcus_2000.png",
    "marcus_2025": "marcus_2025.png",
}

NEG = (
    "blurry, cartoon, anime, painting, extra limbs, distorted face, "
    "watermark, text overlay, bad quality, frozen, static"
)

# ── Style descriptors ──────────────────────────────────────────────────────────
STYLES = {
    "2000": (
        "early 2000s setting, warm golden-amber light, film grain, "
        "slightly faded colours, intimate and alive, cinematic 16:9"
    ),
    "2025": (
        "present day, cold blue-grey light, muted desaturated palette, "
        "stillness and absence, cinematic 16:9"
    ),
    "both": (
        "cinematic 16:9, photorealistic film look"
    ),
}

# ── Scene definitions ──────────────────────────────────────────────────────────
# chars: list of char_ref keys used in scene (first = @Image1, second = @Image2)
# audio_seg: (start_sec, end_sec) of song to feed as @Audio1 for beat guidance
SCENES = [
    # ANCHORS (for --refs-only review)
    {"id": "anchor_sofia_2025", "dur": "5", "era": "2025", "anchor": True,
     "chars": ["sofia_2025"],
     "audio_seg": (0, 10),
     "prompt": (
         "@Image1 as Sofia (47 years old, 2025) stands at a rain-streaked apartment window at night. "
         "One hand is pressed flat against the cold glass — not leaning, just touching it, "
         "as if checking whether something is still real. "
         "She is not crying. She has been crying. Jaw set, shoulders drawn in slightly. "
         "She is trying to hold herself together and mostly succeeding. "
         "Cold blue light from outside falls across one side of her face. "
         "Camera holds very still. She does not move. @Audio1 sets the emotional pacing. {style}"
     )},
    {"id": "anchor_couple_2000", "dur": "5", "era": "2000", "anchor": True,
     "chars": ["sofia_2000", "marcus_2000"],
     "audio_seg": (10, 20),
     "prompt": (
         "@Image1 as Sofia (22 years old) and @Image2 as Marcus (26 years old) sit at a café corner table. "
         "Their coffee cups are between them, both untouched — they forgot about them mid-conversation. "
         "Marcus is drawing something in the air with his hands to illustrate a point. "
         "Sofia's smile breaks before he finishes his sentence, she already sees where it's going. "
         "They are leaning toward each other without noticing. "
         "Warm golden window light. Camera slowly pushes in. @Audio1 sets the warm nostalgic tone. {style}"
     )},
    {"id": "anchor_marcus_2025", "dur": "5", "era": "2025", "anchor": True,
     "chars": ["marcus_2025"],
     "audio_seg": (0, 10),
     "prompt": (
         "@Image1 as Marcus (51 years old, 2025) stands alone on a bridge at night, "
         "both hands on the railing, looking down at dark water. "
         "He is not in danger — he is just unable to go home yet. "
         "Rain soaks through his jacket but he does not notice or does not care. "
         "His shoulders carry the full weight of something unresolved. "
         "He exhales slowly. Camera holds still, slightly below his eyeline. "
         "@Audio1 sets the melancholic pacing. {style}"
     )},

    # INTRO 0-10s
    {"id": "intro_2025_sofia_wide", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["sofia_2025"],
     "audio_seg": (0, 5),
     "prompt": (
         "Wide shot: @Image1 as Sofia (47 years old, 2025) sits alone in a dim apartment at night, "
         "by the window. Rain on the glass. Blue light on her face. "
         "She holds a photograph face-down in both hands on her lap. "
         "She has been sitting here a long time — coat still on, like she just came in and stopped. "
         "Slowly she turns her head away from the window, looking into the dark room behind her. "
         "As if she heard something — or remembered something inside the apartment. "
         "Very slow camera drift inward toward her. @Audio1 opens the mood. {style}"
     )},

    # VERSE 1 10-38s — intercut café 2000 joy vs 2025 solitude
    {"id": "cafe_2000_wide", "dur": "10", "era": "2000", "anchor": False,
     "chars": ["sofia_2000", "marcus_2000"],
     "audio_seg": (10, 20),
     "prompt": (
         "Wide shot of a warm café in 2000, corner table by rain-streaked window. "
         "@Image1 as Sofia (22) and @Image2 as Marcus (26) sit across from each other. "
         "They are flirting — Marcus says something with a half-smile, watching her reaction. "
         "Sofia tilts her head slightly and smiles back, eyes meeting his directly. "
         "Natural eye contact, playful and warm, two people enjoying each other's company. "
         "Neither is leaning awkwardly — relaxed posture, at ease together. "
         "Warm golden light. Camera slowly pushes in. @Audio1 guides the warmth. {style}"
     )},
    {"id": "cafe_2000_marcus_talking", "dur": "5", "era": "2000", "anchor": False,
     "chars": ["marcus_2000", "sofia_2000"],
     "audio_seg": (20, 25),
     "prompt": (
         "Medium close-up on @Image1 as Marcus (26) mid-story — one hand gesturing, "
         "eyes bright, completely committed to making her understand this thing. "
         "He is funny without trying to be. "
         "@Image2 as Sofia visible at frame edge, her expression shifting from skeptical to delighted. "
         "Warm café light catches his face. He leans forward for emphasis. "
         "@Audio1 pacing. {style}"
     )},
    {"id": "cafe_2000_sofia_laughing", "dur": "5", "era": "2000", "anchor": False,
     "chars": ["sofia_2000"],
     "audio_seg": (25, 30),
     "prompt": (
         "Extreme close-up of @Image1 as Sofia (22) — she is laughing and trying to stop laughing "
         "and failing completely. Hand comes up toward her mouth, doesn't make it. "
         "Eyes wet from laughing, head slightly tilted back. "
         "This is not performance — it caught her off guard. "
         "She is the most alive she has ever looked. Warm golden café light. "
         "@Audio1 pacing. {style}"
     )},
    {"id": "cafe_2025_sofia_alone", "dur": "10", "era": "2025", "anchor": False,
     "chars": ["sofia_2025"],
     "audio_seg": (10, 20),
     "prompt": (
         "@Image1 as Sofia (47 years old, 2025) sits alone at the same café corner table. "
         "There are two cups on the table — she ordered out of habit, then realised. "
         "The second cup cools untouched across from her. "
         "She wraps both hands around her own cup but does not drink. "
         "She looks at the empty chair. Not dramatically — just looks. "
         "Cold grey window light. Camera holds completely still. @Audio1 pacing. {style}"
     )},
    {"id": "cafe_2025_empty_chair", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["marcus_2025"],
     "audio_seg": (30, 35),
     "prompt": (
         "@Image1 as Marcus (51 years old, 2025) sits at a café table with a friend — "
         "another man his age, visible at the edge of frame. They talk quietly. "
         "Marcus listens and nods, but his eyes drift away for a moment — out the window, elsewhere. "
         "A slight distance behind his expression, as if something else is occupying part of him. "
         "Camera starts wide and slowly pushes in toward Marcus's face. "
         "Cold grey café light. Unhurried movement. @Audio1 pacing. {style}"
     )},

    # PRE-CHORUS 38-53s — rain street
    {"id": "street_2000_jacket", "dur": "10", "era": "2000", "anchor": False,
     "chars": ["sofia_2000", "marcus_2000"],
     "audio_seg": (38, 48),
     "prompt": (
         "@Image1 as Sofia and @Image2 as Marcus share one umbrella on a wet city street at night. "
         "The umbrella is tilted — toward her, not centred. He is getting rained on. "
         "She notices and tries to correct it; he tilts it back to her. "
         "They are laughing at the argument. Neon reflects everywhere on the pavement. "
         "They are pressed close but the warmth is in the disagreement, not the proximity. "
         "Camera moves with them. @Audio1 drives the energy. {style}"
     )},
    {"id": "street_2025_sofia_alone", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["sofia_2025"],
     "audio_seg": (48, 53),
     "prompt": (
         "@Image1 as Sofia (47) stands at the same street corner in the rain. No umbrella. "
         "She is not seeking shelter. She is standing in it on purpose, "
         "face turned slightly upward, eyes half-closed. "
         "It is not poetic — she just doesn't have a reason to go anywhere. "
         "Cold blue-grey light. Rain runs down her face. Camera holds. @Audio1 pacing. {style}"
     )},
    {"id": "street_2025_marcus_alone", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["marcus_2025"],
     "audio_seg": (48, 53),
     "prompt": (
         "@Image1 as Marcus (51 years old) walks alone down a rainy city street at night. "
         "He stops mid-stride and turns his head slowly, as if something triggered a memory. "
         "He stands still in the rain, looking to one side, then exhales and walks on. "
         "Photorealistic, clean render — no visual artifacts or distortion around him. "
         "Cold grey light, wet pavement reflecting streetlamps. @Audio1 pacing. {style}"
     )},

    # CHORUS 1 53-82s — fast-cut joy vs grief
    {"id": "record_2000", "dur": "10", "era": "2000", "anchor": False,
     "chars": ["sofia_2000", "marcus_2000"],
     "audio_seg": (53, 63),
     "prompt": (
         "@Image1 as Sofia (22) and @Image2 as Marcus (26) browse vinyl records in a warm record store. "
         "Marcus holds up a record sleeve toward Sofia — she leans in, smiles, shakes her head. "
         "Camera drifts from a close-up of the record outward to reveal both of them laughing together. "
         "Slow dolly movement through the shelves, following their energy. "
         "Warm amber light, floor-to-ceiling shelves, cluttered and alive. "
         "Photorealistic, clean render. @Audio1 drives the energy. {style}"
     )},
    {"id": "record_2025_sofia", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["sofia_2025"],
     "audio_seg": (63, 68),
     "prompt": (
         "@Image1 as Sofia (47) stands at a record store shelf. "
         "Her hand moves to a specific sleeve without searching — muscle memory. "
         "She pulls it half out, sees the cover, then does not look away for a moment. "
         "She slides it back without taking it. Her hand stays on the shelf a beat longer. "
         "Then she walks away. Expression not sad — just decided. @Audio1 pacing. {style}"
     )},
    {"id": "park_2000_reading", "dur": "10", "era": "2000", "anchor": False,
     "chars": ["marcus_2000", "sofia_2000"],
     "audio_seg": (63, 73),
     "prompt": (
         "@Image1 as Marcus (26) sits on a sunny park bench reading aloud from a paperback. "
         "@Image2 as Sofia (22) sits close beside him, head resting back, eyes closed, listening. "
         "He reads slowly, glancing at her between sentences. She smiles faintly without opening her eyes. "
         "Dappled summer sunlight through trees above them. Warm and peaceful. "
         "Photorealistic, clean render, natural body language. "
         "@Audio1 guides the gentle warmth. {style}"
     )},
    {"id": "park_2025_sofia_alone", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["sofia_2025"],
     "audio_seg": (73, 78),
     "prompt": (
         "@Image1 as Sofia (47) sits on a winter park bench, positioned slightly to one side — "
         "leaving space, the way you do when you've sat beside someone there a hundred times. "
         "Bare trees, pale cold light. She looks straight ahead at nothing. "
         "Hands deep in coat pockets. She doesn't notice she's left the space. "
         "@Audio1 pacing. {style}"
     )},
    {"id": "park_2025_marcus_alone", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["marcus_2025"],
     "audio_seg": (73, 78),
     "prompt": (
         "@Image1 as Marcus (51) sits on a park bench with a book open on his knee. "
         "He has not turned the page in a long time. "
         "He is looking past the book at the path ahead. "
         "A pigeon lands nearby — he watches it without really seeing it. "
         "Cold winter light. Expression not sad exactly — just absent. @Audio1 pacing. {style}"
     )},

    # CHORUS / DANCE 82-114s
    {"id": "dance_2000", "dur": "10", "era": "2000", "anchor": False,
     "chars": ["sofia_2000", "marcus_2000"],
     "audio_seg": (82, 92),
     "prompt": (
         "@Image1 as Sofia and @Image2 as Marcus slow dance in a dimly lit bar. "
         "They are barely moving — just swaying, the world narrowed to the six inches between their faces. "
         "Her eyes are closed, head not quite on his shoulder, hovering just close. "
         "He has one hand at her back, not pulling her in — just keeping contact. "
         "Other couples are blurred warmth around them. They are not performing this for anyone. "
         "@Audio1 syncs the rhythm. {style}"
     )},
    {"id": "dance_2025_sofia_watching", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["sofia_2025"],
     "audio_seg": (92, 97),
     "prompt": (
         "@Image1 as Sofia (47) walks slowly through an elegant, warmly lit event venue. "
         "She wears a simple dark evening dress. She holds a wine glass loosely in one hand. "
         "She moves with quiet composure — unhurried, upright, dignified. "
         "She is not watching the dancefloor. She moves through the room as if passing through. "
         "Warm amber candlelight, other guests softly blurred around her. "
         "Camera follows her at a gentle pace. @Audio1 pacing. {style}"
     )},
    {"id": "dance_2025_marcus_bar", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["marcus_2025"],
     "audio_seg": (92, 97),
     "prompt": (
         "@Image1 as Marcus (51) sits at the bar, a glass in front of him. "
         "He has not touched the drink. He watches the dancefloor. "
         "Someone at the bar says something to him — we see him register it, almost respond, "
         "then turn back to the dancefloor as if he forgot the person was there. "
         "Warm amber light on his face. @Audio1 pacing. {style}"
     )},

    # INTIMATE MOMENTS 114-131s
    {"id": "intimate_2000_kiss", "dur": "5", "era": "2000", "anchor": False,
     "chars": ["sofia_2000", "marcus_2000"],
     "audio_seg": (114, 119),
     "prompt": (
         "@Image1 as Sofia and @Image2 as Marcus on a city street at night. "
         "The kiss is not a movie kiss — it's brief, natural, the ten-thousandth time. "
         "She leans up, he leans down, it happens like breathing. "
         "Neither of them stops walking. They just do it and keep going. "
         "Warm neon reflections on wet pavement. Completely unposed. @Audio1 pacing. {style}"
     )},
    {"id": "intimate_2000_running_rain", "dur": "5", "era": "2000", "anchor": False,
     "chars": ["sofia_2000", "marcus_2000"],
     "audio_seg": (119, 124),
     "prompt": (
         "@Image1 as Sofia (22) and @Image2 as Marcus (26) lie in bed together on a Sunday morning. "
         "They are under the same duvet, close to each other, faces relaxed. "
         "Early morning sunlight comes through a gap in the curtains, slowly spreading across them. "
         "Neither is fully awake — half asleep, warm, unhurried. "
         "Marcus has one arm loosely around her. Sofia's eyes are closed, breathing slowly. "
         "The light grows gradually warmer. Camera holds still, very close. "
         "@Audio1 sets the gentle waking pace. {style}"
     )},
    {"id": "intimate_2000_walking_away", "dur": "5", "era": "2000", "anchor": False,
     "chars": ["sofia_2000", "marcus_2000"],
     "audio_seg": (124, 129),
     "prompt": (
         "@Image1 as Sofia and @Image2 as Marcus walk away from camera down a golden-lit street, "
         "hand in hand. Their steps are matched without either of them trying. "
         "He says something. She squeezes his hand. Neither looks back. "
         "We watch them go until they are small. Camera stays fixed. @Audio1 pacing. {style}"
     )},
    {"id": "intimate_2000_hands", "dur": "5", "era": "2000", "anchor": False,
     "chars": ["sofia_2000", "marcus_2000"],
     "audio_seg": (129, 134),
     "prompt": (
         "Extreme close-up: two hands intertwined — one woman's, one man's. "
         "His thumb moves slowly across her knuckle. A habitual gesture, done without thinking. "
         "Fingers laced together, completely relaxed. "
         "The certainty of two people who have held this position a thousand times. "
         "Warm golden light. Very slow camera drift. @Audio1 pacing. {style}"
     )},

    # ECU FACES 131-160s
    {"id": "ecus_2000_sofia_happy", "dur": "5", "era": "2000", "anchor": False,
     "chars": ["sofia_2000"],
     "audio_seg": (131, 136),
     "prompt": (
         "Extreme close-up of @Image1 as Sofia (22) face. "
         "She is looking slightly off-camera — at him — and she does not know anyone is watching. "
         "This is not a performance of happiness. "
         "She is just happy, in the way that only happens when you forget to protect yourself. "
         "Eyes bright, completely present, mid-breath between laughs. "
         "Golden warm light. @Audio1 pacing. {style}"
     )},
    {"id": "ecus_2000_marcus_laughing", "dur": "5", "era": "2000", "anchor": False,
     "chars": ["marcus_2000"],
     "audio_seg": (136, 141),
     "prompt": (
         "Extreme close-up of @Image1 as Marcus (26) face, laughing at something she just said. "
         "He thinks she is the funniest person alive and he is not hiding it. "
         "Eyes crinkled shut, head tilted back slightly. "
         "When the laugh subsides he looks back toward her with warmth still all over his face. "
         "Golden café light. @Audio1 pacing. {style}"
     )},
    {"id": "ecus_2025_sofia_tears", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["sofia_2025"],
     "audio_seg": (141, 146),
     "prompt": (
         "Extreme close-up of @Image1 as Sofia (47) face. "
         "A tear has already fallen — she is not crying now, she has been crying and has stopped. "
         "She looks directly into the camera. Jaw set. "
         "She is trying to hold herself together and she has decided something. "
         "Not performance — controlled grief that is almost anger. "
         "Cold blue-grey light cuts across one side of her face. @Audio1 emotional pacing. {style}"
     )},
    {"id": "ecus_2025_marcus_window", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["marcus_2025"],
     "audio_seg": (146, 151),
     "prompt": (
         "Extreme close-up of @Image1 as Marcus (51) face at an apartment window at night. "
         "Rain traces down the glass outside. Cold window light on his face. "
         "He looks out — expression distant and quiet. "
         "Photorealistic, clean facial render — no squares, blocks, or artifacts on his face. "
         "His reflection barely visible in the glass. Camera holds still. @Audio1 pacing. {style}"
     )},
    {"id": "ecus_2025_sofia_photo", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["sofia_2025"],
     "audio_seg": (151, 156),
     "prompt": (
         "Close-up of @Image1 as Sofia (47) holding a small card or photograph. "
         "The back faces us — we see handwritten text on the blank side, a few lines, ink faded. "
         "Sofia holds it so we see the writing but not what it says. "
         "Her thumb traces the edge slowly. Her face above: quiet, careful. "
         "The other side of the card is a photo — she does not turn it over. "
         "Cold light. @Audio1 pacing. {style}"
     )},
    {"id": "ecus_2025_marcus_phone", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["marcus_2025"],
     "audio_seg": (156, 161),
     "prompt": (
         "Close-up of @Image1 as Marcus (51) in a dark room. "
         "He holds a phone loosely at his side — screen not visible, facing away. "
         "His face is lit softly by ambient light from a window, not by the phone. "
         "He looks slightly downward, expression heavy, as if he has just decided not to make a call. "
         "He sets the phone down on a surface slowly. Expression: something resigned. "
         "@Audio1 pacing. {style}"
     )},

    # OUTRO 160-184s
    {"id": "alone_2025_sofia_jacket", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["sofia_2025"],
     "audio_seg": (160, 165),
     "prompt": (
         "@Image1 as Sofia (47) stands in her apartment. She is holding a man's jacket — "
         "old, not hers. She picked it up automatically without deciding to. "
         "She realises she is holding it and looks down at it. "
         "Then she presses it slowly to her chest, arms folding around it, eyes closing. "
         "She is not performing grief. She just cannot put it down. "
         "Cold window light. @Audio1 pacing. {style}"
     )},
    {"id": "alone_2025_marcus_bridge", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["marcus_2025"],
     "audio_seg": (160, 165),
     "prompt": (
         "@Image1 as Marcus (51) stands on a bridge at night, seen from behind. "
         "He stands with his back to camera, looking out at the city in the distance. "
         "Blurred city lights and their reflections fill the background — warm and far away. "
         "He is still and upright, hands in his coat pockets, not touching the railing. "
         "The distance between him and those lights feels immense. "
         "Camera holds on his back. He does not turn. @Audio1 pacing. {style}"
     )},
    {"id": "bridge_2000", "dur": "5", "era": "2000", "anchor": False,
     "chars": ["sofia_2000", "marcus_2000"],
     "audio_seg": (165, 170),
     "prompt": (
         "@Image1 as Sofia and @Image2 as Marcus lean over the same bridge railing in summer, 2000. "
         "Golden evening light. They are playing a game — "
         "looking down at the water trying to spot something, pointing, arguing about what they see. "
         "She grabs his arm to show him. He leans over further to look. "
         "Completely careless and alive. Warm light. @Audio1 pacing. {style}"
     )},
    {"id": "alone_2025_sofia_walking_away", "dur": "5", "era": "2025", "anchor": False,
     "chars": ["sofia_2025"],
     "audio_seg": (170, 175),
     "prompt": (
         "@Image1 as Sofia (47) walks away from camera down a rain-soaked city street at night. "
         "She reaches the spot where they used to always stop — "
         "she almost slows, almost stops. Then she doesn't. She keeps walking. "
         "The camera stays fixed as she gets smaller. Cold grey light. "
         "The street is empty behind her and in front of her. @Audio1 pacing. {style}"
     )},
    {"id": "outro_sofia_window", "dur": "10", "era": "2025", "anchor": False,
     "chars": ["sofia_2025"],
     "audio_seg": (174, 184),
     "prompt": (
         "@Image1 as Sofia (47) stands at her apartment window at night, one hand against the cold glass. "
         "Same as we first saw her. She has come back to this. "
         "Rain runs down the outside. Her reflection is faint in the glass — "
         "she and the empty street below occupy the same space. "
         "She watches the reflection more than the street. "
         "Very slowly she removes her hand from the glass. "
         "She stands without touching anything. Camera holds. Very slow fade to black. "
         "@Audio1 carries the final emotional resolution. {style}"
     )},

    # ENDING — bridge reunion 2025
    {"id": "reunion_bridge_2025", "dur": "10", "era": "2025", "anchor": False,
     "chars": ["sofia_2025", "marcus_2025"],
     "audio_seg": (174, 184),
     "prompt": (
         "Night on a city bridge. @Image2 as Marcus (51) stands from behind, looking out at the city lights. "
         "Rain has stopped. The blurred city glow reflects on the wet railing. "
         "Then @Image1 as Sofia (47) enters frame from behind him. "
         "She stops. She reaches out and places one hand gently on his shoulder. "
         "He goes still for a moment — then slowly turns around. "
         "Their faces come into frame together. Their eyes meet. "
         "Neither speaks yet. Something in both of them releases — "
         "not happiness exactly, but the end of carrying it alone. "
         "A shared exhale. Then the faintest beginning of a smile on both of them. "
         "Camera holds close on their faces. Warm city light. @Audio1 carries the resolution. {style}"
     )},
]

# Scene number lookup (used for numbered filenames)
SCENE_NUMBERS = {s["id"]: i + 1 for i, s in enumerate(SCENES)}

# ── URL cache ─────────────────────────────────────────────────────────────────
CACHE_FILE = MV_DIR / "urls_seedance.json"

def load_cache():
    return json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}

def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")

def upload(filepath, cache, key):
    if key in cache:
        return cache[key]
    print(f"  Uploading {Path(filepath).name}...")
    url = fal_client.upload_file(str(filepath))
    cache[key] = url
    save_cache(cache)
    print(f"  -> {url[:60]}...")
    return url


def extract_audio_segment(start_sec, end_sec, cache_dir):
    """Extract a short segment of the song for @Audio1 beat-sync guidance."""
    seg_id = f"audio_{start_sec}_{end_sec}"
    seg_path = cache_dir / f"{seg_id}.mp3"
    if not seg_path.exists():
        FFMPEG_DIR = r"C:\Users\ari_v\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
        FFMPEG = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
        subprocess.run([
            FFMPEG, "-y",
            "-ss", str(start_sec), "-t", str(end_sec - start_sec),
            "-i", AUDIO_IN,
            "-c:a", "libmp3lame", "-q:a", "4",
            str(seg_path)
        ], capture_output=True, timeout=30, check=True)
    return str(seg_path)


def build_prompt(scene):
    style = STYLES.get(scene.get("era", "both"), STYLES["both"])
    return scene["prompt"].replace("{style}", style)


def generate(scene, cache, audio_cache_dir):
    num = SCENE_NUMBERS.get(scene["id"], 0)
    out = SCENES_DIR / f"{num:03d}_{scene['id']}.mp4"
    if out.exists() and out.stat().st_size > 200_000:
        print(f"  [cached] {scene['id']}")
        return str(out)

    prompt = build_prompt(scene)
    chars = scene.get("chars", [])

    # ── Upload character images ────────────────────────────────────────────────
    image_urls = []
    for char_id in chars:
        char_file = CHARS_DIR / CHAR_REFS[char_id]
        if char_file.exists():
            url = upload(str(char_file), cache, f"char:{char_id}")
            image_urls.append(url)
        else:
            print(f"  [warn] Missing char image: {char_file}")

    # ── Upload audio segment ───────────────────────────────────────────────────
    audio_urls = []
    if scene.get("audio_seg") and Path(AUDIO_IN).exists():
        start, end = scene["audio_seg"]
        try:
            seg_path = extract_audio_segment(start, end, audio_cache_dir)
            audio_url = upload(seg_path, cache, f"audio:{start}_{end}")
            audio_urls.append(audio_url)
        except Exception as e:
            print(f"  [warn] Audio segment failed: {e}")

    # ── Build Seedance arguments ───────────────────────────────────────────────
    n_imgs   = len(image_urls)
    n_audio  = len(audio_urls)
    img_tags  = " ".join(f"@Image{i+1}" for i in range(n_imgs))
    aud_tag   = "@Audio1" if n_audio else ""

    # Replace placeholder tags in prompt
    # (prompts already use @Image1/@Image2/@Audio1 directly)

    args = {
        "prompt": prompt,
        "negative_prompt": NEG,
        "duration": scene["dur"],
        "aspect_ratio": "16:9",
        "generate_audio": False,   # we have the master track — don't add AI audio
    }
    if image_urls:
        args["image_urls"] = image_urls
    if audio_urls:
        args["audio_urls"] = audio_urls

    mode = f"ref-to-video ({n_imgs} imgs, {n_audio} audio)"
    print(f"  {mode} ({scene['dur']}s) [{scene.get('era','?')}]: {scene['id']}")

    result = fal_client.subscribe(MODEL, arguments=args, with_logs=False)
    url = result["video"]["url"]

    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(out, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            if chunk: f.write(chunk)

    mb = out.stat().st_size / 1024 / 1024
    print(f"  Saved {out.name} ({mb:.1f} MB)")
    return str(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refs-only", action="store_true",
                        help="Generate only 3 anchor clips for review")
    parser.add_argument("--scene", help="Regenerate one scene by ID")
    parser.add_argument("--force", action="store_true",
                        help="Ignore cache, regenerate selected scenes")
    args = parser.parse_args()

    # Check char images exist
    chars_manifest = CHARS_DIR / "chars_manifest.json"
    if not chars_manifest.exists():
        print("ERROR: Run mv_generate_chars.py first to generate character images.")
        return
    missing_chars = [k for k, v in CHAR_REFS.items()
                     if not (CHARS_DIR / v).exists()]
    if missing_chars:
        print(f"ERROR: Missing character images: {missing_chars}")
        print("Run: python mv_generate_chars.py")
        return

    # Audio cache dir
    audio_cache = MV_DIR / "audio_segments"
    audio_cache.mkdir(exist_ok=True)

    cache = load_cache()

    # Select scenes
    if args.scene:
        scenes_to_run = [s for s in SCENES if s["id"] == args.scene]
        if not scenes_to_run:
            print(f"ERROR: '{args.scene}' not found"); return
    elif args.refs_only:
        scenes_to_run = [s for s in SCENES if s.get("anchor")]
    else:
        scenes_to_run = SCENES

    if args.force:
        for s in scenes_to_run:
            num = SCENE_NUMBERS.get(s["id"], 0)
            p = SCENES_DIR / f"{num:03d}_{s['id']}.mp4"
            if p.exists(): p.unlink()
        cache = {k: v for k, v in cache.items() if not k.startswith("audio:")}
        save_cache(cache)

    # Cost estimate (Fast: $0.2419/s)
    total_s = sum(int(s["dur"]) for s in scenes_to_run)
    cost    = total_s * 0.2419
    print("=" * 65)
    print("Missing You × Seedance 2.0 — Scene Generation")
    print(f"Model  : {MODEL}")
    print(f"Scenes : {len(scenes_to_run)} | {total_s}s total video")
    print(f"Est.   : ~${cost:.2f} USD")
    print("=" * 65)

    results = []
    for i, scene in enumerate(scenes_to_run, 1):
        print(f"\n[{i}/{len(scenes_to_run)}] {scene['id']}")
        try:
            path = generate(scene, cache, audio_cache)
            if path:
                results.append({**scene, "path": path})
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

    manifest_path = MV_DIR / "scenes_manifest.json"
    existing = {}
    if manifest_path.exists():
        for entry in json.loads(manifest_path.read_text(encoding="utf-8")):
            existing[entry["id"]] = entry
    for r in results:
        existing[r["id"]] = r
    manifest_path.write_text(json.dumps(list(existing.values()), indent=2), encoding="utf-8")

    print(f"\nDone: {len(results)}/{len(scenes_to_run)}")
    if args.refs_only:
        print("Tarkista ankkuriklippit, sitten aja ilman --refs-only")
    else:
        print("Seuraava: python mv_assemble.py")


if __name__ == "__main__":
    main()
