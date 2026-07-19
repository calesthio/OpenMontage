"""Build the permanent, deduped music library at X:\\music-library.

WHY X: and not the repo — every track currently lives under projects/, which .gitignore line 29
excludes and which AGENT_GUIDE describes as "regenerable". Music that costs money to generate
and effort to audition is NOT regenerable. X: is the durable asset drive (X:\\allcounty,
X:\\Lucciano already live there), so the master goes there and survives a repo wipe/reclone.

Re-runnable: safe to run again to fold in new tracks. Never deletes.
"""
import hashlib
import json
import os
import shutil
import subprocess

DEST = r"X:\music-library"
SOURCES = [
    r"C:\dev\OpenMontage\projects\lucciano-campaign\public\music",
    r"C:\dev\OpenMontage\projects\lucciano-contact-sheet\public\music",
    r"C:\dev\OpenMontage\music_library",
]

# Provenance captured from the pixabay_music / ElevenLabs tool responses at download time.
# slug -> (title, artist, source, licence, notes)
PX = "Pixabay Content License — free commercial use, no attribution required"
EL = "ElevenLabs Music — generated; commercial licence per ElevenLabs paid plan"
META = {
    # --- ElevenLabs generated (bespoke, written to an edit) ---
    "el_bass": ("Lucciano Campaign — Dark Bass", "ElevenLabs (generated)", "elevenlabs", EL,
                "USED: lucciano-campaign final. 128bpm dark electronic. Written TO the edit: "
                "drop at 11.8s, strip at 16.8s. Verified peak@11.5s."),
    "el_afro": ("Lucciano Campaign — Afro House", "ElevenLabs (generated)", "elevenlabs", EL,
                "120bpm afro-house. Rejected: peaked at 6.5s and plateaued, no drop at 11.8s."),
    "el_perc": ("Lucciano Campaign — Percussive Techno", "ElevenLabs (generated)", "elevenlabs", EL,
                "124bpm minimal techno. Rejected: energy INVERTED at the 11.8s drop."),
    # --- Pixabay: fashion / house ---
    "w_afro_house_percussion": ("Afro House", "ArtIssizm", "pixabay", PX, "Used in an earlier campaign cut. 97 onsets/24s. Modern fashion sound."),
    "en_energetic_fashion_beat_drop": ("Fashion Beat", "The_Mountain", "pixabay", PX, "Shipped once; user called it awful. Generic."),
    "px_deep_house_fashion_runway": ("Fashion Runway", "BerryDeep", "pixabay", PX, "Used in lucciano-contact-sheet final. Deep house, steady groove."),
    "px_minimal_fashion_house_beat": ("Minimal House", "Monume", "pixabay", PX, ""),
    "px_cinematic_fashion": ("Fashion Show", "MondaMusic", "pixabay", PX, ""),
    "px_minimal_downtempo_editorial": ("Inspiring Downtempo", "Kulakovka", "pixabay", PX, "Groove lurches (steady 0.42)."),
    "w_electro_house_peak_time": ("Electro", "Kulakovka", "pixabay", PX, ""),
    "w_hard_bass_slap_house": ("Beach House Dance", "quincy-house", "pixabay", PX, ""),
    "w_melodic_techno_emotional": ("Melodic Techno 03", "vjgalaxy", "pixabay", PX, ""),
    "w_industrial_techno_warehouse": ("Warehouse Bass Tech Outro", "OpenMindAudio", "pixabay", PX, ""),
    "px_dark_minimal_techno": ("Techno", "Monume", "pixabay", PX, "NOTE: identical file to en_hard_techno_drive."),
    "en_hard_techno_drive": ("Techno", "Monume", "pixabay", PX, "Duplicate of px_dark_minimal_techno."),
    # --- Pixabay: beats / street ---
    "w_uk_drill_dark": ("Into The Night (UK Drill)", "kontraa", "pixabay", PX, "Dark, sliding 808s."),
    "en_trap_hard_hitting_beat": ("Hard — Hard Drill Beat", "vaitsez", "pixabay", PX, "Duplicate of en_drill_beat_hard."),
    "en_drill_beat_hard": ("Hard — Hard Drill Beat", "vaitsez", "pixabay", PX, "NOTE: identical file to en_trap_hard_hitting_beat."),
    "en_phonk_drift_aggressive": ("Phonk Drift", "MondaMusic", "pixabay", PX, "Highest raw energy of any stock track (4.868). Reads as drift/flex, not agency."),
    "en_dark_industrial_beat": ("Dark Trap Beat", "SolarFLEX", "pixabay", PX, ""),
    "w_trap_soul_dark_rnb": ("Soul RnB Music", "APALONBeats", "pixabay", PX, ""),
    "w_lofi_hip_hop_boom_bap": ("HipHop Beat Old School Boom Bap", "mirostar", "pixabay", PX, ""),
    "w_cinematic_hip_hop_orchestral": ("Experimental Cinematic Hip-Hop", "Rockot", "pixabay", PX, ""),
    # --- Pixabay: global / dance ---
    "w_amapiano_log_drum": ("Amapiano Type Beat", "Titetunez", "pixabay", PX, ""),
    "w_reggaeton_perreo": ("Reggaeton Perreo Pla Pla", "flakitogilbeatz", "pixabay", PX, ""),
    "w_baile_funk_brazilian": ("Funk Carioca — Favela Funk Fever", "OpenMindAudio", "pixabay", PX, ""),
    "w_jersey_club_bounce": ("Jazz Club — Midnight Club Music", "alex-morgan", "pixabay", PX, "Query said jersey club; result is not."),
    "w_drum_and_bass_liquid": ("Drum & Bass", "AudioDollar", "pixabay", PX, ""),
    "w_breakbeat_energetic": ("Breakbeat", "Monume", "pixabay", PX, ""),
    "en_big_room_energetic_drop": ("Heavy Dubstep Bass Drop EDM", "alex-morgan", "pixabay", PX, ""),
    "en_electronic_energetic_sport": ("Energetic Action Sport", "AlexGrohl", "pixabay", PX, ""),
    "w_hyperpop_glitch_energetic": ("Energetic Pop Music", "GR0ZA", "pixabay", PX, ""),
    # --- Pixabay: atmosphere / cinematic ---
    "w_future_garage_atmospheric": ("Cascade Breathe (Future Garage)", "NverAvetyanMusic", "pixabay", PX, "Atmospheric, editorial."),
    "w_trip_hop_downtempo_moody": ("Trip Hop", "Kulakovka", "pixabay", PX, ""),
    "w_dark_synthwave_retrowave": ("Synthwave", "prettyjohn1", "pixabay", PX, ""),
    "w_brooding_electronic_bass": ("Electronic Bass", "NastelBom", "pixabay", PX, ""),
    "cx_deep_bass_drone_cinematic": ("Drone", "NastelBom", "pixabay", PX, "Used in an earlier campaign cut."),
    "cx_cinematic_tension_minimal": ("Cinematic Tension", "leberch", "pixabay", PX, ""),
    "cx_minimal_suspense_pulse": ("Suspense", "leberch", "pixabay", PX, ""),
    "cx_sparse_piano_tension": ("Tension", "mirostar", "pixabay", PX, "Best rise of the tension set (0.742)."),
    "cx_dark_ambient_drone": ("Dark Ambient Soundscape", "Monume", "pixabay", PX, "No window with a real build."),
    "cx_cinematic_trailer_atmosphere": ("Total War (Epic Action Trailer)", "AudioAtlant", "pixabay", PX, "Scored top on shape, wrong genre — trailer cheese."),
    # --- pre-existing ---
    "hc_uplifting": ("HC Uplifting", "unknown", "user", "unknown — pre-existing in music_library/", "Home Concepts. Provenance not recorded."),
}

