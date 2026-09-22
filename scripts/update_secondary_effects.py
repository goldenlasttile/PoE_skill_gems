#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = DATA / "manifest.json"
OUT = DATA / "secondary_effects.json"
REPOE_GEMS_URL = "https://repoe-fork.github.io/Korean/gems.min.json"

def is_royale(effect_id: str | None, item_id: str | None = None) -> bool:
    return "Royale" in (effect_id or "") or "Royale" in (item_id or "")

def download_json(url: str):
    req = urllib.request.Request(
        url,
        headers={"User-Agent":"poe1-skill-gem-viewer-secondary-builder/2.0"}
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)

def referenced_secondary_ids():
    wanted=set()
    for path in sorted(DATA.glob("gems_*.xml")):
        root=ET.parse(path).getroot()
        for gem in root.findall(".//gem"):
            eid=gem.get("effectId")
            iid=gem.get("itemId")
            if is_royale(eid,iid):
                continue
            p=gem.find("./repoeGemData/property[@name='secondary_granted_effect']")
            if p is not None and p.get("type")!="null" and (p.text or "").strip():
                wanted.add((p.text or "").strip())
    return wanted

def main():
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    normal_item_effects={
        g.get("effectId") for g in manifest.get("gems",[])
        if g.get("effectId") and not is_royale(g.get("effectId"),g.get("itemId"))
    }

    # References that already point to an ordinary gem (e.g. Vaal Fireball -> Fireball)
    # are loaded directly from gems_*.xml by the viewer.
    wanted=referenced_secondary_ids()-normal_item_effects

    source=download_json(REPOE_GEMS_URL)
    missing=sorted(x for x in wanted if x not in source)
    if missing:
        raise SystemExit(
            "RePoE is missing referenced secondary effects: "+", ".join(missing)
        )

    effects={k:source[k] for k in sorted(wanted)}
    payload={
        "format":"poe1-secondary-granted-effects-v2",
        "generatedAtUtc":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source":REPOE_GEMS_URL,
        "count":len(effects),
        "effects":effects
    }
    OUT.write_text(
        json.dumps(payload,ensure_ascii=False,separators=(",",":")),
        encoding="utf-8"
    )
    print(f"wrote {OUT}: {len(effects)} non-item secondary effects")

if __name__=="__main__":
    main()
