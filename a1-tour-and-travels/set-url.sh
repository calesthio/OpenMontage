#!/usr/bin/env bash
# =============================================================
# set-url.sh — move the site to a new address in one command
#
#   bash a1-tour-and-travels/set-url.sh https://a1toursandtravel.netlify.app
#
# Rewrites every canonical reference: canonical link, Open Graph /
# Twitter URLs, hreflang, JSON-LD (@id / url), sitemap.xml,
# robots.txt and the docs. Run from the repository root.
#
# Every changed file is backed up as <file>.bak first, so you can undo with:
#   find . -name '*.bak' -exec sh -c 'mv "$1" "${1%.bak}"' _ {} \;
# =============================================================
set -euo pipefail

NEW="${1:-}"
if [ -z "$NEW" ]; then
  echo "Usage: bash a1-tour-and-travels/set-url.sh https://your-new-url [old-url]"
  echo
  echo "The optional second argument overrides the URL being replaced"
  echo "(default: the current raw.githack link)."
  exit 1
fi

NEW="${NEW%/}"
case "$NEW" in
  http://*|https://*) ;;
  *) echo "Error: the URL must start with https:// (got: $NEW)"; exit 1 ;;
esac

OLD="${2:-https://raw.githack.com/snazim0345/OpenMontage/arena/54180390-openmontage/a1-tour-and-travels/index.html}"
OLD_DIR="${OLD%/index.html}"

NEW="$NEW" OLD="$OLD" OLD_DIR="$OLD_DIR" python3 - <<'PY'
import os, pathlib

new     = os.environ['NEW']
old     = os.environ['OLD']
old_dir = os.environ['OLD_DIR']
old_base = old.split('/index.html')[0]          # folder form used in sitemap/robots/meta

# longest first, so the /index.html form is replaced before the folder form
pairs = [(old, new), (old_dir, new), (old_base, new)]
changed = []

for path in pathlib.Path('a1-tour-and-travels').rglob('*'):
    if not path.is_file() or path.suffix == '.bak' or path.name.endswith('.bak'):
        continue
    if path.suffix not in {'.html', '.md', '.xml', '.txt', '.json'}:
        continue
    text = original = path.read_text(encoding='utf-8')
    hits = 0
    for a, b in pairs:
        if a and a in text:
            hits += text.count(a)
            text = text.replace(a, b)
    if hits:
        path.with_suffix(path.suffix + '.bak').write_text(original, encoding='utf-8')
        path.write_text(text, encoding='utf-8')
        changed.append((str(path), hits))

print(f"Replacing: {old}")
print(f"With:      {new}\n")
if not changed:
    print("Nothing to change — no file contained the old URL.")
else:
    for name, hits in sorted(changed):
        print(f"  {hits:3} replacement(s)  {name}")
    print(f"\nFiles changed: {len(changed)}   Total replacements: {sum(h for _, h in changed)}")

# ---- verify the three key files ----
def show(label, path, needle_start):
    p = pathlib.Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding='utf-8').splitlines():
        if needle_start in line:
            print(f"  {label}: {line.strip()[:140]}")
            return
    print(f"  {label}: (reference not found)")

print("\nVerification:")
show('canonical ', 'a1-tour-and-travels/index.html', 'rel="canonical"')
show('og:url    ', 'a1-tour-and-travels/index.html', 'og:url')
show('sitemap   ', 'a1-tour-and-travels/sitemap.xml', '<loc>')
show('robots    ', 'a1-tour-and-travels/robots.txt', 'Sitemap:')
PY

echo
echo "Next: review the diff, then commit and push."
echo "Backups: a1-tour-and-travels/**.bak  (remove them once you're happy)"
