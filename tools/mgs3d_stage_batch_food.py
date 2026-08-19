# -*- coding: utf-8 -*-
"""FOOD batch: Korean for the stage food / stamina / camo-uniform rows.

Keys are the resource's exact raw plain text (including its own 0x0A line
breaks) -- the worklist's `english` column is display-only and flattens them.

Scales kept distinct and ordered:
  taste     맛이 끔찍했다 < 맛있었다 < 제법 < 꽤 < 상당히 < 믿을 수 없이
  stamina   거의 없음 < 미미 < 소량 < 제법 < 보통 < 양호 < 매우 양호 < 큼 < 최상
Terms reused from codec/TUTORIAL/MEDICINE: 스태미나, 위장률, 레이션, EZ GUN,
서바이벌 나이프, 러시아 가짜망고, 식중독.
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
    # ---- labels -------------------------------------------------------------
    'Instant Noodles\n': '인스턴트 라면\n',
    'MEALS EATEN': '식사 횟수',
    'Food Poisoning\n': '식중독\n',
    'Food Poisoning:\n': '식중독:\n',
    'EAT\nEat food.\n': '먹기\n먹는다.\n',
    'DISCARD\nDispose of food.\n': '버리기\n음식을 버린다.\n',
    'Eat food gathered.\n': '모은 음식 섭취.\n',
    'Food\nEat food gathered.\n': '음식\n모은 음식 섭취.\n',
    'Came down with food poisoning.\n': '식중독에 걸렸다.\n',
    'EVA came down with food poisoning.\n': 'EVA가 식중독에 걸렸다.\n',

    # ---- stamina recovery scale ---------------------------------------------
    'Barely noticeable stamina recovery.\n': '스태미나 회복 거의 없음.\n',
    'Slight stamina recovery.\n': '스태미나 회복 미미.\n',
    'Small stamina recovery.\n': '스태미나 회복 소량.\n',
    'Decent stamina recovery.\n': '스태미나 회복 제법.\n',
    'Moderate stamina recovery.\n': '스태미나 회복 보통.\n',
    'Good stamina recovery.\n': '스태미나 회복 양호.\n',
    'Very good stamina recovery.\n': '스태미나 회복 매우 양호.\n',
    'Great stamina recovery.\n': '스태미나 회복 큼.\n',
    'Excellent stamina recovery.\n': '스태미나 회복 최상.\n',

    "EVA's stamina recovery was barely noticeable.\n": 'EVA의 스태미나 회복 거의 없음.\n',
    "EVA's stamina recovery was slight.\n": 'EVA의 스태미나 회복 미미.\n',
    "EVA's stamina recovery was small.\n": 'EVA의 스태미나 회복 소량.\n',
    "EVA's stamina recovery was decent.\n": 'EVA의 스태미나 회복 제법.\n',
    "EVA's stamina recovery was moderate.\n": 'EVA의 스태미나 회복 보통.\n',
    "EVA's stamina recovery was good.\n": 'EVA의 스태미나 회복 양호.\n',
    "EVA's stamina recovery was very good.\n": 'EVA의 스태미나 회복 매우 양호.\n',
    "EVA's stamina recovery was great.\n": 'EVA의 스태미나 회복 큼.\n',
    "EVA's stamina recovery was excellent.\n": 'EVA의 스태미나 회복 최상.\n',

    # ---- eaten-taste lines --------------------------------------------------
    'Arowana\nWas pretty tasty.\n': '아로와나\n꽤 맛있었다.\n',
    'Giant Anaconda\nWas quite tasty.\n': '대왕 아나콘다\n상당히 맛있었다.\n',
    'Golova\nWas fairly tasty.\n': '골로바\n제법 맛있었다.\n',
    'Green Tree Python\nWas pretty tasty.\n': '그린 트리 파이톤\n꽤 맛있었다.\n',
    'Indian Gavial\nWas tasty.\n': '인도 가비알\n맛있었다.\n',
    'Kenyan Mangrove Crab\nWas pretty tasty.\n': '케냐 맹그로브 게\n꽤 맛있었다.\n',
    'Reticulated Python\nWas fairly tasty.\n': '그물무늬비단뱀\n제법 맛있었다.\n',
    'Russian False Mango\nWas pretty tasty.\n': '러시아 가짜망고\n꽤 맛있었다.\n',
    'Vine Melon\nWas pretty tasty.\n': '덩굴 멜론\n꽤 맛있었다.\n',
    'Ration\nTasted terrible.\n': '레이션\n맛이 끔찍했다.\n',
    'Calorie Mate\nIt was unbelievably tasty!\n': '칼로리 메이트\n믿을 수 없이 맛있었다!\n',
    'Instant Noodles\nIt was unbelievably tasty!\n': '인스턴트 라면\n믿을 수 없이 맛있었다!\n',
    'Liquid\nUnbelievably tasty!\n': '리퀴드\n믿을 수 없는 맛!\n',
    'Magpie\nTaste unknown, but said to be edible.\n':
        '까치\n맛은 모르나 먹을 수 있다고 한다.\n',
    'Siberian Ink Cap\nTaste unknown, but said to be edible.\n':
        '시베리아 먹물버섯\n맛은 모르나 먹을 수 있다고 한다.\n',
    'Sunda Whistling-Thrush\nTaste unknown, but said to be edible.\n':
        '순다 휘파람지빠귀\n맛은 모르나 먹을 수 있다고 한다.\n',

    # ---- item descriptions --------------------------------------------------
    'Calorie Mate. A balanced nutrition food invented in\nJapan.\nContains a healthy balance of all five major\nnutrients : protein, fat, carbohydrates, vitamins,\nand minerals.\nIt was unbelievably tasty!\n':
        '칼로리 메이트. 일본에서 개발된 균형\n영양식.\n단백질, 지방, 탄수화물, 비타민, 미네랄\n5대 영양소를 고루 함유.\n믿을 수 없이 맛있었다!\n',
    'Calorie Mate. Never seen a food like this before.\nIt was unbelievably tasty!\n':
        '칼로리 메이트. 처음 보는 음식이다.\n믿을 수 없이 맛있었다!\n',
    "Instant Noodles. The world's first instant noodles,\ninvented in Japan.\nJust add hot water and they're ready to eat.\nIt was unbelievably tasty!\n":
        '인스턴트 라면. 일본에서 개발된\n세계 최초의 인스턴트 라면.\n뜨거운 물만 부으면 바로 먹을 수 있다.\n믿을 수 없이 맛있었다!\n',
    'Instant Noodles. Turns into a noodle meal.\nIt was unbelievably tasty!\n':
        '인스턴트 라면. 면 요리가 된다.\n믿을 수 없이 맛있었다!\n',
    "Ration. A portable ration issued by the Russian\nmilitary. High in nutrients and designed to last\nwithout spoiling.\nBut it's not very good.\n":
        '레이션. 러시아군 지급 휴대 식량.\n영양가가 높고 잘 상하지 않도록\n만들어졌다.\n하지만 맛은 별로다.\n',
    "Ration. A portable ration issued by the Russian\nmilitary. High in nutrients and designed to last\nwithout spoiling.\nBut it's said to not be very good.\n":
        '레이션. 러시아군 지급 휴대 식량.\n영양가가 높고 잘 상하지 않도록\n만들어졌다.\n하지만 맛은 별로라고 한다.\n',
    'Magpie. A member of the crow family. Native to\nNorth America and the Eurasian continent.\nDistinguished by its beautiful dark blue and\nwhite body and its long tail.\nTaste unknown, but said to be edible.\n':
        '까치. 까마귀과의 새.\n북아메리카와 유라시아 대륙에 서식.\n아름다운 짙은 청색과 흰색 몸통,\n긴 꼬리가 특징.\n맛은 모르나 먹을 수 있다고 한다.\n',
    'Maroon Shark. A member of the carp family native\nto Southeast Asia.\nIts meat is tasty, but a little oily.\n':
        '마룬 샤크. 동남아시아에 서식하는\n잉어과 물고기.\n살은 맛있지만 약간 기름지다.\n',
    'A fork. Used for eating.\nCan be used in place of the survival knife.\nPlants and animals nabbed using the fork can be\neaten on the spot.\n':
        '포크. 식사용.\n서바이벌 나이프 대신 사용 가능.\n포크로 잡은 동식물은 그 자리에서\n먹을 수 있다.\n',

    # ---- camo uniforms ------------------------------------------------------
    'A banana pattern camo uniform. It makes any food\ntaste great.\n':
        '바나나 무늬 위장복. 어떤 음식이든\n맛있게 만든다.\n',
    "The Fear's camo uniform. Gives wearer stealth\ncapability at the cost of stamina.\n":
        '피어의 위장복. 스태미나를 소모해\n스텔스 능력을 준다.\n',
    "The Sorrow's camo uniform. Eliminates footstep\nnoise. Also allows wearer to drain stamina by\nchoking enemies in CQC.\n":
        '소로우의 위장복. 발소리가 사라진다.\nCQC로 적의 목을 조르면\n스태미나를 흡수한다.\n',
    'The latest battle uniform developed by the Soviet\nUnion. Cuts all damage in half and reduces\nstamina consumption.\n':
        '소련이 개발한 최신 전투복.\n모든 피해를 절반으로 줄이고\n스태미나 소모를 감소시킨다.\n',
    'The EZ GUN. A suppressed tranquilizer gun\ndeveloped especially for FOX. The suppression\nfunction is built into the gun itself. Also equipped\nwith an internal laser sight. When equipped,\ncauses stamina to recover faster and keeps\nthe Camo Index high. Also eliminates footstep\nnoise.\n':
        'EZ GUN. FOX를 위해 개발된 소음기 내장\n마취총. 총 자체에 소음 기능이 있다.\n레이저 사이트도 내장. 장비하면\n스태미나 회복이 빨라지고\n위장률이 높게 유지된다.\n발소리도 사라진다.\n',

    # ---- status / screens ---------------------------------------------------
    'Bloodsucking\nleeches attached to\nbody. Stamina will\ncontinually decrease\nwhile leeches\nare attached.\nTo remove leeches,\nburn them off\nwith a lit cigar.\n':
        '몸에 흡혈 거머리가\n붙었다. 붙어 있는\n동안 스태미나가\n계속 감소한다.\n거머리를 떼려면\n불붙인 시가로\n태운다.\n',
    'Shot with a\ntranquilizer needle.\nStamina will\ndecrease until\ntreated. Will lose\nconsciousness if\nstamina reaches\nzero. To extract a\nneedle, use a knife.\n':
        '마취 바늘에\n맞았다.\n치료할 때까지\n스태미나 감소.\n스태미나가 0이 되면\n의식을 잃는다.\n바늘은 나이프로\n뽑는다.\n',
    'About this screen :\nHere you choose which character to\nfeed. Select EVA when you want to\nrestore her stamina.\n':
        '이 화면 설명 :\n음식을 먹일 대상을 선택한다.\nEVA의 스태미나를 회복시키려면\nEVA를 선택한다.\n',
    'Condition :\nMeals Eaten : 250 or more\n':
        '조건 :\n식사 횟수 : 250회 이상\n',
    'Hint :\nAwarded to those who complete\ntheir mission having eaten a\ncountless amount of food.\n':
        '힌트 :\n수많은 음식을 먹으며\n임무를 완수한 자에게\n주어진다.\n',
}

if __name__ == '__main__':
    pb.run_batch('FOOD', T, 'STAGE_FOOD_2026-08-19')
