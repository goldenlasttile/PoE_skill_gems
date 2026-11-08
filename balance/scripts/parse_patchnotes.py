#!/usr/bin/env python3
"""Convert the official PoE 'New and Changed Gems' forum HTML to balance JSON.

Examples (run from repository root):
    pip install -r balance/scripts/requirements.txt
    python balance/scripts/parse_patchnotes.py \
        --html downloads/3.29.html --patch 3.29 --previous 3.28 \
        --manifest data/manifest.json --output balance/data/3.29.json
    python balance/scripts/parse_patchnotes.py \
        --url https://www.pathofexile.com/forum/view-thread/3987254 \
        --patch 3.29 --previous 3.28 \
        --manifest data/manifest.json --output balance/data/3.29.json

The parser is deliberately conservative: unrecognized sentences are retained as
qualitative changes, never silently treated as buffs/nerfs or assigned made-up numbers.
Check unmatched.json and validation summaries before publishing the full result.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    sys.exit("Missing beautifulsoup4. Run: pip install -r balance/scripts/requirements.txt")

PATTERNS = [
    # key, label, regex, group, direction, unit
    ("manaCost", "마나 비용", r"^Cost\s+([\d,.]+)\s+Mana$", "cost", -1, ""),
    ("lifeCost", "생명력 비용", r"^Cost\s+([\d,.]+)\s+Life$", "cost", -1, ""),
    ("costMultiplier", "소모·점유 배율", r"^Cost\s*(?:&|and)\s*Reservation Multiplier\s+([\d,.]+)%$", "cost", -1, "%"),
    ("castTime", "시전 시간", r"^Cast Time\s+([\d,.]+)\s+sec(?:onds?)?$", "speed", -1, "초"),
    ("attackTime", "공격 시간", r"^Attack Time\s+([\d,.]+)\s+sec(?:onds?)?$", "speed", -1, "초"),
    ("cooldown", "재사용 대기시간", r"^Cooldown Time\s+([\d,.]+)\s+sec(?:onds?)?(?:\s*\([^)]*\))?$", "cooldown", -1, "초"),
    ("damageEffectiveness", "추가 피해 효율", r"^Effectiveness of Added Damage\s+([\d,.]+)%$", "effectiveness", 1, "%"),
    ("crit", "치명타 확률", r"^Critical Strike Chance\s+([\d,.]+)%$", "crit", 1, "%"),
    ("radius", "효과 반경", r"^Base radius is\s+([\d,.]+)\s+metres?$", "radius", 1, "m"),
    ("duration", "기본 지속시간", r"^Base duration is\s+([\d,.]+)\s+seconds?$", "duration", 0, "초"),
    ("debuffDuration", "디버프 지속시간", r"^Base Debuff Duration is\s+([\d,.]+)\s+seconds?$", "duration", 0, "초"),
    ("projectiles", "투사체 수", r"^Fires\s+([\d,.]+)\s+Projectiles$", "projectiles", 1, "개"),
    ("additionalProjectiles", "추가 투사체", r"^Supported Skills fire\s+([\d,.]+)\s+additional Projectiles$", "projectiles", 1, "개"),
    ("lessDamage", "피해 감폭", r"^Supported (?:Triggered )?Skills deal\s+([\d,.]+)%\s+less Damage(?:.*)?$", "supportDamage", -1, "%"),
    ("lessDamage", "피해 감폭", r"^Supported Triggered Spells deal\s+([\d,.]+)%\s+less Damage(?:.*)?$", "supportDamage", -1, "%"),
    ("triggerInterval", "발동 간격", r"^Trigger a Supported Spell every\s+([\d,.]+)\s+seconds?\s+while Channelling Supported Skills$", "speed", -1, "초"),
    ("soulsPerUse", "사용 영혼 소모", r"^Souls Per Use\s+([\d,.]+)$", "cost", -1, ""),
    ("storedUses", "저장 사용 횟수", r"^Can Store\s+([\d,.]+)\s+Uses$", "utility", 1, "회"),
    ("soulGainPrevention", "영혼 획득 방지", r"^Soul Gain Prevention\s+([\d,.]+)\s+sec$", "cooldown", -1, "초"),
]

RANGE_RE = re.compile(r"^(?:Deals\s+)?([\d,.]+)\s+to\s+([\d,.]+)\s+(?:Base\s+)?(?:Off Hand\s+)?(Physical|Fire|Cold|Lightning|Chaos)\s+Damage(.*)$", re.I)
DOT_RE = re.compile(r"^(?:Supported Skills deal |Deals )([\d,.]+)\s+Base\s+(Physical|Fire|Cold|Lightning|Chaos)\s+Damage\s+per\s+second$", re.I)
EN_DAMAGE = {"Physical":"물리","Fire":"화염","Cold":"냉기","Lightning":"번개","Chaos":"카오스"}


def number(s):
    return float(s.replace(",", ""))


def pretty(n):
    if n is None:
        return "-"
    if float(n).is_integer():
        return f"{int(n):,}"
    return f"{n:,.2f}".rstrip("0").rstrip(".")


def normalize_text(s):
    return " ".join(s.replace("\xa0", " ").strip().split())


def normalize_name(s):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", s).lower())


def analyze_line(text):
    text = normalize_text(text)
    for key, label, pattern, group, better_dir, unit in PATTERNS:
        m = re.fullmatch(pattern, text, re.I)
        if m:
            val = number(m.group(1))
            suffix = ""
            if key == "cooldown" and re.search(r"\(\s*\d+\s+uses\)", text, re.I):
                suffix = re.search(r"\(([^)]+)\)", text).group(1)
            return {"key":key,"group":group,"label":label,"value":val,"display":pretty(val) + unit + (" ("+suffix+")" if suffix else ""),"betterDir":better_dir}
    m = DOT_RE.fullmatch(text)
    if m:
        name = EN_DAMAGE[m.group(2).capitalize()]
        val = number(m.group(1))
        return {"key":"dot."+m.group(2).lower(),"group":"damage","label":name+" 지속 피해/초","value":val,"display":pretty(val),"betterDir":1}
    m = RANGE_RE.fullmatch(text)
    if m:
        a,b = number(m.group(1)),number(m.group(2))
        dtype = m.group(3).lower()
        suffix = normalize_text(m.group(4))
        # Conditional damage (per armour, per charge, from corpses) should NOT be
        # compared to unconditional hit damage; keep it with its own distinct key.
        key = "hit."+dtype+(".conditional."+normalize_name(suffix) if suffix else "")
        return {"key":key,"group":"damage","label":EN_DAMAGE[m.group(3).capitalize()]+(" 조건부" if suffix else " 명중 피해"),"value":(a+b)/2,"display":pretty(a)+"~"+pretty(b),"betterDir":1}
    return None


def analyze_pair(before_raw, after_raw):
    before, after = analyze_line(before_raw), analyze_line(after_raw)
    if not before or not after or before["key"] != after["key"]:
        return {"type":"modified","key":"text","group":"other","label":"효과 변경",
                "before":None,"after":None,"beforeText":normalize_text(before_raw),
                "afterText":normalize_text(after_raw),"deltaPct":None,"impactPct":None,"impact":"neutral","verified":False}
    a,b = before["value"], after["value"]
    raw_delta = (b/a-1)*100 if a != 0 else None
    better_dir=before["betterDir"]
    impact_delta = raw_delta * better_dir if raw_delta is not None else None
    if before["key"] in ("castTime", "cooldown", "attackTime", "triggerInterval") and a>0 and b>0:
        # Rate improvement, not just decrease in interval.
        impact_delta = (a/b-1)*100
    elif before["key"] == "lessDamage" and a<100 and b<100:
        # 40% less -> 50% less = 0.60 -> 0.50 = -16.7% effective damage.
        impact_delta = ((100-b)/(100-a)-1)*100
    impact = "neutral"
    if better_dir and impact_delta is not None:
        if impact_delta > 0.000001: impact="buff"
        if impact_delta < -0.000001: impact="nerf"
    return {"type":"modified","key":before["key"],"group":before["group"],"label":before["label"],
            "before":a,"after":b,"beforeText":before["display"],"afterText":after["display"],
            "deltaPct":round(raw_delta,3) if raw_delta is not None else None,
            "impactPct":round(impact_delta,3) if impact_delta is not None else None,
            "impact":impact,"verified":True}


def analyze_added_removed(text,change_type):
    normalized = analyze_line(text)
    return {"type":change_type,"key":normalized["key"] if normalized else "text",
            "group":normalized["group"] if normalized else "other",
            "label":normalized["label"] if normalized else ("효과 추가" if change_type == "added" else "효과 제거"),
            "before":None,"after":None,"beforeText":normalize_text(text) if change_type=="removed" else "",
            "afterText":normalize_text(text) if change_type=="added" else "",
            "deltaPct":None,"impactPct":None,"impact":"neutral","verified":bool(normalized)}


def parse_source_html(html):
    """Return structured gem sections from the headings and changed text.

    Some news posts use h4/h6/li while others build cards from nested divs.
    We gather text tokens between h4 headings and parse the visible New:/Old:
    pairs. This does not require a specific CSS class name.
    """
    soup = BeautifulSoup(html, "html.parser")
    headings = soup.find_all(["h3","h4"])
    marker = next((h for h in headings if normalize_text(h.get_text(" ",strip=True)).lower() in ("new gems","updated gems")), None)
    if marker is None:
        raise ValueError("Could not locate a 'New Gems' or 'Updated Gems' heading. Check downloaded HTML.")
    sections=[]
    mode=None
    for h in headings:
        title = normalize_text(h.get_text(" ",strip=True))
        if title.lower()=="new gems": mode="new"; continue
        if title.lower()=="updated gems": mode="updated"; continue
        if h.name!="h4" or mode is None:
            continue
        # Read text fragments between gem headings. Preserve the ordering of
        # Added / Removed / Modified as well as New/Old pairs.
        events=[]
        current_type="modified"
        seen=set()
        for node in h.next_elements:
            if isinstance(node,Tag):
                if node.name in ("h3","h4") and node is not h: break
                if node.name=="h6":
                    txt=normalize_text(node.get_text(" ",strip=True)).lower()
                    if txt in ("added","removed","modified"):
                        current_type=txt
                    continue
                if node.name=="li":
                    txt=normalize_text(node.get_text(" ",strip=True))
                    if txt and (current_type,txt) not in seen:
                        seen.add((current_type,txt));events.append((current_type,txt))
                    continue
            if isinstance(node,NavigableString) and node.parent is not None:
                parent=node.parent
                if any(a.name in ("li","h6","h4") for a in [parent,*parent.parents] if isinstance(a,Tag)):
                    continue
                txt=normalize_text(str(node))
                if (txt.startswith("New:") or txt.startswith("Old:")) and (current_type,txt) not in seen:
                    seen.add((current_type,txt));events.append((current_type,txt))
        # Each list item commonly contains one New:/Old: sentence. Some layouts
        # concatenate multiple comparisons within a single fragment.
        tokens=[]
        for event_type, raw in events:
            # Drop share/buttons from raw text.
            raw=re.sub(r"(?:Show|Hide) Differences", "", raw).strip()
            pieces=re.split(r"(?=(?:\bNew:|\bOld:))",raw)
            if not pieces: continue
            for p in pieces:
                p=normalize_text(p)
                if p: tokens.append((event_type,p))
        changes=[]
        pending_new=None
        for typ,token in tokens:
            if token.startswith("New:"):
                if pending_new:
                    changes.append(analyze_added_removed(pending_new,"added"))
                pending_new=token[4:].strip()
            elif token.startswith("Old:"):
                old=token[4:].strip()
                if pending_new:
                    changes.append(analyze_pair(old,pending_new));pending_new=None
                else:
                    changes.append(analyze_added_removed(old,"removed"))
            elif typ=="added":
                changes.append(analyze_added_removed(token,"added"))
            elif typ=="removed":
                changes.append(analyze_added_removed(token,"removed"))
        if pending_new:
            changes.append(analyze_added_removed(pending_new,"added"))
        # Duplicate removal - sometimes website markup nests a 'New' string twice.
        unique=[];seen_changes=set()
        for c in changes:
            sig=(c["type"],c.get("key"),c.get("beforeText"),c.get("afterText"))
            if sig not in seen_changes: unique.append(c);seen_changes.add(sig)
        if unique or mode=="new":
            sections.append({"nameEn":title,"gemState":"new" if mode=="new" else "existing","changes":unique})
    return sections


def make_lookup(manifest, aliases):
    look={}
    for g in manifest.get("gems",[]):
        eid=g.get("effectId","")
        candidates=[eid]
        if eid.startswith("Support"):
            candidates.append(eid[7:]+"Support")
        if eid.startswith("Vaal"):
            candidates.append("Vaal"+eid[4:])
        for cand in candidates:
            norm=normalize_name(cand)
            # Do not invent mappings for X/Y variants.
            if "altx" not in norm and "alty" not in norm:
                look[norm]=g
        look[normalize_name(eid)]=g
    for eng,eid in aliases.items():
        item=next((g for g in manifest.get("gems",[]) if g.get("effectId")==eid),None)
        if item:look[normalize_name(eng)]=item
    return look


def classify_verdict(changes):
    observed={c.get("impact") for c in changes}
    if "buff" in observed and "nerf" in observed: return "mixed"
    # unclassified changes should not be silently forced into an unambiguous verdict
    if "neutral" in observed and ("buff" in observed or "nerf" in observed):return "mixed"
    if "buff" in observed:return "buff"
    if "nerf" in observed:return "nerf"
    return "adjusted"


def build_payload(sections, *, patch, previous, url, manifest, aliases):
    lookup=make_lookup(manifest, aliases)
    gems=[];unmatched=[]
    for section in sections:
        source_name=section["nameEn"]
        g=lookup.get(normalize_name(source_name))
        if g is None:
            unmatched.append(source_name)
        kind=(g or {}).get("kind") or ("support" if " Support" in source_name else "active")
        variant=(g or {}).get("variant") or ("transfigured" if " of " in source_name and not source_name.lower().startswith("vaal ") else "standard")
        eid=(g or {}).get("effectId")
        changes=section["changes"]
        gems.append({
            "id":eid or "unmatched:"+normalize_name(source_name),
            "nameKo":(g or {}).get("name") or source_name,
            "nameEn":source_name,"kind":kind,"variant":variant,
            "color":(g or {}).get("color") or ("r" if kind=="support" else "w"),
            "gemState":section["gemState"],
            "verdict":"new" if section["gemState"]=="new" else classify_verdict(changes),
            "icon":None,"changes":changes,
            "matched":g is not None
        })
    return {
        "schemaVersion":1,"patch":patch,"previousPatch":previous,
        "basis":"Lv20 · Quality 20% (as published by GGG)",
        "source":{"url":url,"mode":"parsed_official_html","status":"requires_review"},
        "gems":gems,
    },unmatched


def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    inp=p.add_mutually_exclusive_group(required=True)
    inp.add_argument("--html",type=Path,help="saved official HTML page")
    inp.add_argument("--url",help="official forum page URL (requires internet)")
    p.add_argument("--patch",required=True)
    p.add_argument("--previous",required=True)
    p.add_argument("--manifest",type=Path,default=Path("data/manifest.json"))
    p.add_argument("--aliases",type=Path,default=Path(__file__).parent/"aliases.json")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.url:
        try:import requests
        except ImportError:sys.exit("Missing requests. Run: pip install -r balance/scripts/requirements.txt")
        r=requests.get(args.url,timeout=40,headers={"User-Agent":"Mozilla/5.0 (PoE gem balance research)"})
        r.raise_for_status();html=r.text;url=args.url
    else:
        html=args.html.read_text(encoding="utf-8")
        url="https://www.pathofexile.com/forum/view-thread/3987254" if args.patch=="3.29" else ""
    manifest=json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest.exists() else {"gems":[]}
    aliases=json.loads(args.aliases.read_text(encoding="utf-8")) if args.aliases.exists() else {}
    sections=parse_source_html(html)
    if not sections:
        sys.exit("No gem sections found. The web page may have changed; inspect HTML or try a saved copy.")
    output,unmatched=build_payload(sections,patch=args.patch,previous=args.previous,url=url,manifest=manifest,aliases=aliases)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report={"patch":args.patch,"totalGems":len(sections),"matched":len(sections)-len(unmatched),
            "unmatched":unmatched,"withChanges":sum(bool(g["changes"]) for g in output["gems"]),
            "typedChanges":sum(c["verified"] for g in output["gems"] for c in g["changes"]),
            "needsReview":sum(not c["verified"] for g in output["gems"] for c in g["changes"])}
    reportpath=args.output.parent/(args.patch+".review.json")
    reportpath.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print("Created:",args.output)
    print("Review:",reportpath)
    if report["needsReview"] or unmatched:
        print("WARNING: review unmatched gems and unclassified effects before publishing.",file=sys.stderr)

if __name__=="__main__":main()
