# -*- coding: utf-8 -*-
"""MEDICINE batch: Korean for the stage medicine / status / condition rows.

Compressed UI style, approved 2026-08-19: every game-relevant fact (item name,
effect, cure, condition value) is kept; particles and predicates are cut.
Item names reuse the terminology fixed in the TUTORIAL_CONTROL glossary
(해독제 / 붕대 / 혈청 / 소화제 ...).

Keys are the resource's exact plain text including its own 0x0A line breaks --
the on-screen layout is per line, so the line structure is preserved.
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

T = {
    # ---- short labels -------------------------------------------------------
    'PENTAZEMIN': '펜타제민',
    'SERUM': '혈청',
    'MEDICINE USED': '약품 사용',
    'Bolt extracted.\n': '화살 제거.\n',
    'Bullet extracted.\n': '탄환 제거.\n',
    'Cure EVA.\n': 'EVA 치료.\n',
    'Needs medicine.\n': '약품 필요.\n',
    'Ointment not applied.\n': '연고 미사용.\n',
    'Cure wounds or diseases.\n': '부상,질병 치료.\n',
    'No wounds/diseases to treat.\n': '치료할 부상,질병 없음.\n',
    'Cure\nCure wounds or diseases.\n': '치료\n부상,질병 치료.\n',
    'Afflicted area\nfastened with splint.\n': '부목으로\n환부 고정.\n',

    # ---- status messages ----------------------------------------------------
    'A bandage pattern camo uniform. Wearing it\nprevents you from being seriously injured.\n':
        '붕대 무늬 위장복. 착용하면\n중상을 입지 않는다.\n',
    'Poisoned.\nLIFE will continually\ndecrease until\nneutralized.\nTo cure, inject\nserum.\n':
        '중독.\n중화할 때까지\nLIFE 계속 감소.\n치료하려면\n혈청 주사.\n',
    'Caught a cold.\nStamina will\ncontinually\ndecrease until\ncured.\nTo cure, take\ncold medicine.\n':
        '감기.\n치료할 때까지\n스태미나\n계속 감소.\n치료하려면\n감기약.\n',
    'Food poisoning\ncontracted from\neating rotten food.\nStamina will\ncontinually decrease\nuntil cured.\nTo cure, take\ndigestive medicine.\n':
        '상한 음식 섭취로\n인한 식중독.\n치료할 때까지\n스태미나 계속 감소.\n치료하려면\n소화제.\n',
    'Food poisoning\ncontracted from\neating naturally\npoisonous food.\nLIFE will\ncontinually decrease\nuntil cured.\nTo cure, use the\nantidote.\n':
        '자연독 음식\n섭취로 인한\n식중독.\n치료할 때까지\nLIFE 계속 감소.\n치료하려면\n해독제.\n',

    # ---- item descriptions --------------------------------------------------
    'LIFE Medicine:\nDeveloped by USSR. Restores\nLIFE. Touch Use Icon to use.\n':
        'LIFE 회복약:\n소련 개발. LIFE 회복.\n사용 아이콘으로 사용.\n',
    'Revival Pill:\nEspionage pill developed by\nthe CIA. Revives user from\nfake death. Touch Use Icon to\nuse.\n':
        '소생 알약:\nCIA가 개발한 첩보용\n알약. 가사 상태에서\n소생. 사용 아이콘으로\n사용.\n',
    'Fake Death Pill:\nEspionage pill developed by\nthe CIA. Can fake death\ntemporarily. Touch Use Icon\nto use.\n':
        '가사 알약:\nCIA가 개발한 첩보용\n알약. 일시적으로 가사\n상태. 사용 아이콘으로\n사용.\n',
    'Pentazemin:\nBenzodiazepine antianxiety\ndrug. Temporarily supresses\nhand tremors when using sniper\nrifles. Touch Use Icon to use.\n':
        '펜타제민:\n벤조디아제핀계 항불안제.\n저격총 사용 시 손떨림을\n일시 억제.\n사용 아이콘으로 사용.\n',

    # ---- encyclopedia -------------------------------------------------------
    'Baikal Scaly Tooth.\nContains poison neutralizing properties. Picking\none will cause an Antidote item to appear.\nTried it. Tasted terrible.\n':
        '바이칼 비늘치.\n독을 중화하는 성분이 있다. 채집하면\n해독제가 나온다.\n먹어봤다. 맛이 끔찍했다.\n',
    'Baikal Scaly Tooth.\nContains poison neutralizing properties. Picking\none will cause an Antidote item to appear.\nNot eaten yet. Said not to be very good.\n':
        '바이칼 비늘치.\n독을 중화하는 성분이 있다. 채집하면\n해독제가 나온다.\n미섭취. 맛은 별로라고 한다.\n',
    'Russian False Mango. A fruit resembling a mango\nthat grows only in Tselinoyarsk.\nIts seeds cure stomach aches. Picking one will\ncause a Digestive Medicine item to appear.\nTried it. Was pretty tasty.\n':
        '러시아 가짜망고. 첼리노야르스크에만\n자라는 망고 비슷한 열매.\n씨는 복통에 듣는다. 채집하면\n소화제가 나온다.\n먹어봤다. 꽤 맛있었다.\n',
    'Russian False Mango. A fruit resembling a mango\nthat grows only in Tselinoyarsk.\nIts seeds cure stomach aches. Picking one will\ncause a Digestive Medicine item to appear.\nNot eaten yet. Said to be tasty.\n':
        '러시아 가짜망고. 첼리노야르스크에만\n자라는 망고 비슷한 열매.\n씨는 복통에 듣는다. 채집하면\n소화제가 나온다.\n미섭취. 맛있다고 한다.\n',
    'European Rabbit. Originally from the Mediterranean\nregion, but now found throughout the world.\nThe European rabbits in this region carry special\nanti-venom agents in their blood. Capturing one\nwill cause a Serum item to appear.\nTried it. Not too bad.\n':
        '유럽토끼. 원래 지중해 지역 토종이나\n지금은 세계 각지에 분포.\n이 지역 유럽토끼는 피에 특수한 항독\n성분을 지닌다. 포획하면\n혈청이 나온다.\n먹어봤다. 나쁘지 않았다.\n',
    'European Rabbit. Originally from the Mediterranean\nregion, but now found throughout the world.\nThe European rabbits in this region carry special\nanti-venom agents in their blood. Capturing one\nwill cause a Serum item to appear.\nNot eaten yet. Known to be edible.\n':
        '유럽토끼. 원래 지중해 지역 토종이나\n지금은 세계 각지에 분포.\n이 지역 유럽토끼는 피에 특수한 항독\n성분을 지닌다. 포획하면\n혈청이 나온다.\n미섭취. 먹을 수 있다고 한다.\n',

    # ---- rank conditions ----------------------------------------------------
    'Conditions:\nPlay Time: 6h or less\nContinues: 0\nAlert Modes: 10 or less\nPeople Killed: 0\nMedicine Used: 0\nSpecial Items: Not Used\n':
        '조건:\n플레이 시간: 6시간 이하\n컨티뉴: 0\n경계: 10회 이하\n살상: 0\n약품 사용: 0\n특수 아이템: 미사용\n',
    'Conditions:\nDifficulty: NORMAL or higher\nPlay Time: 5h30m or less\nContinues: 0\nAlert Modes: 5 or less\nPeople Killed: 0\nMedicine Used: 0\nSpecial Items: Not Used\n':
        '조건:\n난이도: NORMAL 이상\n플레이 시간: 5시간 30분 이하\n컨티뉴: 0\n경계: 5회 이하\n살상: 0\n약품 사용: 0\n특수 아이템: 미사용\n',
    'Conditions:\nDifficulty: HARD or higher\nPlay Time: 5h or less\nSaves: 35 or less\nContinues: 0\nAlert Modes: 3 or less\nPeople Killed: 0\nMedicine Used: 0\nSpecial Items: Not Used\n':
        '조건:\n난이도: HARD 이상\n플레이 시간: 5시간 이하\n세이브: 35회 이하\n컨티뉴: 0\n경계: 3회 이하\n살상: 0\n약품 사용: 0\n특수 아이템: 미사용\n',
    'Conditions :\nPlay Time : 50h or more\nSaves : 100 or more\nContinues : 60 or more\nAlert Modes : 250 or more\nPeople Killed : 250 or more\nSerious Injuries : 250 or more\nDamage Taken : 30 bars or more\nMedicine Used : 10 or more\n':
        '조건 :\n플레이 시간 : 50시간 이상\n세이브 : 100회 이상\n컨티뉴 : 60회 이상\n경계 : 250회 이상\n살상 : 250명 이상\n중상 : 250회 이상\n피해 : 30칸 이상\n약품 사용 : 10회 이상\n',
    'Conditions :\nDifficulty : EXTREME\nPlay Time : 5h or less\nSaves : 25 or less\nContinues : 0\nAlert Modes : 0\nPeople Killed : 0\nSerious Injuries : 20 or less\nDamage Taken : 5 bars or less\nMedicine Used : 0\nSpecial Items : Not Used\n':
        '조건 :\n난이도 : EXTREME\n플레이 시간 : 5시간 이하\n세이브 : 25회 이하\n컨티뉴 : 0\n경계 : 0\n살상 : 0\n중상 : 20회 이하\n피해 : 5칸 이하\n약품 사용 : 0\n특수 아이템 : 미사용\n',
}

if __name__ == '__main__':
    pb.run_batch('MEDICINE', T, 'STAGE_MEDICINE_2026-08-19')
