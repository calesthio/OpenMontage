#!/usr/bin/env python3
"""Verify that API keys in .env actually work by making one real call each."""
import os, sys, json, urllib.request, urllib.error
from pathlib import Path

def load_env():
    p = Path(".env")
    if not p.is_file():
        print("ERROR: no .env file here. Are you in the OpenMontage folder?")
        sys.exit(1)
    env = {}
    for line in p.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.split("#")[0].strip().strip('"').strip("'")
        if v:
            env[k.strip()] = v
    return env

def call(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read(300).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(300).decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)

env = load_env()
results = []

# --- Pexels ---
k = env.get("PEXELS_API_KEY")
if not k:
    results.append(("Pexels", "NOT SET", "add PEXELS_API_KEY to .env"))
else:
    code, body = call("https://api.pexels.com/v1/search?query=car&per_page=1",
                      {"Authorization": k})
    if code == 200:
        results.append(("Pexels", "WORKING", "real photo search returned results"))
    elif code == 401:
        results.append(("Pexels", "BAD KEY", "server rejected it - recopy from pexels.com/api"))
    else:
        results.append(("Pexels", f"PROBLEM ({code})", body[:120]))

# --- Pixabay ---
k = env.get("PIXABAY_API_KEY")
if not k:
    results.append(("Pixabay", "NOT SET", "add PIXABAY_API_KEY to .env"))
else:
    code, body = call(f"https://pixabay.com/api/?key={k}&q=car&per_page=3")
    if code == 200:
        results.append(("Pixabay", "WORKING", "real photo search returned results"))
    elif code in (400, 401, 403):
        results.append(("Pixabay", "BAD KEY", "server rejected it - recopy from pixabay.com/api/docs"))
    else:
        results.append(("Pixabay", f"PROBLEM ({code})", body[:120]))

# --- Google: two separate services, tested separately ---
k = env.get("GOOGLE_API_KEY") or env.get("GEMINI_API_KEY")
if not k:
    results.append(("Google (all)", "NOT SET", "add GOOGLE_API_KEY to .env"))
else:
    code, body = call(f"https://texttospeech.googleapis.com/v1/voices?key={k}")
    if code == 200:
        results.append(("Google TTS (voiceover)", "WORKING", "voice list retrieved"))
    elif code == 403:
        hint = "key is valid but the Text-to-Speech API is not switched on for this project"
        results.append(("Google TTS (voiceover)", "NEEDS ENABLING", hint))
    elif code == 400:
        results.append(("Google TTS (voiceover)", "BAD KEY", "recopy from aistudio.google.com/apikey"))
    else:
        results.append(("Google TTS (voiceover)", f"PROBLEM ({code})", body[:120]))

    code, body = call(f"https://generativelanguage.googleapis.com/v1beta/models?key={k}")
    if code == 200:
        results.append(("Google AI (images/video)", "WORKING", "model list retrieved"))
    elif code in (400, 403):
        results.append(("Google AI (images/video)", "BAD KEY", "recopy from aistudio.google.com/apikey"))
    else:
        results.append(("Google AI (images/video)", f"PROBLEM ({code})", body[:120]))

print()
print("=" * 68)
print("  API KEY CHECK - real calls, not just 'is it filled in'")
print("=" * 68)
for name, status, note in results:
    mark = "OK  " if status == "WORKING" else "FAIL"
    print(f"  [{mark}] {name:26} {status}")
    print(f"         {note}")
print("=" * 68)
ok = sum(1 for _, s, _ in results if s == "WORKING")
print(f"  {ok} of {len(results)} working")
print()
