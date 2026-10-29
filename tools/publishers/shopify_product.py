#!/usr/bin/env python3
"""Scrape a Shopify product into structured JSON + downloaded images.

Uses the public ``<product-url>.json`` endpoint that every Shopify storefront
exposes. No API key, no browser, no third-party deps beyond Pillow (optional,
used only to verify downloaded pixel dimensions).

Usage:
    python shopify_product.py <product-url> -o <output-dir> [--no-images]

Writes ``<output-dir>/<handle>/product.json`` and downloads every product
image to the same directory as ``NN_<image_id>.<ext>`` (NN preserves the
Shopify gallery order).
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from html import unescape
from urllib.parse import urlparse, parse_qs, urlunparse

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) shopify_product.py"
TIMEOUT = 30


# --------------------------------------------------------------------------
# URL handling
# --------------------------------------------------------------------------

def parse_product_url(url):
    """Return (json_url, handle, variant_id_or_None) from any product URL.

    Handles query strings (``?variant=123&s=rec``), collection-scoped paths
    (``/collections/x/products/handle``) and trailing slashes.
    """
    parts = urlparse(url)
    if not parts.scheme:
        parts = urlparse("https://" + url)
    if not parts.netloc:
        raise ValueError("not a valid URL: %r" % url)

    segments = [s for s in parts.path.split("/") if s]
    if "products" not in segments:
        raise ValueError("URL has no /products/ segment: %r" % url)
    idx = segments.index("products")
    if idx + 1 >= len(segments):
        raise ValueError("URL has no product handle after /products/: %r" % url)
    handle = segments[idx + 1]
    if handle.endswith(".json") or handle.endswith(".js"):
        handle = handle.rsplit(".", 1)[0]

    variant_id = None
    variants = parse_qs(parts.query).get("variant")
    if variants:
        variant_id = variants[0].strip()

    json_path = "/".join(segments[:idx + 1] + [handle]) + ".json"
    json_url = urlunparse((parts.scheme, parts.netloc, "/" + json_path, "", "", ""))
    return json_url, handle, variant_id


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = resp.read()
    return data if binary else data.decode("utf-8")


# --------------------------------------------------------------------------
# HTML -> plain text
# --------------------------------------------------------------------------

def html_to_text(html):
    """Strip markup, keep paragraph/list line breaks."""
    if not html:
        return ""
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|h[1-6]|tr)>", "\n\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
    text = re.sub(r"(?i)</(li|ul|ol)>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


# --------------------------------------------------------------------------
# Personalisation detection
# --------------------------------------------------------------------------

# (regex, canonical field name, what the buyer supplies)
PERSONALIZATION_HINTS = [
    (r"\bupload(?:ing|ed)?\b.{0,30}\bphoto|\bphoto\b.{0,20}\bupload", "upload_photo", "image"),
    (r"\bcustom(?:ize|ise|izable)?\b.{0,25}\bname|\bname[s]?\b.{0,25}\bcustom", "custom_name", "text"),
    (r"\bpersonaliz(?:e|ed|ation)\b.{0,30}\bname", "custom_name", "text"),
    (r"\bnumber of (?:people|members|pets|names|characters)", "member_count", "number"),
    (r"\byour (?:family'?s? )?names?\b", "custom_name", "text"),
    (r"\bcustom (?:text|message|wording)\b", "custom_text", "text"),
    (r"\benter\b.{0,20}\b(name|text|date)", "custom_text", "text"),
    (r"\bcustom date\b|\bpersonaliz\w+ date\b", "custom_date", "text"),
]


def detect_personalization(product, description_text):
    """Infer personalisation inputs from tags, options and description.

    NOTE: storefront personalisation widgets (Customily, Teeinblue, ...) render
    their field list client-side, so this is inference, not the live form.
    The ``source`` key records that honestly.
    """
    haystack = "\n".join([
        product.get("title") or "",
        product.get("tags") if isinstance(product.get("tags"), str) else " ".join(product.get("tags") or []),
        description_text,
    ]).lower()

    fields = {}
    for pattern, name, kind in PERSONALIZATION_HINTS:
        if re.search(pattern, haystack):
            fields.setdefault(name, {"field": name, "input_type": kind})

    # Product options are real Shopify variant options, not personalisation,
    # but record them so the caller can tell the two apart.
    variant_options = [
        {"name": o.get("name"), "values": o.get("values") or []}
        for o in (product.get("options") or [])
    ]

    return {
        "source": "description_inference",
        "requires_dom_render": True,
        "app": None,
        "is_personalized": bool(fields) or "personalized" in haystack,
        # Deliberately empty: real field names live only in the rendered DOM.
        # Keyword guesses go in inferred_hints so they are never mistaken for
        # actual line-item property names.
        "fields": [],
        "inferred_hints": list(fields.values()),
        "variant_options": variant_options,
        "note": "Personalisation forms on Shopify are rendered client-side and "
                "are NOT in the .json payload. 'fields' is empty by design; "
                "render the page to read the real properties[...] inputs, then "
                "set source to 'rendered_dom'.",
    }


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------

def image_key(src):
    """Dedupe key: path without the ?v= cache-buster."""
    return urlparse(src).path


def extension_for(src):
    ext = os.path.splitext(urlparse(src).path)[1].lower()
    return ext if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif") else ".jpg"


def measure(path):
    """Actual pixel dimensions of a downloaded file, or None."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as im:
            return list(im.size)
    except Exception:
        return None


