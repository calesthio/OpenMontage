#!/usr/bin/env python3
"""Submit every page of the site to the Wayback Machine (archive.org).

Why: the Internet Archive is free, permanent, needs no account, and its copies are
crawlable — so the pages keep existing and get discovered even beyond search engines.
Writes .diagnostics/archive-submit.txt
"""
import concurrent.futures as cf
import os
import re
import time
import urllib.parse
import urllib.request

BASE = "https://snazim0345.github.io/OpenMontage"
UA = {"User-Agent": "Mozilla/5.0 (compatible; A1TourSiteArchiver/1.0)"}
LOG = []


def get(url, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)


def pages():
    """Every URL in the sitemap, so the archive mirrors exactly the published site."""
    try:
        with open("a1-tour-and-travels/sitemap.xml") as fh:
            locs = re.findall(r"<loc>(.*?)</loc>", fh.read())
    except FileNotFoundError:
        locs = []
    out = []
    for loc in locs:
        loc = loc.strip()
        if loc.rstrip("/") == BASE.rstrip("/"):
            loc = BASE + "/"
        out.append((loc, loc.replace(BASE + "/", "").strip("/") or "index.html"))
    return out


def submit(item):
    url, name = item
    for attempt in range(1, 4):
        code, _ = get("https://web.archive.org/save/" + url)
        if code in (200, 201, 302):
            return f"  {name:<40} submitted  http={code}"
        time.sleep(20 * attempt)
    return f"  {name:<40} NOT submitted (last http={code})"


def verify(item):
    url, name = item
    code, body = get("https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe=""))
    live = '"available": true' in body.replace('"available":true', '"available": true') or '"available":true' in body
    snap = "none"
    m = re.search(r'"url":\s*"(http[^"]+)"', body)
    if m:
        snap = m.group(1)
    return f"  {name:<40} archived={'yes' if live else 'NO'}  {snap[:96]}"


def main():
    items = pages()
    LOG.append(f"=== Wayback submissions — {time.strftime('%a %d %b %Y %H:%M UTC', time.gmtime())} ===")
    LOG.append(f"pages found in sitemap: {len(items)}")
    LOG.append("")
    LOG.append("-- submitting (3 at a time) --")
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        for line in ex.map(submit, items):
            LOG.append(line)
            print(line, flush=True)
    time.sleep(30)
    LOG.append("")
    LOG.append("-- verifying the archive actually took the snapshots --")
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        for line in ex.map(verify, items):
            LOG.append(line)
            print(line, flush=True)

    os.makedirs(".diagnostics", exist_ok=True)
    with open(".diagnostics/archive-submit.txt", "w") as fh:
        fh.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