CATEGORY = {
    "elevenlabs": "00-generated",
    "user": "01-user-supplied",
}
GENRE_DIR = {
    "w_afro_house_percussion": "02-fashion-house", "en_energetic_fashion_beat_drop": "02-fashion-house",
    "px_deep_house_fashion_runway": "02-fashion-house", "px_minimal_fashion_house_beat": "02-fashion-house",
    "px_cinematic_fashion": "02-fashion-house", "px_minimal_downtempo_editorial": "02-fashion-house",
    "w_electro_house_peak_time": "02-fashion-house", "w_hard_bass_slap_house": "02-fashion-house",
    "w_melodic_techno_emotional": "02-fashion-house", "w_industrial_techno_warehouse": "02-fashion-house",
    "px_dark_minimal_techno": "02-fashion-house", "en_hard_techno_drive": "02-fashion-house",
    "w_uk_drill_dark": "03-beats-street", "en_trap_hard_hitting_beat": "03-beats-street",
    "en_drill_beat_hard": "03-beats-street", "en_phonk_drift_aggressive": "03-beats-street",
    "en_dark_industrial_beat": "03-beats-street", "w_trap_soul_dark_rnb": "03-beats-street",
    "w_lofi_hip_hop_boom_bap": "03-beats-street", "w_cinematic_hip_hop_orchestral": "03-beats-street",
    "w_amapiano_log_drum": "04-global-dance", "w_reggaeton_perreo": "04-global-dance",
    "w_baile_funk_brazilian": "04-global-dance", "w_jersey_club_bounce": "04-global-dance",
    "w_drum_and_bass_liquid": "04-global-dance", "w_breakbeat_energetic": "04-global-dance",
    "en_big_room_energetic_drop": "04-global-dance", "en_electronic_energetic_sport": "04-global-dance",
    "w_hyperpop_glitch_energetic": "04-global-dance",
    "w_future_garage_atmospheric": "05-atmosphere-cinematic", "w_trip_hop_downtempo_moody": "05-atmosphere-cinematic",
    "w_dark_synthwave_retrowave": "05-atmosphere-cinematic", "w_brooding_electronic_bass": "05-atmosphere-cinematic",
    "cx_deep_bass_drone_cinematic": "05-atmosphere-cinematic", "cx_cinematic_tension_minimal": "05-atmosphere-cinematic",
    "cx_minimal_suspense_pulse": "05-atmosphere-cinematic", "cx_sparse_piano_tension": "05-atmosphere-cinematic",
    "cx_dark_ambient_drone": "05-atmosphere-cinematic", "cx_cinematic_trailer_atmosphere": "05-atmosphere-cinematic",
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,bit_rate",
         "-of", "default=nw=1:nk=1", path], capture_output=True, text=True).stdout.split()
    try:
        return round(float(out[0]), 1), int(int(out[1]) / 1000)
    except Exception:
        return None, None