def download_images(product, out_dir, download=True):
    featured_id = (product.get("image") or {}).get("id")
    images, seen = [], set()
    by_hash = {}

    for image in product.get("images") or []:
        src = image.get("src") or ""
        key = image_key(src)
        if not src or key in seen:
            continue
        seen.add(key)

        position = len(images) + 1
        filename = "%02d_%s%s" % (position, image.get("id"), extension_for(src))
        record = {
            "position": position,
            "id": image.get("id"),
            "src": src,
            "alt": image.get("alt"),
            "declared_width": image.get("width"),
            "declared_height": image.get("height"),
            "is_featured": featured_id is not None and image.get("id") == featured_id,
            "variant_ids": image.get("variant_ids") or [],
            "file": filename,
            # Filled in by a human/vision pass; the scraper cannot judge these.
            "shot_type": None,
            "visual_description": None,
            "reference_quality": None,
            "reference_reason": None,
        }

        if download:
            dest = os.path.join(out_dir, filename)
            try:
                blob = fetch(src, binary=True)
                digest = hashlib.sha256(blob).hexdigest()
                twin = by_hash.get(digest)
                if twin:
                    # Same bytes re-uploaded under a new Shopify image id.
                    # No file of its own; `duplicate_of` points at the one on disk.
                    record["duplicate_of"] = twin["file"]
                    record["file"] = None
                    record["bytes"] = twin.get("bytes")
                    record["downloaded_size"] = twin.get("downloaded_size")
                    record["sha256"] = digest
                    images.append(record)
                    continue
                with open(dest, "wb") as fh:
                    fh.write(blob)
                by_hash[digest] = record
                record["sha256"] = digest
                record["bytes"] = len(blob)
                record["downloaded_size"] = measure(dest)
            except (urllib.error.URLError, OSError) as exc:
                record["download_error"] = str(exc)
                print("  ! failed %s: %s" % (src, exc), file=sys.stderr)

        images.append(record)

    # If Shopify reported no explicit featured image, the first is the hero.
    if images and not any(i["is_featured"] for i in images):
        images[0]["is_featured"] = True
    return images


# --------------------------------------------------------------------------
# Variants
# --------------------------------------------------------------------------

