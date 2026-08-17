#!/usr/bin/env python3
"""Scan the codec corpus for *sense* mistranslations only.

This is not a quality checker. It looks for one specific failure mode: an
English polysemous word, phrasal verb or idiom rendered with a Korean word
carrying the wrong sense for the surrounding context -- the `manage` -> 관리
family. Each rule pairs

    en      the English trigger,
    ko_bad  the Korean wording that only appears if the wrong sense was taken,
    ko_ok   (optional) wording that proves the right sense was taken, which
            suppresses the hit.

Rules are deliberately narrow: a rule that fires on correct translations is
worse than one that misses, because every hit is read by hand afterwards.
Output is candidates, never verdicts.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
csv.field_size_limit(10**9)


def rule(rid, en, ko_bad, ko_ok=None, note=""):
    return {
        "id": rid,
        "en": re.compile(en, re.I),
        "ko_bad": re.compile(ko_bad),
        "ko_ok": re.compile(ko_ok) if ko_ok else None,
        "note": note,
    }


RULES = [
    # --- verbs whose everyday sense collides with a military/technical one ---
    rule("manage", r"\bmanage[ds]?\b|\bmanaging\b", r"관리", None,
         "manage(해내다/성공하다)를 '관리'(administer)로"),
    rule("operation", r"\boperations?\b", r"수술", None,
         "operation(작전)을 '수술'로"),
    rule("intelligence", r"\bintelligence\b", r"지능", None,
         "intelligence(첩보/정보기관)를 '지능'으로"),
    rule("arms", r"\barms\b", r"팔(을|이|은|로|과|에)", r"무기|무장|군비",
         "arms(무기)를 '팔'로"),
    rule("grave", r"\bgrave\b", r"무덤", None,
         "grave(중대한)를 '무덤'으로"),
    rule("party", r"\b(search|scouting|raiding|landing)\s+party\b", r"파티", r"부대|수색대|일행",
         "party(부대/일행)를 '파티'로"),
    rule("company", r"\bcompany\b", r"회사", r"중대|동행|일행",
         "company(중대/동행)를 '회사'로"),
    rule("post", r"\b(guard|sentry|listening|command)\s+post\b|\bpost\b", r"우편|게시(물|글)", None,
         "post(초소)를 '우편/게시물'로"),
    rule("watch", r"\bwatch\b", r"손목시계|시계를", r"감시|망보|경계",
         "watch(감시)를 '시계'로"),
    rule("second", r"\bseconds?\b", r"두 번째|둘째", r"초\b",
         "second(초)를 '두 번째'로"),
    rule("current", r"\bcurrents?\b", r"현재", r"해류|물살|전류",
         "current(해류/전류)를 '현재'로"),
    rule("spot", r"\bspot(ted|s)?\b", r"얼룩|반점", r"발견|들키|포착|자리",
         "spot(발견하다)을 '얼룩/반점'으로"),
    rule("cover", r"\bcover\b", r"덮개|표지", r"엄폐|은폐|가리",
         "cover(엄폐)를 '덮개/표지'로"),
    rule("bug", r"\bbug(s|ged)?\b", r"벌레|곤충", r"도청",
         "bug(도청기)를 '벌레'로"),
    rule("tail", r"\btail(ing|ed)?\b", r"꼬리", r"미행|추적",
         "tail(미행)을 '꼬리'로"),
    rule("lead", r"\blead\b", r"납\b", r"이끌|안내|단서|앞서",
         "lead(이끌다/단서)를 '납'으로"),
    rule("plant", r"\bplant(ing|ed|s)?\b\s+(the\s+)?(c3|charges?|explosives?|bombs?|mines?)",
         r"심(다|어|으|은|을)", r"설치",
         "plant(설치하다)을 '심다'로"),
    rule("come_in_radio", r"\bcome in\b", r"들어(와|오|가)", r"응답|나와라|들리",
         "come in(무전 응답하라)을 '들어와'로"),
    rule("pick_up_signal", r"\bpick(ing|ed)? up\b.*(signal|transmission|frequency|reading)",
         r"줍|집어", r"포착|잡히|수신",
         "pick up(수신하다)을 '줍다'로"),
    rule("put_down", r"\bput (him|them|it) down\b", r"내려놓|내려 놓", None,
         "put down(제압/처치)을 '내려놓다'로"),
    rule("take_on", r"\btake (him|them|it|these|those) on\b", r"입(다|어)|착용|태우", None,
         "take on(상대하다)을 '입다/태우다'로"),
    rule("make_it", r"\bmake it\b", r"만들", r"해내|성공|도착|살아",
         "make it(해내다/도착하다)을 '만들다'로"),
    rule("get_it", r"\bget it\b", r"가져|얻", r"이해|알겠|알았",
         "get it(이해하다)을 '가져오다'로"),
    rule("run", r"\brun(s|ning)?\b", r"운영|경영", r"달리|뛰|가동|작동|흐르",
         "run(달리다/작동)을 '운영'으로"),
    rule("stand", r"\b(can't|cannot|couldn't) stand\b", r"서 있|설 수", None,
         "can't stand(못 견디다)을 '설 수 없다'로"),
    rule("left_remaining", r"\b(is|are|was|were|\bhow much\b|\bhow many\b).{0,20}\bleft\b",
         r"왼쪽", None, "left(남은)를 '왼쪽'으로"),
    rule("mean_adj", r"\bmean\b", r"못된|심술", r"의미|뜻",
         "mean(의미하다)을 '못된'으로"),
    rule("kind_noun", r"\bkind of\b|\bwhat kind\b", r"친절", r"종류|어떤",
         "kind(종류)를 '친절'로"),
    rule("case", r"\bin case\b|\bin any case\b", r"상자|케이스", None,
         "in case(~에 대비해)를 '상자'로"),
    rule("point", r"\bthe point\b|\bmore to the point\b|\bno point\b", r"점을|점이|점\.", r"요점|의미|소용",
         "point(요점/의미)를 '점'으로"),
    rule("match", r"\bmatch\b", r"성냥", r"상대|시합|맞|어울",
         "match(상대/맞다)를 '성냥'으로"),
    rule("scale", r"\bscales?\b", r"저울", r"비늘|규모",
         "scale(비늘/규모)을 '저울'로"),
    rule("trunk", r"\btrunk\b", r"트렁크", r"줄기|몸통|코\b",
         "trunk(줄기/코)를 '트렁크'로"),
    rule("band", r"\bband\b", r"밴드", r"무리|띠|일당",
         "band(무리/띠)를 '밴드'로"),
    rule("green", r"\bgreen\b", r"초록|녹색", r"미숙|풋내|신참",
         "green(미숙한)을 '초록'으로"),
    rule("sharp", r"\bsharp\b", r"날카로운", r"예민|빠른|정확|또렷",
         "sharp(민첩한/정확한)을 '날카로운'으로"),
    rule("fire_noun", r"\b(under|open|hold|cease|covering|suppressive)\s+fire\b|\brifle fire\b",
         r"화재|불이 났|불길", r"사격|총격|발포",
         "fire(사격)를 '화재'로"),
    rule("shot_photo", r"\bshots?\b|\bshooting\b", r"촬영|사진", r"사격|쏘|탄",
         "shot(사격)을 '촬영/사진'으로"),
    rule("magazine", r"\bmagazine\b", r"잡지", r"탄창",
         "magazine(탄창)을 '잡지'로"),
    rule("mine_noun", r"\bmines?\b", r"광산|채굴", r"지뢰|기뢰",
         "mine(지뢰)을 '광산'으로"),
    rule("cell", r"\bcell\b", r"세포", r"감방|독방|조직",
         "cell(감방/조직)을 '세포'로"),
    rule("charges", r"\bcharges?\b", r"요금|충전료", r"폭약|장약|돌격|기소",
         "charge(폭약)를 '요금'으로"),
    rule("take_out", r"\btake (him|her|them|it|out) .{0,12}out\b|\btake out\b", r"꺼내|데리고 나가|데리고",
         r"처치|제거|쓰러|없애|해치우|날려", "take out(처치하다)을 '꺼내다/데리고 가다'로"),
    rule("work_verb", r"\b(should|will|might|does|doesn't|won't) work\b|\bworks (well|fine)\b",
         r"작동", r"통하|효과|먹히",
         "work(효과가 있다)을 '작동'으로"),
    rule("draw", r"\bquick-?draw\b|\bdraw (your|his|the) (gun|weapon)\b", r"추첨|그리", None,
         "draw(뽑다)를 '추첨/그리다'로"),
    rule("rank", r"\brank\b", r"순위", r"계급|서열",
         "rank(계급)를 '순위'로"),
    rule("major_rank", r"\b(a|the) major\b|\bMajor\b", r"전공", None,
         "major(소령)를 '전공'으로"),
    rule("armor", r"\barmor\b", r"갑옷", r"장갑",
         "armor(장갑)를 '갑옷'으로"),
    rule("round_ammo", r"\brounds?\b", r"라운드", r"탄|발\b|회전",
         "round(탄)을 '라운드'로"),
    rule("bridge", r"\bbridge\b", r"함교", r"다리|철교|교량",
         "bridge(다리/철교)를 '함교'로"),
    rule("hangar", r"\bhangar\b", r"헛간", r"격납고|HANGAR",
         "hangar(격납고)를 '헛간'으로"),
    rule("wing_bldg", r"\b(east|west|main|north|south)\s+wing\b", r"날개|주익|윙", r"관\b|동\b|본관",
         "wing(건물 부속동)을 '날개/윙'으로"),
    rule("beats_me", r"\bbeats me\b", r"이겼|때린|이기", None,
         "Beats me(모르겠다)를 문자 그대로"),
    rule("wet_works", r"\bwet work", r"수중|물속", None,
         "wet works(암살 임무)를 '수중 작업'으로"),
    rule("drop_fall", r"\b(a hell of a|the) drop\b|\bdrop zone\b", r"하락|떨어뜨리기", r"낙하|추락|투하",
         "drop(낙하/추락)을 '하락'으로"),
    rule("sound_like", r"\bsounds? like\b|\bsounds? (good|fun|about right)\b", r"소리", r"같|듯|들리",
         "sound like(~인 것 같다)를 '소리'로"),
    rule("figure", r"\bfigures\.|\bI figured\b|\bgo figure\b", r"수치|숫자|그림", None,
         "Figures(그럴 줄 알았다)를 '수치/숫자'로"),
    rule("save_game", r"\bsave\b.{0,20}\b(game|now|here|data)\b|\bwant to save\b", r"구하|구조", None,
         "save(저장)를 '구하다'로"),
    rule("pass_as", r"\bpass (as|for)\b", r"통과", r"행세|속이|가장",
         "pass as(~로 행세하다)를 '통과'로"),
    rule("address", r"\baddress (the|this|that|it)\b", r"주소", None,
         "address(대처하다)를 '주소'로"),
    rule("handle", r"\bhandle (it|him|her|them|this|that)\b", r"손잡이", r"다루|처리|상대",
         "handle(다루다)을 '손잡이'로"),
    rule("piece_gun", r"\bpiece\b", r"조각", r"총|권총|작품",
         "piece(총)를 '조각'으로"),
    rule("brass", r"\bbrass\b", r"놋쇠|황동", r"수뇌|고위|장교|탄피",
         "brass(수뇌부/탄피)를 '놋쇠'로"),
    rule("clear_verb", r"\bclear (the|a|this|that)\b|\ball clear\b", r"맑|투명", r"제거|정리|이상 없|치우",
         "clear(제거하다)를 '맑다'로"),
    rule("field", r"\bin the field\b|\bfield (work|agent|test)\b", r"들판|밭", r"현장|실전|야전",
         "field(현장/야전)를 '들판'으로"),
    rule("front_mil", r"\b(eastern|western|northern|southern|the) front\b", r"앞쪽|정면", r"전선|전방",
         "front(전선)를 '앞쪽'으로"),
    rule("change_money", r"\bchange\b", r"잔돈|거스름", None,
         "change(변화)를 '잔돈'으로"),
    rule("boot", r"\bboot\b", r"부츠|장화", r"시동|부팅|걷어차",
         "boot(시동/걷어차기)를 '부츠'로"),
    rule("still_motion", r"\bstand still\b|\bhold still\b|\bstay still\b", r"여전히", None,
         "still(가만히)을 '여전히'로"),
    rule("light_weight", r"\blight(er|weight)?\b", r"빛|조명", r"가벼|가볍|불\b|점등",
         "light(가벼운)을 '빛'으로"),
    rule("order_cmd", r"\border(s|ed)?\b", r"주문", r"명령|지시|순서|질서",
         "order(명령)를 '주문'으로"),
    rule("cut_wound", r"\bcut\b", r"자르|절단", r"상처|베인|베",
         "cut(상처)를 '자르다'로"),
    rule("trip_trigger", r"\btrip(ped|s|wire)?\b", r"여행", r"걸리|작동|넘어",
         "trip(작동시키다/걸려 넘어지다)을 '여행'으로"),
    rule("blow_destroy", r"\bblow (it|them|him|up|the)\b", r"불(다|어|기)", r"날려|폭파|터뜨",
         "blow up(폭파)을 '불다'로"),
    rule("check_stop", r"\bkeep (him|them|it) in check\b|\bhold (him|them|it) in check\b",
         r"확인|점검", None, "in check(억제하다)를 '확인'으로"),
    rule("spirit_drink", r"\bspirits?\b", r"영혼|정령", r"기분|사기|술",
         "spirits(기분/술)를 '영혼'으로"),
    rule("cold_war", r"\bcold war\b", r"추운|차가운", r"냉전",
         "Cold War(냉전)를 '추운 전쟁'으로"),
    rule("agent", r"\bagents?\b", r"대리인|중개", r"요원|첩보|작용제|제\b",
         "agent(요원)를 '대리인'으로"),
]


def load_rows(review_csv: Path, recovered_json: Path | None):
    with review_csv.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if recovered_json and recovered_json.exists():
        rec = {
            (r["gcx"], r["resource"]): r["english_plain"]
            for r in json.loads(recovered_json.read_text(encoding="utf-8"))
        }
        for r in rows:
            key = (r["gcx"], r["resource"])
            if key in rec:
                r["english"] = rec[key]
                r["english_source"] = "recovered"
    return rows


DONOR = re.compile(r"<1f[0-9a-f]{2}>|\b(le|la|les|des|une|un|est|vous|tu|que|qui|con|los|las|para|como|pero|est\xe1|d\xe9j\xe0)\b", re.I)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--review", type=Path,
                    default=ROOT / "translation/10_master/review/codec-full-contextual-review.csv")
    ap.add_argument("--recovered", type=Path,
                    default=ROOT / "translation/10_master/review/full-qa-final/_recovered166.json")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--skip-donor", action="store_true", default=True)
    args = ap.parse_args(argv)

    rows = load_rows(args.review, args.recovered)
    hits = []
    for r in rows:
        en, ko = r["english"], r["korean"]
        if args.skip_donor and DONOR.search(en):
            continue
        for rl in RULES:
            if not rl["en"].search(en):
                continue
            if not rl["ko_bad"].search(ko):
                continue
            if rl["ko_ok"] and rl["ko_ok"].search(ko):
                continue
            hits.append({**r, "rule": rl["id"], "rule_note": rl["note"]})
    if args.out:
        fields = ["rule", "rule_note", "gcx", "resource", "english", "korean",
                  "verdict", "issue_type", "reason"]
        with args.out.open("w", encoding="utf-8", newline="") as handle:
            w = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(hits)
    print(f"scanned {len(rows)} rows, {len(hits)} candidate hits", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
