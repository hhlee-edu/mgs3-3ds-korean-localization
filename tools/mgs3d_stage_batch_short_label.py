# -*- coding: utf-8 -*-
"""SHORT_LABEL batch.

Classification is by ADJACENCY in the raw GCX, not by the scanner's `language`
column and not by how English the label looks. A stage record stores the same
label list once per language, so a bare abbreviation inherits the language of
the resources physically next to it:

    ending:1099 'SRPT A'   neighbours R.NI FREL / SRPT B / GRENO A  -> French
                           (serpent / nid de frelons / grenouille)
    ending:1513 'SPT C'    neighbours SPT B / SPT D / RNA A         -> Spanish
                           (serpiente / rana)
    ending:713  'CRAB'     neighbours FISH A / FISH B / TCHNKO      -> English
    hx001a:6470 'Hypoxia'  neighbours Quemadura el<1f>ctrica /
                           Golpe recibido                            -> Spanish

DONOR below is the set whose neighbours are French or Spanish; every one of
them was read out of the clean tree before being listed here.

KEEP_ENGLISH covers three groups: the award/rank names, which TITLE_AWARD
already keeps in English ('칭호 "FOX" 획득.'); the jukebox track names, same
policy as MUSIC_TITLE; and a handful of labels whose slot leaves 3-7 bytes,
where no Korean form exists that short (PATRIOT, MIC, TCHNKO, Bike, the
language list, EASY/HARD -- the difficulty names are already kept in English by
the MEDICINE rank conditions).
"""
import sys
import os
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location(
    'pb', os.path.join(ROOT, 'tools/mgs3d_stage_plain_batch.py'))
pb = importlib.util.module_from_spec(_s)
sys.modules['pb'] = pb
_s.loader.exec_module(pb)

DONOR = [
    '(!!!)APPROVED BY', 'ARAIGNEE', 'ARCHIVOS INFORMES\n', 'Abalone\n',
    'Activado\n', 'Avertissement\n', 'BONUS\n', 'Baguette\n', 'Bronchite\n',
    'CANG', 'CAPT. AP', 'Caries\n', 'Cointreau\n', 'Cortada\n', 'DEMO\n',
    'DESINFECT', 'DESINFECT.', 'DIFFICULTE', 'DIFmCIL', 'DUEL\n', 'DUELO\n',
    'Desactivado\n', 'ESMOQUIN', 'ESPECES', 'Emetteur :\n', 'Entorse\n',
    'Esguince\n', 'Espresso\n', 'FICHIERS BRIEFING\n', 'FbCIL', 'Foccacia\n',
    'Fractura :\n', 'GRENO A', 'GRENO B', 'GRENO C', 'Gastrite\n', 'Gelures\n',
    'Granin', 'Grappa\n', 'Hipotermia\n', 'Hypoxia\n', 'Hypoxie\n', 'INFINIDAD',
    'INSECTCD', 'LLAVE A', 'LLAVE B', 'LUN. THER.', 'LUN. VN', 'Liquid\n',
    'M.DIGEST.', 'MAS. SINGE', 'MED. D.', 'MED. R.', 'MEDICAMENTOS USADOS',
    'MEDICAMENTS UTILISES', 'MIC. DIR.', 'MISSION VERTUEUSE\n', 'MUERT FLS\n',
    'NEC. SUT.', 'NON\n', 'Non\n', 'OIS A', 'OIS C', 'OIS D', 'OIS E',
    'Otitis\n', 'PERSONAS', 'PJA A', 'PJA C', 'PJA D', 'PJA E', 'PLbTANO',
    'PSN A', 'PSN B', 'Proctitis\n', 'R.CANG', 'R.TCHNKO', 'RESULTATS',
    'Rectite\n', 'Saignement.\n', 'Salchicha\n', 'Sangrando.\n',
    'TEATRO DEMO\n', 'TIPOS', 'TIRAR\n', 'Tendinitis\n', 'UNGUENTO', 'Vin\n',
    'Vino\n', 'Yogur\n',
] + ['SPT %s' % c for c in 'CDEFGHIJK'] + ['SRPT %s' % c for c in 'ABCDEFGHIJK']

