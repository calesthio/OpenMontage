"""
create_documentary_short.py
One-Command Single-Documentary Continuous Story Short Pipeline.

Downloads a 1080p nature documentary for the target animal, detects scene
boundaries, and compiles a 9:16 vertical Short with AI narration, SFX, and BGM.

Usage:
  python scripts/create_documentary_short.py --animal tiger
  python scripts/create_documentary_short.py --animal lion --banner "SAVANNA KING"
  python scripts/create_documentary_short.py --animal wolf --no-download
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

HOOK_STYLES = {
    "default":    "WILD & UNTAMED",
    "mysterious": "SILENT PREDATOR",
    "powerful":   "APEX PREDATOR",
    "majestic":   "KING OF THE WILD",
    "stealthy":   "HIDDEN HUNTER",
}

ANIMAL_THEMES = {
    "tiger":   ("tiger",   "The Silent Bengal Hunter",     "TIGER: SILENT STALKER",    "stealthy"),
    "lion":    ("lion",    "The Pride Sovereign",           "LION: SAVANNA KING",       "majestic"),
    "wolf":    ("wolf",    "Untamed Wolf Pack",             "WOLF: PACK LAW",           "powerful"),
    "bear":    ("bear",    "The Mighty Grizzly",            "BEAR: WILD FORCE",         "powerful"),
    "leopard": ("leopard", "Ghost of the Treetops",         "LEOPARD: SHADOW HUNTER",   "stealthy"),
    "cheetah": ("cheetah", "Born to Run",                   "CHEETAH: SPEED DEMON",     "mysterious"),
    "eagle":   ("eagle",   "Wings of the Mountain",         "EAGLE: SKY SOVEREIGN",     "majestic"),
    "shark":   ("shark",   "The Ocean Predator",            "SHARK: DEEP TERROR",       "powerful"),
    "elephant":("elephant","Gentle Giant of the Savannah",  "ELEPHANT: ANCIENT SOUL",   "majestic"),
    "orca":    ("orca",    "The Sea Wolf",                  "ORCA: OCEAN'S APEX",       "powerful"),
    "crocodile":("crocodile","Ambush in the Shallows",      "CROCODILE: PRIMEVAL HUNTER","mysterious"),
    "snake":   ("snake",   "Venom and Precision",           "SNAKE: SILENT DEATH",      "stealthy"),
    "hyena":   ("hyena",   "Laughter in the Dark",          "HYENA: CUNNING SCAVENGER", "mysterious"),
    "rhino":   ("rhino",   "Armored Titan",                 "RHINO: UNSTOPPABLE FORCE", "powerful"),
    "gorilla": ("gorilla", "Strength of the Mountain",      "GORILLA: GENTLE GIANT",    "majestic"),
}


ANIMAL_STORIES = {
    "wolf": [
        "Across the frozen wilderness, temperatures drop to thirty below zero.",
        "For the pack, survival in the dead of winter is a relentless race against starvation.",
        "The alpha leads the patrol, reading faint traces of scent left in the snow.",
        "Every footstep is measured, conserving precious energy across vast arctic distances.",
        "Suddenly, the lead scout freezes, locking eyes on movement at the tree line.",
        "In silence, the pack splits into formation, flanking their target from both sides.",
        "The distance closes, heartbeat by heartbeat, until the tension breaks.",
        "With explosive speed, the pack surges across the open tundra in perfect unison.",
        "The prey scatters in panic, but the wolves' coordination is unbroken.",
        "Through teamwork and unyielding endurance, the alpha closes the final gap.",
        "One decisive strike seals the hunt, ensuring the pack survives another brutal winter night.",
        "As darkness settles over the frozen forest, the wolves sing their ancient victory song.",
    ],
    "polar_bear": [
        "In the vast frozen kingdom of the Arctic, sea ice is rapidly shifting.",
        "A solitary polar bear navigates the treacherous frozen expanse.",
        "Enduring sub-zero blizzards, this apex hunter possesses an acute sense of smell.",
        "It catches the faint scent of a seal breathing hole miles away.",
        "Moving with impossible stealth across the snow, every step is calculated.",
        "Hours pass in near-motionless patience under the bitter arctic wind.",
        "A ripple in the dark water beneath the ice breaks the silence.",
        "In a fraction of a second, raw power explodes through the frozen surface.",
        "Strength, patience, and ancient instinct turn freezing isolation into survival.",
        "The king of the Arctic reigns supreme over the edge of the world.",
    ],
    "tiger": [
        "Deep in the mist of the Bengal jungle, shadows conceal a master of the hunt.",
        "A Bengal tiger prowls its ancestral territory with complete silence.",
        "Every muscle is coiled, listening to the alarm calls of the canopy above.",
        "It calculates the wind direction, staying hidden beneath the dense foliage.",
        "A single mistake will alert the entire forest and ruin hours of stalking.",
        "The target draws near, unaware of the amber eyes watching from the brush.",
        "In one breathtaking explosion of speed and power, the tiger launches forward.",
        "Through dense thorns and water, the apex predator secures its reign.",
        "This is the untamed spirit of the wild, unmatched in majesty and force.",
    ],
    "lion": [
        "Across the sun-scorched savanna, heat waves distort the endless horizon.",
        "A pride of lions guards their sacred hunting grounds against invading rivals.",
        "The lionesses move like phantoms through the golden grass.",
        "They read the wind and coordinate their positions with unspoken precision.",
        "When the moment arrives, the savanna erupts into high-stakes pursuit.",
        "Power, strategy, and sheer collective force overcome the swiftest prey.",
        "The roar of the pride echoes across the plains, declaring their sovereign rule.",
    ],
    "orca": [
        "In the icy depths of the open ocean, the wolves of the sea assemble.",
        "An orca pod navigates the currents with sophisticated acoustic communication.",
        "Working as a synchronized tactical unit, they locate their prey near the surface.",
        "They create deliberate ocean waves, washing over the ice floes with terrifying intelligence.",
        "With unmatched power and agility, the apex predators rule the global seas.",
    ],
}


def _generate_script_template(animal: str) -> dict:
    animal_key = animal.lower().strip().replace(" ", "_")
    _, title, banner, style = ANIMAL_THEMES.get(
        animal_key,
        (animal_key, f"The Wild {animal.title()}", f"{animal.upper()}: UNTAMED", "default")
    )

    if animal_key in ANIMAL_STORIES:
        story_lines = ANIMAL_STORIES[animal_key]
        template_scenes = [{"text": line} for line in story_lines]
    else:
        opening = {
            "stealthy": f"In the shadows of its territory, the {animal} moves without a sound.",
            "powerful": f"Raw power courses through every fiber of the {animal}'s muscular frame.",
            "majestic": f"Across the vast landscape, the {animal} surveys its ancient kingdom.",
            "mysterious": f"Deep in the wilderness, the elusive {animal} lives by its own secret code.",
            "default": f"The {animal} embodies the raw spirit of the untamed wilderness.",
        }[style]
        template_scenes = [
            {"text": opening},
            {"text": f"Here, every single day begins with a high-stakes test of endurance."},
            {"text": "Its senses are razor-sharp, attuned to every subtle change in the environment."},
            {"text": "The hunter reads the wind, tracking invisible trails across the landscape."},
            {"text": "A sudden shift in the terrain forces an immediate and calculated decision."},
            {"text": "Patience and precision are the only currency that matters in the wild."},
            {"text": "Then, the opportunity presents itself, and instinct takes absolute command."},
            {"text": "With explosive power, the predator strikes at the decisive moment."},
            {"text": "Strength and experience turn immense risk into a triumphant reward."},
            {"text": f"That is how the {animal} rules this untamed domain."},
        ]

    return {
        "title": title,
        "hook_banner": banner,
        "voice": "en-GB-RyanNeural",
        "scenes": template_scenes,
    }


def _generate_with_llm(animal: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
    if not api_key:
        return _generate_script_template(animal)

    import urllib.request
    prompt = (
        f"Write a 14-beat dramatic narration script for a 60 to 72 second nature documentary "
        f"YouTube Short about {animal}s. Each sentence becomes one voiceover scene. "
        f"The beats must form a complete arc: hook, habitat, adaptation, goal, escalating risk, "
        f"setback, decision, climax, recovery, and payoff. "
        f"Style: dramatic, David Attenborough-like, powerful, cinematic. "
        f"Use 12 to 18 words per sentence. "
        f"Output ONLY valid JSON like: "
        f'{{"title": "...", "hook_banner": "{animal.upper()}: ...", '
        f'"scenes": [{{"text": "..."}}, ...]}}'
    )
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps({
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
            }).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"]
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("\n```", 1)[0]
        result = json.loads(content)
        result.setdefault("voice", "en-US-ChristopherNeural")
        print(f"[LLM] Generated script: \"{result.get('title', '...')}\"")
        return result
    except Exception as e:
        print(f"[WARN] LLM generation failed ({e}), using template.")
        return _generate_script_template(animal)


def main():
    parser = argparse.ArgumentParser(
        description="Create a single-documentary continuous story Short video.",
    )
    parser.add_argument(
        "--animal", type=str, default="tiger",
        help="Target animal for the documentary short.",
    )
    parser.add_argument(
        "--banner", type=str, default=None,
        help="Override the top hook banner text.",
    )
    parser.add_argument(
        "--title", type=str, default=None,
        help="Override the video title.",
    )
    parser.add_argument(
        "--no-download", action="store_true",
        help="Skip documentary download (use cached if available).",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Skip LLM script generation; use template scripts.",
    )
    parser.add_argument(
        "--resolution", type=str, default="1080p",
        choices=["720p", "1080p", "4k"],
        help="Target documentary resolution.",
    )
    parser.add_argument(
        "--source-url", type=str, default=None,
        help="Pinned documentary URL. Recommended for semantic source continuity.",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Custom output MP4 path.",
    )
    parser.add_argument(
        "--original-audio", "--original-voice", action="store_true", default=False,
        help="Use original documentary audio and narrator voice to preserve authentic animal sounds and surroundings.",
    )
    args = parser.parse_args()

    animal = args.animal.lower().strip()

    print("=" * 60)
    print(f"  OpenMontage | Single-Documentary Short Pipeline")
    print(f"  Animal: {animal.upper()}  |  Resolution: {args.resolution}")
    print(f"  Audio Mode: {'ORIGINAL SOURCE AUDIO' if args.original_audio else 'SYNTHESIZED NARRATION'}")
    print("=" * 60)

    # ---- Script generation ----
    if args.no_llm:
        script_data = _generate_script_template(animal)
    else:
        script_data = _generate_with_llm(animal)

    if args.title:
        script_data["title"] = args.title
    if args.banner:
        script_data["hook_banner"] = args.banner

    print(f"\n  Title:   {script_data['title']}")
    print(f"  Banner:  {script_data['hook_banner']}")
    print(f"  Scenes:  {len(script_data['scenes'])}")
    for i, s in enumerate(script_data["scenes"], 1):
        print(f"           {i}. {s['text']}")
    print()

    # ---- Build engine & render ----
    t0 = time.time()

    from lib.documentary_story_engine import DocumentaryStoryEngine

    engine = DocumentaryStoryEngine(animal=animal, source_url=args.source_url)

    output_path = Path(args.output) if args.output else None
    result = engine.render_continuous_short(
        script_data,
        output_path=output_path,
        use_original_audio=args.original_audio,
    )

    elapsed = time.time() - t0

    print("\n" + "=" * 60)
    print(f"  PRODUCTION COMPLETE  ({elapsed:.0f}s)")
    print(f"  Output: {result}")
    print("=" * 60)

    # ---- Quick verification ----
    import subprocess
    ver = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(result)],
        capture_output=True, text=True,
    )
    if ver.returncode == 0:
        probe = json.loads(ver.stdout)
        for s in probe.get("streams", []):
            if s["codec_type"] == "video":
                print(f"\n  Resolution: {s.get('width')}x{s.get('height')}")
                print(f"  Codec:      {s.get('codec_name')}")
                print(f"  Duration:   {float(s.get('duration', 0)):.1f}s")
            elif s["codec_type"] == "audio":
                print(f"  Audio:      {s.get('codec_name')} {s.get('sample_rate')}Hz "
                      f"{s.get('channels')}ch")


if __name__ == "__main__":
    main()
