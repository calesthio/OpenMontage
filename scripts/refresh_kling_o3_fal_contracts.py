"""Refresh Kling O3 fal contracts from published queue OpenAPI schemas.

No fal jobs are submitted. Run from the repository root after reviewing catalog
changes; only the fal-ai/kling-{video,image}/o3/* entries are replaced.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import quote
from urllib.request import urlopen

CONTRACTS = Path(__file__).resolve().parents[1] / "tools/provider_contracts/fal_models.json"
CATALOG = "https://api.fal.ai/v1/models?q=Kling+O3&limit=100"
OPENAPI = "https://fal.ai/api/openapi/queue/openapi.json?endpoint_id="
EXCLUDE = {"description", "title", "examples", "x-fal-order-properties", "x-fal", "ui", "_fal_ui_field", "limit_description"}


def fetch(url: str) -> dict:
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def is_o3(endpoint: str) -> bool:
    return endpoint.startswith(("fal-ai/kling-video/o3/", "fal-ai/kling-image/o3/"))


def compact(value: Any) -> Any:
    if isinstance(value, list):
        return [compact(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in EXCLUDE:
            continue
        if key == "$ref" and item.startswith("#/components/schemas/"):
            item = item.replace("#/components/schemas/", "#/$defs/", 1)
        result[key] = compact(item)
    return result


def input_schema(document: dict, endpoint: str) -> dict:
    post = document["paths"]["/" + endpoint]["post"]
    ref = post["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    components = document["components"]["schemas"]
    name = ref.rsplit("/", 1)[-1]
    schema = compact(components[name])
    needed = set()

    def collect(value):
        if isinstance(value, dict):
            reference = value.get("$ref", "")
            if reference.startswith("#/$defs/"):
                dependency = reference.rsplit("/", 1)[-1]
                if dependency not in needed:
                    needed.add(dependency)
                    collect(compact(components[dependency]))
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(schema)
    if needed:
        schema["$defs"] = {key: compact(components[key]) for key in sorted(needed)}
    schema["additionalProperties"] = False
    return schema


def main():
    catalog = fetch(CATALOG)
    if catalog.get("has_more") or catalog.get("next_cursor"):
        raise RuntimeError("Kling O3 catalog is paginated; refusing partial refresh")
    endpoints = sorted({item["endpoint_id"] for item in catalog["models"] if is_o3(item["endpoint_id"])})
    if not endpoints:
        raise RuntimeError("Kling O3 catalog returned no endpoints")
    original = json.loads(CONTRACTS.read_text(encoding="utf-8"))
    entries = {}
    for endpoint in endpoints:
        source = OPENAPI + quote(endpoint, safe="/")
        entries[endpoint] = {
            "input_schema": input_schema(fetch(source), endpoint),
            "source": source,
            "verified_on": datetime.date.today().isoformat(),
        }
    rest = {key: value for key, value in original.items() if not is_o3(key)}
    result = {**entries, **rest}
    with tempfile.NamedTemporaryFile("w", dir=CONTRACTS.parent, encoding="utf-8", delete=False) as temp:
        temp.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        temp_path = Path(temp.name)
    os.replace(temp_path, CONTRACTS)
    print(f"Refreshed {len(endpoints)} Kling O3 contracts: {', '.join(endpoints)}")


if __name__ == "__main__":
    main()
