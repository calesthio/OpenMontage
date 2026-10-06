#!/usr/bin/env python3
"""Try to claim a branded short link named exactly 'a1toursandtravel'.

Short links need no account, no domain, no money — and some allow choosing the alias.
If it works, the owner gets https://is.gd/a1toursandtravel today, which looks branded
on a visiting card and in an SMS even before the real domain is approved.
Writes/append to .diagnostics/shortlinks.txt
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://snazim0345.github.io/OpenMontage/"
ALIAS = "a1toursandtravel"
UA = {"User-Agent": "Mozilla/5.0 (compatible; A1TourLinks/1.0)"}
LOG = []


def say(m=""):
    print(m, flush=True)
    LOG.append(str(m))


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), url
    except Exception as e:
        return 0, f"ERROR {e}", url


def try_shortener(name, base, create_url):
    say(f"-- {name} --")
    existing = f"{base}/{ALIAS}"
    code, _, _ = fetch(existing)
    say(f"  {existing} -> http={code}")
    if code == 200:
        say(f"  already exists (that is fine if it points at us — check below)")
    code, body, final = fetch(create_url)
    say(f"  create -> http={code}")
    say(f"  response: {body.strip()[:200]}")
    url = body.strip().split()[-1] if body.strip().startswith("http") else existing
    time.sleep(2)
    code, html, landed = fetch(url)
    good = code == 200 and "7888007234" in html
    say(f"  verify {url} -> http={code} landed={landed[:70]}")
    say(f"  shows our phone number on the landing page: {'YES' if good else 'no'}")
    say()
    return good


def try_1pt():
    """1pt.co allows choosing the short name with no account."""
    say("-- 1pt.co (free API, custom short name) --")
    url = f"https://api.1pt.co/addURL?long={urllib.parse.quote(SITE, safe='')}&short={ALIAS}"
    code, body, _ = fetch(url)
    say(f"  create -> http={code} body={body.strip()[:200]}")
    try:
        d = json.loads(body)
        short = d.get("short")
        if short:
            link = f"https://1pt.co/{short}"
            time.sleep(2)
            c, html, landed = fetch(link)
            good = c == 200 and "7888007234" in html
            say(f"  verify {link} -> http={c} landed={landed[:70]}")
            say(f"  shows our phone number: {'YES' if good else 'no'}")
            say()
            return good
    except Exception:
        pass
    say("  -> not available")
    say()
    return False


def try_spoo():
    """spoo.me accepts a custom alias without an account."""
    say("-- spoo.me (free shortener, custom alias) --")
    data = urllib.parse.urlencode({"url": SITE, "alias": ALIAS}).encode()
    req = urllib.request.Request("https://spoo.me/", data=data,
                                 headers={**UA, "Accept": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read().decode("utf-8", "replace")
            say(f"  create -> http={r.status} body={body.strip()[:200]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        say(f"  create -> http={e.code} body={body.strip()[:200]}")
    except Exception as e:
        say(f"  create failed: {e}")
        body = ""
    m = re.search(r'"short_url"\s*:\s*"(http[^"]+)"', body) or re.search(r'(https://spoo\.me/[A-Za-z0-9_-]+)', body)
    if m:
        link = m.group(1).replace("\\/", "/")
        time.sleep(2)
        c, html, landed = fetch(link)
        good = c == 200 and "7888007234" in html
        say(f"  verify {link} -> http={c} landed={landed[:70]}")
        say(f"  shows our phone number: {'YES' if good else 'no'}")
        say()
        return good
    say("  -> not available")
    say()
    return False


def main():
    say(f"=== branded short links — {time.strftime('%a %d %b %Y %H:%M UTC', time.gmtime())} ===")
    say(f"target site: {SITE}")
    say()
    enc = urllib.parse.quote(SITE, safe="")
    results = {}
    results["is.gd"] = try_shortener(
        "is.gd (free, no account, custom alias)",
        "https://is.gd",
        f"https://is.gd/create.php?format=simple&url={enc}&shorturl={ALIAS}",
    )
    results["v.gd"] = try_shortener(
        "v.gd (same service, different domain)",
        "https://v.gd",
        f"https://v.gd/create.php?format=simple&url={enc}&shorturl={ALIAS}",
    )
    results["1pt.co"] = try_1pt()
    results["spoo.me"] = try_spoo()
    say("-- result --")
    for k, v in results.items():
        say(f"  {k}: {'WORKS — branded short link live' if v else 'not available'}")
    working = [k for k, v in results.items() if v]
    if working:
        say(f"  use: https://{working[0]}/{ALIAS}")

    os.makedirs(".diagnostics", exist_ok=True)
    path = ".diagnostics/shortlinks.txt"
    with open(path, "a") as fh:
        fh.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
