#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = DATA / "manifest.json"
OUT = DATA / "secondary_effects.json"

# Change this if you use another locale.
REPOE_GEMS_URL = "https://repoe-fork.github.io/Korean/gems.min.json"


def download_json(url: str):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "poe1-skill-gem-viewer-secondary-effects/1.0"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def secondary_ids_from_chunks() -> set[str]:
    ids: set[str] = set()
    for path in sorted(DATA.glob("gems_*.xml")):
        root = ET.parse(path).getroot()
        for gem in root.findall(".//gem"):
            p = gem.find("./repoeGemData/property[@name='secondary_granted_effect']")
            if p is not None and p.get("type") != "null" and (p.text or "").strip():
                ids.add((p.text or "").strip())
    return ids


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    item_effect_ids = {
        x.get("effectId")
        for x in manifest.get("gems", [])
        if x.get("effectId")
    }

    wanted = secondary_ids_from_chunks()
    # If the target is already a normal gem item, the viewer can load it
    # from the existing split XML, so no need to duplicate it here.
    wanted -= item_effect_ids

    print(f"secondary effects needed: {len(wanted)}")
    source = download_json(REPOE_GEMS_URL)

    missing = sorted(x for x in wanted if x not in source)
    if missing:
        print("WARNING: not found in RePoE:", ", ".join(missing))

    effects = {k: source[k] for k in sorted(wanted) if k in source}
    payload = {
        "format": "poe1-secondary-granted-effects-v1",
        "generatedAtUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": REPOE_GEMS_URL,
        "count": len(effects),
        "effects": effects,
    }

    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({len(effects)} effects)")


if __name__ == "__main__":
    main()
