#!/usr/bin/env python3
"""Normalize established MGS proper-name spellings while preserving particles."""

from __future__ import annotations
import argparse, csv
from pathlib import Path

REPLACEMENTS = [
    ("니콜라이 스테파노비치 소코로프", "Nikolai Stepanovich Sokolov"),
    ("니콜라이 스테파노비치 소콜로프", "Nikolai Stepanovich Sokolov"),
    ("예브게니 보리소비치 볼긴", "Yevgeny Borisovitch Volgin"),
    ("이완 라이데노비치 라이코프", "Ivan Raidenovitch Raikov"),
    ("알렉산드르 레오노비치 그라닌", "Aleksandr Leonovitch Granin"),
    ("파라 메딕", "Para-Medic"), ("파라메딕", "Para-Medic"),
    ("더 보스", "The Boss"), ("소코로프", "Sokolov"), ("소콜로프", "Sokolov"),
    ("스네이크", "Snake"), ("오셀롯", "Ocelot"), ("볼긴", "Volgin"),
    ("라이코프", "Raikov"), ("그라닌", "Granin"), ("시긴트", "Sigint"),
    ("샤고호드", "Shagohod"), ("흐루쇼프", "Khrushchev"),
    ("브레즈네프", "Brezhnev"), ("코시긴", "Kosygin"),
    ("아담스카", "Adamska"), ("조니", "Johnny"),
    ("에바", "EVA"),
]

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("source",type=Path); p.add_argument("output",type=Path); p.add_argument("audit",type=Path); a=p.parse_args()
    with a.source.open(encoding="utf-8-sig",newline="") as f: rd=csv.DictReader(f); rows=list(rd); fields=list(rd.fieldnames or [])
    audit=[]
    for row in rows:
        before=row.get("korean",""); after=before
        for old,new in REPLACEMENTS: after=after.replace(old,new)
        if after!=before:
            audit.append({"media":row["media"],"record":row["record"],"entry":row["entry"],"english":row["preview"],"before":before,"after":after})
            row["korean"]=after
    for path,data,fs in ((a.output,rows,fields),(a.audit,audit,["media","record","entry","english","before","after"])):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("w",encoding="utf-8-sig",newline="") as f: wr=csv.DictWriter(f,fieldnames=fs); wr.writeheader(); wr.writerows(data)
    print(f"normalized_rows={len(audit)}")
    return 0
if __name__=="__main__": raise SystemExit(main())