def safe(s):
    return "".join(c if c.isalnum() or c in " -_&" else "_" for c in s).strip()


found = {}
for src in SOURCES:
    if not os.path.isdir(src):
        continue
    for fn in sorted(os.listdir(src)):
        if not fn.lower().endswith(".mp3"):
            continue
        slug = fn[:-4]
        found.setdefault(slug, os.path.join(src, fn))

by_hash, entries, dupes = {}, [], []
for slug, path in sorted(found.items()):
    h = sha(path)
    title, artist, source, lic, notes = META.get(
        slug, (slug.replace("_", " ").title(), "unknown", "unknown", "unknown", ""))
    if h in by_hash:
        dupes.append({"slug": slug, "identical_to": by_hash[h], "sha256": h[:16]})
        print(f"DUP  {slug:34s} == {by_hash[h]}  (not copied twice)")
        continue
    by_hash[h] = slug

    folder = CATEGORY.get(source) or GENRE_DIR.get(slug, "06-unsorted")
    dur, br = probe(path)
    newname = f"{safe(artist)} - {safe(title)}.mp3"
    outdir = os.path.join(DEST, folder)
    os.makedirs(outdir, exist_ok=True)
    dst = os.path.join(outdir, newname)
    if not os.path.exists(dst):
        shutil.copy2(path, dst)
    entries.append({
        "file": f"{folder}/{newname}", "title": title, "artist": artist, "source": source,
        "licence": lic, "duration_s": dur, "bitrate_kbps": br, "sha256": h,
        "original_slug": slug, "notes": notes,
    })
    print(f"OK   {folder}/{newname}   ({dur}s, {br}kbps)")

manifest = {
    "library": DEST,
    "purpose": "Permanent, deduped music library. Master copy — do not delete.",
    "built_from": SOURCES,
    "track_count": len(entries),
    "duplicates_skipped": dupes,
    "tracks": sorted(entries, key=lambda e: e["file"]),
}
with open(os.path.join(DEST, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f"\n{len(entries)} unique tracks, {len(dupes)} duplicates skipped -> {DEST}")
