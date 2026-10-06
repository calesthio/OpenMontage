#!/usr/bin/env python3
"""Try to obtain a real, branded, free web address for A1 Tour and Travels.

Runs from GitHub Actions (full internet). Writes .diagnostics/branded-url.txt.
Everything here is account-free: no tokens, no signups, no cost.
"""
import json
import os
import urllib.error
import urllib.request
import zipfile

SITE_DIR = "a1-tour-and-travels"
NAME = "a1toursandtravel"
LOG = []


def say(msg=""):
    print(msg, flush=True)
    LOG.append(str(msg))


def http(url, method="GET", data=None, headers=None, timeout=90):
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, f"ERROR {e}"


def main():
    say(f"=== branded free URL attempt — {os.popen('date -u').read().strip()} ===")
    say()

    say("-- 1. are the candidate names already taken? --")
    for u in (
        f"https://{NAME}.netlify.app/",
        f"https://{NAME}.surge.sh/",
        f"https://{NAME}.vercel.app/",
    ):
        code, _ = http(u, timeout=30)
        say(f"  {u:<46} http={code}")
    say()

    say("-- 2. anonymous site creation on Netlify (no account, no token) --")
    code, body = http(
        "https://api.netlify.com/api/v1/sites",
        method="POST",
        data=json.dumps({"name": NAME}).encode(),
        headers={"Content-Type": "application/json"},
        timeout=120,
    )
    say(f"  http={code}")
    site = None
    try:
        d = json.loads(body)
        if isinstance(d, dict) and d.get("id"):
            site = d
            say(f"  CREATED   id={d['id']}")
            say(f"  name      = {d.get('name')}")
            say(f"  ssl_url   = {d.get('ssl_url')}")
        else:
            say(f"  refused: {json.dumps(d)[:300]}")
    except Exception:
        say(f"  raw: {body[:300]}")
    say()
    if not site:
        say("=> Netlify anonymous creation did not yield a site. Stopping.")
        write_log()
        return

    sid = site["id"]

    say("-- 3. try to claim the branded name on that site --")
    code, body = http(
        f"https://api.netlify.com/api/v1/sites/{sid}",
        method="PATCH",
        data=json.dumps({"name": NAME}).encode(),
        headers={"Content-Type": "application/json"},
        timeout=90,
    )
    say(f"  http={code}")
    try:
        d = json.loads(body)
        say(f"  name now  = {d.get('name')}")
        say(f"  ssl_url   = {d.get('ssl_url')}")
        say(f"  message   = {d.get('message')}")
    except Exception:
        say(f"  raw: {body[:200]}")
    say()

    say("-- 4. zip the live site and deploy it --")
    zpath = "/tmp/site.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(SITE_DIR):
            dirs[:] = [d for d in dirs if d not in ("domains", "__pycache__")]
            for f in files:
                if f.startswith("build-") and f.endswith(".py"):
                    continue
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, SITE_DIR))
    say(f"  zip size: {os.path.getsize(zpath)//1024} KB")
    with open(zpath, "rb") as fh:
        code, body = http(
            f"https://api.netlify.com/api/v1/sites/{sid}/deploys",
            method="POST",
            data=fh.read(),
            headers={"Content-Type": "application/zip"},
            timeout=300,
        )
    say(f"  deploy http={code}")
    try:
        d = json.loads(body)
        say(f"  deploy id : {d.get('id')}")
        say(f"  state     : {d.get('state')}")
        say(f"  url       : {d.get('ssl_url') or d.get('url')}")
        say(f"  message   : {d.get('message')}")
    except Exception:
        say(f"  raw: {body[:300]}")
    say()

    say("-- 5. verify the deployed site really serves the page --")
    import time
    for url in (f"https://{NAME}.netlify.app/", site.get("ssl_url", "")):
        if not url:
            continue
        for attempt in range(6):
            code, html = http(url, timeout=45)
            if code == 200:
                has_brand = "A1 Tour and Travels" in html
                has_phone = "7888007234" in html
                say(f"  {url} -> http=200, brand={has_brand}, phone={has_phone}, bytes={len(html)}")
                break
            say(f"  {url} -> http={code} (attempt {attempt+1}/6)")
            time.sleep(20)
    write_log()


def write_log():
    os.makedirs(".diagnostics", exist_ok=True)
    with open(".diagnostics/branded-url.txt", "w") as fh:
        fh.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
