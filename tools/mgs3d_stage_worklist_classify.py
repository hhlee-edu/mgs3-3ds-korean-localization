# -*- coding: utf-8 -*-
"""Classify the stage/scenerio.gcx English worklist and pull the dialogue set.

READ-ONLY. Reads the 2026-08-19 stage scan output plus the Korean reference catalog
and the script reference transcript; writes only into
docs/evidence/2026-08-19-stage-recovery/.

Classification is deliberately conservative. Every rule below is a lexical or
structural signal that can be pointed at; anything a rule cannot decide is left
as OTHER rather than guessed. Category counts in the report are therefore a
floor, not an estimate.
"""
import csv
import io
import json
import os
import re
import sys
import collections
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location(
    'ctx', os.path.join(HERE, 'mgs3d_media_misplaced_context.py'))
ctx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctx)

SCAN = os.path.join(ROOT, 'docs/evidence/2026-08-19-stage-text-scan')
WORKLIST = os.path.join(SCAN, 'stage-text-english-worklist.csv')
LOCATIONS = os.path.join(SCAN, 'stage-text-locations.csv')
OUT = os.path.join(ROOT, 'docs/evidence/2026-08-19-stage-recovery')

# Enemy barks, established structurally: they occupy the contiguous resource
# band that follows the food/animal description block (res ~1296-1340) and are
# the only English strings in that band. See the report for the s004a dump.
BARKS = {'Speak!', 'Answer me!', "Who's that!", 'I see him!!', "Who's there!",
         'Who the...!!', 'Hyuuh!', 'Hyeeei!', 'Hyahya!', 'Hyaaaah!', 'Gwoah!',
         'Huuuuhya!'}
BARK_BAND = (1290, 1345)

CTRL = re.compile(r'#\s*\{')
TITLE = re.compile(r'You obtained the title|^You got ')
INJURY_WORDS = re.compile(
    r'\b(Wound|Fracture|Broken|Burn|Bleeding|Gastritis|Poison|Sprain|Dislocat|'
    r'Sustained|Leech|Stab|Bruis|Cut)\b', re.I)
MED_WORDS = re.compile(
    r'\b(Bandage|Disinfectant|Ointment|Splint|Styptic|Suture|Serum|Antidote|'
    r'Medicine|Pentazemin|Cure|Cures|Treat|extracted|Syringe|Pill)\b', re.I)
FAUNA_WORDS = re.compile(
    r'\b(captured alive|Not eaten yet|Tried it|species|snake|frog|bird|fish|'
    r'scorpion|spider|rat|bat|crocodile|mushroom|fungus|hornet|wasp|rabbit|'
    r'squirrel|parrot|vulture|tortoise|salamander|centipede|moth|butterfly)\b',
    re.I)
FOOD_WORDS = re.compile(
    r'\b(Ration|Calorie Mate|Instant Noodles|Compressed Ration|tasty|taste|'
    r'delicious|nutrition|food|eaten|stamina)\b', re.I)
WEAPON_WORDS = re.compile(
    r'\b(rifle|pistol|revolver|shotgun|grenade|ammunition|ammo|calibre|caliber'
    r'|magazine|silencer|suppressor|launcher|knife|weapon|camo|uniform|'
    r'face paint|mine|explosive|C3|claymore|scope|goggles)\b', re.I)
RESULTS_WORDS = re.compile(
    r'\b(TOTAL|TIMES|ALERTS|CONTINUES|SAVES|KILLS|DAMAGE|RESULT|RANK|CLEAR|'
    r'PLAY TIME|SPECIAL)\b')
AREA_HINT = re.compile(
    r'\b(North|South|East|West|Base|Camp|Tunnel|Bridge|Ruins|Warehouse|'
    r'Mountaintop|Swamp|Forest|Cave|Factory|Lab|Hangar|Runway|Dock|Pass|'
    r'Grad|Rassvet|Dremuchij|Bolshaya|Chyornaya|Ponizovje|Graniny|Krasnogorje|'
    r'Tikhogornyj|Zaozyorje|Rokovoj|Lazorevo|Svyatogornyj|Sokrovenno)\b')
DIALOGUE = re.compile(r'[!?]\s*$')
UI_PROMPT = re.compile(
    r"\b(Cancel|Continue|Return to the main menu|Settings|memory card|SD Card|"
    r"saved data|Save|Load|Quit|Exit|Overwrite|Delete|I like MGS|"
    r"favorite METAL GEAR|I'm playing MGS)\b", re.I)
# the in-game questionnaire answers ("I like MGS1!") - the digit defeats \b
UI_SURVEY = re.compile(r"\bI like MGS\d|\bI'm playing MGS", re.I)


