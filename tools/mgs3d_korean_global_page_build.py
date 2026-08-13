#!/usr/bin/env python3
"""Audit the 8401..87FF namespace and build deterministic Korean glyph pages.

This tool is deliberately non-destructive.  It emits reports/pages under an
output directory and never patches code.bin, DAT, HPK, or a live RomFS.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_gcx_font_tool import render_character
from mgs3d_movie_tool import parse_records
from mgs3d_codec_tool import parse_codec
from PIL import ImageFont

BASE = 0x8400
CAPACITY = 1020
FONT = Path(r"C:\Windows\Fonts\malgun.ttf")
MOVIE = ROOT / "experiments/shared_glyph_optimized_build_2026-08-12/movie_live_base.dat"
DEMO = ROOT / "experiments/scene_fixed_natural_2026-08-12/demo_live_safe_base.dat"
CODEC = ROOT / "experiments/full_korean_apply_2026-08-12/codec_official_plus_3ds.dat"
ALLOC = ROOT / "experiments/shared_glyph_optimized_build_2026-08-12/sna01-allocation-report.json"
MOVIE_CSV = ROOT / "experiments/shared_glyph_optimized_build_2026-08-12/movie_live_rebased.csv"
DEMO_CSV = ROOT / "experiments/scene_fixed_natural_2026-08-12/demo_live_natural_rebased.csv"
CODEC_JSON = ROOT / "experiments/full_korean_apply_2026-08-12/codec_translation_official_plus_3ds.json"
REVIEW = ROOT / "experiments/story_media_order/html/mgs3d_review_v10.json"
CANONICAL_MOVIE_CSV = ROOT / "translation/10_master/bundle_natural_full/movie_natural_full.csv"
CANONICAL_DEMO_CSV = ROOT / "translation/10_master/bundle_natural_full/demo_natural_full.csv"
CANONICAL_CODEC_JSON = ROOT / "translation/10_master/bundle_natural_full/codec_natural_full.json"
CANONICAL_REVIEW = ROOT / "translation/10_master/bundle_natural_full/mgs3d_review_v10_natural_full.json"
DEFAULT_OUT = ROOT / "analysis/global_korean_page_build_2026-08-12"
DEFAULT_ROMFS = Path(r"C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs")

def token(index: int) -> int:
    if not 0 <= index < CAPACITY: raise ValueError("index outside 0..1019")
    group, offset = divmod(index, 255)
    return BASE + group * 0x100 + offset + 1

def iter_tokens(raw: bytes):
    i = 0
    while i < len(raw):
        b = raw[i]
        if not b: break
        if b >= 0x80 and i + 1 < len(raw):
            yield (b << 8) | raw[i+1]; i += 2
        else: i += 1

def structured_usage() -> Counter[int]:
    c: Counter[int] = Counter()
    for path in (MOVIE, DEMO):
        _, records, _ = parse_records(path.read_bytes())
        for r in records:
            for s in r.subtitles: c.update(iter_tokens(s.raw))
    for r in parse_codec(CODEC.read_bytes()):
        for x in r.resources(): c.update(iter_tokens(x.data))
    return c

def hangul_from_obj(obj) -> set[str]:
    found: set[str] = set()
    def walk(x):
        if isinstance(x, str): found.update(ch for ch in x if '\uac00' <= ch <= '\ud7a3')
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(obj); return found

def translation_chars(canonical_master: bool = False) -> tuple[list[str], set[str], dict[str,int]]:
    all_chars: set[str] = set(); counts: Counter[str] = Counter()
    csv_sources = ((CANONICAL_MOVIE_CSV, CANONICAL_DEMO_CSV) if canonical_master
                   else (MOVIE_CSV, DEMO_CSV))
    json_sources = ((CANONICAL_CODEC_JSON, CANONICAL_REVIEW) if canonical_master
                    else (CODEC_JSON, REVIEW))
    for p in csv_sources:
        text = p.read_text(encoding="utf-8-sig")
        counts.update(ch for ch in text if '\uac00' <= ch <= '\ud7a3')
        all_chars.update(counts)
    for p in json_sources:
        obj = json.loads(p.read_text(encoding="utf-8-sig"))
        chars = hangul_from_obj(obj); all_chars.update(chars)
        # Frequency is only a stable ordering aid; JSON string representation is sufficient.
        counts.update(ch for ch in json.dumps(obj, ensure_ascii=False) if '\uac00' <= ch <= '\ud7a3')
    fixed = set(json.loads(ALLOC.read_text(encoding="utf-8"))["characters"])
    new = sorted(all_chars - fixed, key=lambda ch: (-counts[ch], ord(ch)))
    return new, fixed, dict(counts)

def audit(out: Path) -> dict:
    usage = structured_usage(); rows=[]
    for i in range(CAPACITY):
        t=token(i); aliases=[t,t|0x2000,t|0x4000,t|0x6000]
        hits={f"0x{x:04X}":usage[x] for x in aliases if usage[x]}
        rows.append({"index":i,"token":f"0x{t:04X}","aliases":" ".join(f"0x{x:04X}" for x in aliases),"structured_hits":sum(hits.values()),"hit_detail":json.dumps(hits)})
    out.mkdir(parents=True,exist_ok=True)
    with (out/"namespace_audit.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    report={"range":"0x8401..0x87FF excluding xx00","slots":CAPACITY,"movie_demo_codec_alias_collisions":sum(bool(r["structured_hits"]) for r in rows),"ui_runtime_status":"pending exhaustive menu/system-message traversal","safe_to_finalize":False}
    (out/"namespace_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report

def scan_assets(out: Path, romfs: Path) -> dict:
    """Conservative byte scan: candidates are evidence to inspect, not usage proof."""
    rows=[]; total=0
    pattern=re.compile(b"(?=([\\x84-\\x87][\\x01-\\xff]))")
    files=sorted(x for x in romfs.rglob("*") if x.is_file())
    for p in files:
        data=p.read_bytes(); hits=Counter(int.from_bytes(m.group(1),"big") for m in pattern.finditer(data))
        if hits:
            total+=sum(hits.values()); rows.append({"path":str(p.relative_to(romfs)),"size":len(data),"candidate_pairs":sum(hits.values()),"distinct":len(hits),"first_tokens":" ".join(f"0x{x:04X}" for x in sorted(hits)[:16]),"classification":"raw candidate only; compressed/binary false positives possible"})
    with (out/"whole_romfs_raw_candidates.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=rows[0] if rows else ["path","size","candidate_pairs","distinct","first_tokens","classification"]);w.writeheader();w.writerows(rows)
    result={"files_scanned":len(files),"files_with_raw_candidates":len(rows),"raw_candidate_pairs":total,"interpretation":"not proof of token use; structured parsers and runtime traversal remain authoritative"}
    (out/"whole_romfs_raw_scan.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result

def build(out: Path, limit: int|None, canonical_master: bool = False,
          extend_map: Path | None = None) -> dict:
    chars,fixed,counts=translation_chars(canonical_master)
    if len(chars)>CAPACITY: raise SystemExit(f"capacity exceeded: {len(chars)} > {CAPACITY}")
    if extend_map is not None:
        with extend_map.open(encoding="utf-8-sig", newline="") as stream:
            previous = list(csv.DictReader(stream))
        previous_chars = [row["character"] for row in previous]
        if len(previous_chars) != len(set(previous_chars)):
            raise SystemExit("extend-map contains duplicate characters")
        unknown = set(previous_chars) - set(chars)
        if unknown:
            raise SystemExit(f"extend-map contains {len(unknown)} characters outside current corpus")
        chars = previous_chars + [character for character in chars if character not in set(previous_chars)]
    selected=chars if limit is None else chars[:limit]
    font=ImageFont.truetype(str(FONT),16)
    page=bytearray(CAPACITY*64); rows=[]
    for i,ch in enumerate(selected):
        bitmap=render_character(ch,font)
        if len(bitmap)!=64: raise RuntimeError(f"bad glyph size: {ch}")
        page[i*64:(i+1)*64]=bitmap
        rows.append({"character":ch,"unicode":f"U+{ord(ch):04X}","index":i,"token":f"0x{token(i):04X}","bytes":token(i).to_bytes(2,"big").hex(),"frequency":counts.get(ch,0)})
    out.mkdir(parents=True,exist_ok=True)
    suffix="full" if limit is None else f"stress_{limit}"
    page_path=out/f"korean_page_{suffix}.bin";page_path.write_bytes(page)
    with (out/f"korean_token_map_{suffix}.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    result={"fixed_characters":len(fixed),"new_characters":len(chars),"selected":len(selected),"capacity":CAPACITY,"free_after_full":CAPACITY-len(chars),"page_bytes":len(page),"page_sha256":hashlib.sha256(page).hexdigest(),"font":str(FONT),"font_size":16,"corpus":"canonical-master" if canonical_master else "historical-2026-08-12","map_policy":"append-only" if extend_map else "frequency-ordered","extended_from":str(extend_map) if extend_map else None}
    (out/f"build_{suffix}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--out",type=Path,default=DEFAULT_OUT);ap.add_argument("--audit",action="store_true");ap.add_argument("--scan-assets",action="store_true");ap.add_argument("--romfs",type=Path,default=DEFAULT_ROMFS);ap.add_argument("--stress",type=int,choices=range(32,65));ap.add_argument("--build-full",action="store_true");ap.add_argument("--canonical-master",action="store_true",help="derive glyphs from translation/10_master instead of the frozen historical corpus");ap.add_argument("--extend-map",type=Path,help="preserve an existing token-map order and append only newly required characters");a=ap.parse_args()
    if not (a.audit or a.scan_assets or a.stress or a.build_full): ap.error("choose --audit, --scan-assets, --stress N, or --build-full")
    result={}
    if a.audit: result["audit"]=audit(a.out)
    if a.scan_assets: result["asset_scan"]=scan_assets(a.out,a.romfs)
    if a.stress: result["stress"]=build(a.out,a.stress,a.canonical_master,a.extend_map)
    if a.build_full: result["full"]=build(a.out,None,a.canonical_master,a.extend_map)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