def money(value):
    """Shopify sends prices as strings, and empty string for 'unset'."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_availability(json_url):
    """Per-variant `available`, which the .json endpoint omits.

    Only the ``/products/<handle>.js`` payload carries it. Returns {} if that
    request fails, so availability becomes null rather than a fabricated True.
    """
    try:
        payload = json.loads(fetch(json_url[: -len(".json")] + ".js"))
    except (urllib.error.URLError, ValueError, OSError):
        return {}
    return {
        v.get("id"): v.get("available")
        for v in payload.get("variants") or []
        if v.get("id") is not None
    }


def build_variants(product, wanted_variant_id, availability=None):
    availability = availability or {}
    variants, selected = [], None
    for v in product.get("variants") or []:
        record = {
            "id": v.get("id"),
            "title": v.get("title"),
            "sku": v.get("sku"),
            "price": money(v.get("price")),
            "compare_at_price": money(v.get("compare_at_price")),
            # None (not True) when the .js payload was unavailable.
            "available": availability.get(v.get("id")),
            "position": v.get("position"),
            "options": [v.get(k) for k in ("option1", "option2", "option3") if v.get(k)],
        }
        variants.append(record)
        if wanted_variant_id and str(v.get("id")) == str(wanted_variant_id):
            selected = record

    prices = [v["price"] for v in variants if v["price"] is not None]
    price_range = {
        "min": min(prices) if prices else None,
        "max": max(prices) if prices else None,
    }
    return variants, selected, price_range


def currency_of(product):
    for v in product.get("variants") or []:
        if v.get("price_currency"):
            return v["price_currency"]
    return None


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

# Human/vision judgements the scraper cannot regenerate. A re-run must never
# silently destroy them.
ANNOTATION_KEYS = ("shot_type", "visual_description", "reference_quality", "reference_reason")


def carry_forward_annotations(dest, data):
    """Preserve hand-added annotations across a re-run of the scraper.

    Re-scraping is routine (prices change); re-deriving a visual description is
    not. Image annotations are matched by Shopify image id, and a
    ``personalization`` block that was verified against the rendered DOM
    outranks this tool's keyword inference.
    """
    if not os.path.exists(dest):
        return data
    try:
        with open(dest, encoding="utf-8") as fh:
            old = json.load(fh)
    except (ValueError, OSError):
        return data

    previous = {i.get("id"): i for i in old.get("images") or []}
    for image in data["images"]:
        before = previous.get(image.get("id"))
        if not before:
            continue
        for key in ANNOTATION_KEYS:
            if before.get(key) is not None and image.get(key) is None:
                image[key] = before[key]

    if old.get("reference_summary"):
        data["reference_summary"] = old["reference_summary"]
    if (old.get("personalization") or {}).get("source") == "rendered_dom":
        data["personalization"] = old["personalization"]
    return data


def scrape(url, out_root, download=True):
    json_url, handle, variant_id = parse_product_url(url)
    print("GET %s" % json_url)
    product = json.loads(fetch(json_url))["product"]

    handle = product.get("handle") or handle
    out_dir = os.path.join(out_root, handle)
    os.makedirs(out_dir, exist_ok=True)

    description = html_to_text(product.get("body_html"))
    variants, selected, price_range = build_variants(
        product, variant_id, fetch_availability(json_url)
    )
    if variant_id and selected is None:
        print("  ! variant %s not found in product" % variant_id, file=sys.stderr)

    tags = product.get("tags")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    images = download_images(product, out_dir, download=download)

    data = {
        "source_url": url,
        "json_endpoint": json_url,
        "scrape_method": "shopify_product_json",
        "id": product.get("id"),
        "handle": handle,
        "title": product.get("title"),
        "vendor": product.get("vendor"),
        "product_type": product.get("product_type"),
        "tags": tags or [],
        "published_at": product.get("published_at"),
        "updated_at": product.get("updated_at"),
        "description": description,
        "description_html": product.get("body_html"),
        "currency": currency_of(product),
        "selected_variant_id": int(variant_id) if variant_id and variant_id.isdigit() else variant_id,
        "selected_variant": selected,
        "price_range": price_range,
        "variants": variants,
        "options": [
            {"name": o.get("name"), "position": o.get("position"), "values": o.get("values") or []}
            for o in (product.get("options") or [])
        ],
        "personalization": detect_personalization(product, description),
        "images": images,
        "image_count": len(images),
        "unique_file_count": len({i["file"] for i in images if i.get("file")}),
        "reference_summary": None,
    }

    dest = os.path.join(out_dir, "product.json")
    data = carry_forward_annotations(dest, data)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    print("Wrote %s (%d images)" % (dest, len(images)))
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scrape a Shopify product to JSON + images.")
    ap.add_argument("url", nargs="+", help="Shopify product URL(s)")
    ap.add_argument("-o", "--out", required=True, help="output root directory")
    ap.add_argument("--no-images", action="store_true", help="metadata only")
    args = ap.parse_args(argv)

    failures = 0
    for url in args.url:
        try:
            scrape(url, args.out, download=not args.no_images)
        except (ValueError, urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
            print("FAILED %s: %s" % (url, exc), file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