KEEP = [
    # award / rank names -- TITLE_AWARD keeps these in English inside the quotes
    'CHAMELEON', 'COW', 'DOBERMAN', 'EAGLE', 'FOX', 'FOXHOUND', 'HOUND',
    'INFINITY', 'JAGUAR', 'LEOPARD', 'PANTHER', 'PIG', 'PIGEON', 'PUMA',
    'TARANTULA',
    # jukebox tracks -- same policy as MUSIC_TITLE
    "JUMPIN' JOHNNY", 'PILLOW TALK', 'SAILOR', 'SALTY CATFISH', 'SURFING GUITAR',
    # language list -- shown in each language's own name
    'English', 'French', 'German', 'Italian', 'Spanish',
    # difficulty names -- MEDICINE's rank conditions already keep NORMAL/HARD/EXTREME
    'EASY', 'HARD',
    # 3-7 byte slots with no Korean form that short
    'PATRIOT', 'MIC', 'TCHNKO', 'Bike',
    # character names whose english-labelled locations sit in the French block
    'EVA', 'MAJOR ZERO', 'SIGINT', 'THE BOSS',
    # engine placeholder, not display text
    'undefinded\n',
]

T = {
    'TIME': '시간',
    'ALERT MODE': '경계 모드',
    'APPROVED BY': '승인',
    'BASIC ACTIONS\n': '기본 조작\n',
    'BATTERY': '배터리',
    'BOOK': '잡지',
    'BRIEFING FILES\n': '브리핑 파일\n',
    'BUG JUICE': '방충제',
    'BULLET BEE\n': '총알벌\n',
    'CAMERA': '카메라',
    'CBOX B': '상자B',
    'CBOX C': '상자C',
    'CIG SPRAY': '가스시가',
    'CIGAR': '시가',
    'COLD\n': '감기\n',
    'Cold\n': '감기\n',
    'Cold:\n': '감기:\n',
    'CRAB': '게',
    'CROC CAP': '악어모자',
    'Create\n': '작성\n',
    'DATA >': '기록>',
    'DATA > NOW': '기록>현재',
    'DISCARD\n': '버리기\n',
    'Escape': '탈출',
    'FORK': '포크',
    'Frostbite\n': '동상\n',
    'HANDKER': '손수건',
    'KEY A': '열쇠A',
    'KEY B': '열쇠B',
    'KEY C': '열쇠C',
    'KIND': '종류',
    'KINDS': '종류',
    'LF MED': '회복약',
    'LIFE BAR': 'LIFE바',
    'LIFE BARS': 'LIFE바',
    'MONKEY MASK': '원숭이 가면',
    'MOUSETRAP': '쥐덫',
    'NEW GAME\n': '새 게임\n',
    'NONE': '없음',
    'NOT USED': '미사용',
    'OFF\n': '끔\n',
    'PEOPLE': '명',
    'PEOPLE KILLED': '살상',
    'PERSON': '명',
    'R.CRAB': '희귀게',
    'RESULTS': '결과',
    'REVIVAL.P': '소생약',
    'SERIOUS INJURIES': '중상',
    'STEALTH': '스텔스',
    'STOMACH ACHE\n': '복통\n',
    'Shagohod': '샤고호드',
    'Special\n': '특수\n',
    'TRANSMITTER\n': '발신기\n',
    'Transmitter:\n': '발신기:\n',
    'TUXEDO': '턱시도',
    'Tea\n': '차\n',
    'VIRTUOUS MISSION\n': '버추어스 미션\n',
    'Volgin': '볼긴',
    'Warning\n': '경고\n',
    'Wine\n': '와인\n',
    'Beehive': '벌집',
}

if __name__ == '__main__':
    pb.run_batch('SHORT_LABEL', T, 'STAGE_SHORT_LABEL_2026-08-19')