def classify(text, kind, resources, stages):
    t = text.strip()
    if not t:
        return 'OTHER', 'empty'
    if text in BARKS and any(BARK_BAND[0] <= r <= BARK_BAND[1] for r in resources):
        return 'ENEMY_BARK', 'known bark inside the res%d-%d bark band' % BARK_BAND
    if CTRL.search(t):
        return 'TUTORIAL_CONTROL', 'contains a #{nn}# button token'
    if TITLE.search(t):
        return 'TITLE_AWARD', 'award / unlock message'
    if kind == 'label' and t.isupper() and RESULTS_WORDS.search(t):
        return 'RESULTS', 'uppercase results-screen label'
    if INJURY_WORDS.search(t) and len(t) <= 40:
        return 'INJURY', 'injury/status name'
    if MED_WORDS.search(t):
        return 'MEDICINE', 'medical item vocabulary'
    if FAUNA_WORDS.search(t):
        return 'FLORA_FAUNA', 'creature/plant encyclopedia vocabulary'
    if FOOD_WORDS.search(t):
        return 'FOOD', 'food vocabulary'
    if WEAPON_WORDS.search(t):
        return 'ITEM_WEAPON', 'weapon/equipment vocabulary'
    if AREA_HINT.search(t) and len(t) <= 48 and t[:1].isupper():
        return 'AREA_NAME', 'area-name vocabulary'
    if UI_PROMPT.search(t) or UI_SURVEY.search(t):
        # System dialogs and the in-game questionnaire. They end in '?' like
        # dialogue does, but none of the allowed categories covers system UI,
        # so they stay OTHER rather than being mislabelled as NPC speech.
        return 'OTHER', 'system UI prompt / questionnaire, not character speech'
    if DIALOGUE.search(t) and len(t) <= 60:
        return 'NPC_DIALOGUE', 'short line ending in ! or ? outside the bark band'
    return 'OTHER', 'no rule matched - left unclassified on purpose'


def main():
    os.makedirs(OUT, exist_ok=True)
    work = ctx.read_csv(WORKLIST)

    # per-unique-text: which stages and resources it occurs at (english branch)
    res_by_text = collections.defaultdict(set)
    stg_by_text = collections.defaultdict(set)
    eng_locations = 0
    with io.open(LOCATIONS, encoding='utf-8-sig', newline='') as fh:
        for r in csv.DictReader(fh):
            if r['language'] != 'english':
                continue
            eng_locations += 1
            res_by_text[r['text']].add(int(r['resource']))
            stg_by_text[r['text']].add(r['stage'])

    rows = []
    for w in work:
        t = w['text']
        res = res_by_text.get(t, set())
        cat, why = classify(t, w['kind'], res, stg_by_text.get(t, set()))
        rows.append({
            'stage': w['first_stage'],
            'record': w['first_record'],
            'resource': w['first_resource'],
            'english': t,
            'category': cat,
            'category_basis': why,
            'occurrences': w['locations'],
            'en_location_count': w['locations'],
            'donor_locations': '',
            'stages': w['stages'],
            'kind': w['kind'],
            'branch_span': w['branch_span'],
            'scan_basis': w['basis'],
            'bytes': w['bytes'],
            'current_status': 'UNTRANSLATED',
            'ps2_candidate': '',
            'script_ref_candidate': '',
            'source_authority': '',
            'match_confidence': 'UNRESOLVED',
            'speaker': '',
            'speaker_confidence': 'UNKNOWN',
            'notes': '',
        })

    cols = list(rows[0].keys())
    rows.sort(key=lambda r: (r['category'], -int(r['occurrences'])))
    with io.open(os.path.join(OUT, 'stage-worklist-classified.csv'), 'w',
                 encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
        w.writeheader()
        w.writerows(rows)

    dlg = [r for r in rows if r['category'] in ('ENEMY_BARK', 'NPC_DIALOGUE')]
    with io.open(os.path.join(OUT, 'stage-enemy-npc-dialogue.csv'), 'w',
                 encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
        w.writeheader()
        w.writerows(dlg)

    tally = collections.Counter(r['category'] for r in rows)
    loc = collections.Counter()
    for r in rows:
        loc[r['category']] += int(r['occurrences'])
    summary = {
        'unique_english': len(rows),
        'english_locations_total': eng_locations,
        'by_category_unique': dict(tally),
        'by_category_locations': dict(loc),
    }
    with io.open(os.path.join(OUT, 'stage-classification-summary.json'), 'w',
                 encoding='utf-8') as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    print('unique english rows %d' % len(rows))
    print('english locations   %d' % eng_locations)
    print()
    print('%-18s %6s %9s' % ('category', 'unique', 'locations'))
    for c, n in tally.most_common():
        print('%-18s %6d %9d' % (c, n, loc[c]))
    print()
    print('dialogue rows written: %d' % len(dlg))


if __name__ == '__main__':
    main()
