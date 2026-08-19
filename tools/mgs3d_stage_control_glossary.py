# -*- coding: utf-8 -*-
"""Korean for the TUTORIAL_CONTROL text runs, in compressed UI style.

Approved 2026-08-19: gameplay information (button names, actions, conditions,
effects) is kept in full; particles, subjects and repeated predicates are cut.
Nothing is dropped just to fit a byte budget -- a row that cannot fit without
losing meaning is reported as HUMAN instead.

Every run below is the exact ASCII run extracted from the resource bytes by
mgs3d_stage_control_author.decompose(). Control and glyph bytes never appear
here; they are reproduced verbatim by the assembler.
"""

# --- fixed terminology -------------------------------------------------------
GLOSSARY = {
    'Attack Button': '공격 버튼',
    'Aim Button': '조준 버튼',
    'Confirm Button': '확인 버튼',
    'Circle Pad': '서클 패드',
    'BACK': '뒤로',
    'OK': '확인',
}

# --- shared sentence tails ---------------------------------------------------
# "Ready w/ Aim Button (A)" -> "조준 버튼(A)으로 준비"
READY = ':\n조준 버튼('

RUNS = {
    # ---- high-frequency fragments ------------------------------------------
    ') is pressed.\n': ')을 누른 시간에 따름.\n',
    '),\nthrow w/ Attack Button (': ')으로 준비,\n공격 버튼(',
    ').\nDistance varies by how long\nAttack Button (': ')으로 투척.\n거리는 공격 버튼(',
    ' : BACK\n': ' : 뒤로\n',
    ' : OK\n': ' : 확인\n',
    '),\nfire w/ Attack Button (': ')으로 준비,\n공격 버튼(',
    ') is\npressed.\n': ')을 누른\n시간에 따름.\n',
    ') to remove object.\n': ')으로 제거.\n',
    '), throw w/ Attack\nButton (': ')으로 준비,\n공격 버튼(',
    '), fire w/ Attack\nButton (': ')으로 준비,\n공격 버튼(',
    ' : MOVE CURSOR\n': ' : 커서 이동\n',
    ' : EXIT VIEWER MODE\n': ' : 뷰어 종료\n',
    ') to ready,\nthen Attack Button (': ')으로 준비 후\n공격 버튼(',
    ') to swallow.\n': ')으로 섭취.\n',
    ') to apply.\n': ')으로 사용.\n',
    '). Distance varies by\nhow long Attack Button (': ')으로 투척.\n거리는 공격 버튼(',
    ' : SWITCH CATEGORY\n': ' : 분류 전환\n',
    ' : ROTATE MODEL\n': ' : 모델 회전\n',
    ' : MOVE MODEL\n': ' : 모델 이동\n',
    ' : ZOOM IN\n': ' : 확대\n',
    ' : ZOOM OUT\n': ' : 축소\n',
    ' : DEFAULT POSITION\n': ' : 기본 위치\n',
    'Bare hands:\nNo weapon equipped. Press\nAttack Button (': '맨손:\n무기 없음. 공격 버튼(',
    '), set w/ Attack\nButton (': ')으로 준비,\n공격 버튼(',
    '), set w/ Attack Button (': ')으로 준비, 공격 버튼(',
    '), throw w/\nAttack Button (': ')으로 준비,\n공격 버튼(',
    '). Distance\nvaries by how long Attack\nButton (': ')으로 투척.\n거리는 공격 버튼(',
    '), throw w/ Attack Button\n(': ')으로 준비,\n공격 버튼(',
    '). Distance varies by how\nlong Attack Button (': ')으로 투척.\n거리는 공격 버튼(',
    '). Touch Supressor\nIcon (ON/OFF) to attach/detach\nsuppressor.\n':
        ')으로 발사.\n소음기 아이콘(ON/OFF)으로\n탈착.\n',

    # ---- control-help labels ------------------------------------------------
    ' : ADJUST FREQUENCY\n': ' : 주파수 조정\n',
    ' : SEND\n': ' : 송신\n',
    ' : BACK\nDURING COMMUNICATIONS\n': ' : 뒤로\n통신 중\n',
    ' : FAST FORWARD\n': ' : 빨리 감기\n',
    ' : PAUSE/ADVANCE\n': ' : 일시정지/진행\n',
    ' : ADVANCE (WHEN PAUSED)\n': ' : 진행(정지 중)\n',
    ' : SWITCH CONTROL MODE\n': ' : 조작 모드 전환\n',
    ' : MOVE ITEM ICON\n': ' : 아이템 이동\n',
    ' : MOVE WEAPON ICON\n': ' : 무기 이동\n',
    ' : MOVE MAP\n': ' : 지도 이동\n',
    ' : SWITCH AREAS\n': ' : 구역 전환\n',
    ' : SWITCH FLOORS\n': ' : 층 전환\n',
    ' : MOVE PHOTO\n': ' : 사진 이동\n',
    ' : MOVE PHOTO (SLOW)\n': ' : 사진 이동(느림)\n',
    ' : SWITCH CROP SIZE\n': ' : 자르기 크기\n',
    ' : CONFIRM SIZE & POSITION\n': ' : 크기,위치 확정\n',
    ' : NEXT EXPLANATION PAGE\n': ' : 다음 설명\n',
    ' : DISPLAY HISTORY\n': ' : 기록 표시\n',
    ' : EXPAND X-RAY AREA\n': ' : 투시 확대\n',
    ' : SHRINK X-RAY AREA\n': ' : 투시 축소\n',
    ' : SCROLL THROUGH HIST.\n': ' : 기록 스크롤\n',
    ' : SWITCH HISTORIES\n': ' : 기록 전환\n',
    ' : CLOSE HISTORY\n': ' : 기록 닫기\n',

    # ---- traps / tools ------------------------------------------------------
    'A bait trap for luring small animals and\ncapturing them alive.\nPress Aim Button (':
        '작은 동물을 유인해 산 채로\n포획하는 덫.\n조준 버튼(',
    ') to set.\nCrawl over a trap to retrieve it.\n': ')으로 설치.\n포복으로 지나가면 회수.\n',
    'A spent ammo magazine.\nPress Aim Button (': '빈 탄창.\n조준 버튼(',
    ') to throw.\n': ')으로 투척.\n',
    'A torch made from white birch soaked in\npine tree resin. Press Attack Button (':
        '송진에 적신 자작나무 횃불.\n공격 버튼(',
    ')\nto swing it around as a weapon. Touch\nFire Icon (ON/OFF) to light/extinguish.\n':
        ')으로 무기처럼 휘두름.\n불 아이콘(ON/OFF)으로 점화,소화.\n',

    # ---- medicine -----------------------------------------------------------
    'Antidote :\nEffective for treating food poisoning.\nPress the Confirm Button (':
        '해독제 :\n식중독 치료에 효과적.\n확인 버튼(',
    'Bandage :\nEffective for treating burns, cuts,\ngunshot wounds, and broken bones.\nPress the Confirm Button (':
        '붕대 :\n화상,열상,총상,골절\n치료에 효과적.\n확인 버튼(',
    ') to wrap injury.\n': ')으로 감기.\n',
    'Cigar :\nEffective for removing leeches attached to the body.\nPress the Confirm Button (':
        '시가 :\n몸에 붙은 거머리 제거에 효과적.\n확인 버튼(',
    ') to\npress cigar against leech.\n': ')으로\n거머리에 지짐.\n',
    'Cold Medicine :\nEffective for treating colds.\nPress the Confirm Button (':
        '감기약 :\n감기 치료에 효과적.\n확인 버튼(',
    'Digestive Medicine :\nEffective for treating stomach aches.\nPress the Confirm Button (':
        '소화제 :\n복통 치료에 효과적.\n확인 버튼(',
    'Fork :\nEffective for removing bullets and arrows.\nPress the Confirm Button (':
        '포크 :\n탄환,화살 제거에 효과적.\n확인 버튼(',
    'Ointment :\nEffective for treating burns.\nPress the Confirm Button (':
        '연고 :\n화상 치료에 효과적.\n확인 버튼(',
    'Serum :\nEffective for treating venom poisoning.\nPress the Confirm Button (':
        '혈청 :\n독 치료에 효과적.\n확인 버튼(',
    ') to inject.\n': ')으로 주사.\n',
    'Splint :\nEffective for helping broken bones to heal.\nPress the Confirm Button (':
        '부목 :\n골절 회복에 효과적.\n확인 버튼(',
    ') to set.\n': ')으로 고정.\n',
    'Styptic :\nEffective for treating cuts and gunshot wounds.\nPress the Confirm Button (':
        '지혈제 :\n열상,총상 치료에 효과적.\n확인 버튼(',
    ') to apply\nand stop bleeding.\n': ')으로 발라\n지혈.\n',
    'Suture Kit :\nEffective for treating cuts.\nPress the Confirm Button (':
        '봉합 키트 :\n열상 치료에 효과적.\n확인 버튼(',
    ') to sew injury.\n': ')으로 봉합.\n',
    'Disinfectant :\nEffective for treating cuts and gunshot wounds.\nPress the Confirm Button (':
        '소독약 :\n열상,총상 치료에 효과적.\n확인 버튼(',
    'Survival Knife :\nEffective for removing bullets and arrows.\nPress the Confirm Button (':
        '서바이벌 나이프 :\n탄환,화살 제거에 효과적.\n확인 버튼(',
    'Survival Knife :\nEffective for removing bullets, arrows,\nand tranquilizer darts.\nPress the Confirm Button (':
        '서바이벌 나이프 :\n탄환,화살,마취침\n제거에 효과적.\n확인 버튼(',
    'Disinfectant :\nEffective for treating cuts, gunshot wounds,\nand bullet bees.\nPress the Confirm Button (':
        '소독약 :\n열상,총상,벌 쏘임\n치료에 효과적.\n확인 버튼(',
    'Survival Knife :\nEffective for removing bullets, arrows,\nand bullet bees.\nPress the Confirm Button (':
        '서바이벌 나이프 :\n탄환,화살,벌침\n제거에 효과적.\n확인 버튼(',

    # ---- explosives / weapons ----------------------------------------------
    'Trinitrotoluene (TNT).\nA military-grade explosive equipped\nwith a remote-controlled detonator.\nPress Aim Button (':
        'TNT.\n원격 기폭 장치가 달린\n군용 폭약.\n조준 버튼(',
    ') to set.\nAfter setting, press Attack Button (': ')으로 설치.\n설치 후 공격 버튼(',
    ')\nwithout readying TNT to detonate.\n': ')을\n준비 없이 눌러 기폭.\n',
    ') to punch,\npress repeatedly to perform a\ncombo.\n': ')으로 타격,\n연타로 연속기.\n',
    ') to punch,\npress repeatedly to perform a\ncombo, or hold to restrain\nenemy. Hold while moving the\nCircle Pad to throw.\n':
        ')으로 타격, 연타로 연속기,\n길게 눌러 적 제압.\n누른 채 서클 패드로 던지기.\n',
    'AK-47:\nSoviet assault rifle.\nReady w/ Aim Button (': 'AK-47:\n소련 돌격소총.\n조준 버튼(',
    'C3:\nPlastic explosive. Ready w/\nAim Button (': 'C3:\n플라스틱 폭약.\n조준 버튼(',
    '). Can only be set on\nor near liquid fuel tanks in\nhangar.\n':
        ')으로 설치.\n격납고 액체연료 탱크\n부근에만 설치 가능.\n',
    'Chaff Grenade:\nJams equipment. Ready w/ Aim\nButton (': '채프 수류탄:\n기기 교란.\n조준 버튼(',
    '). Distance varies\nby how long Attack Button (': ')으로 투척.\n거리는 공격 버튼(',
    ')\nis pressed.\n': ')을\n누른 시간에 따름.\n',
    'Cigarette Gas Gun:\nKnockout gas gun disguised as\na cigarette. Ready w/ Aim\nButton (':
        '담배형 가스총:\n담배로 위장한 마취 가스총.\n조준 버튼(',
    'Claymore:\nFrontal anti-personnel\nlandmine. Ready w/ Aim Button\n(': '클레이모어:\n지향성 대인 지뢰.\n조준 버튼(',
    ').\nCrawl over to retrieve.\n': ')으로 설치.\n포복으로 회수.\n',
    'Directional Microphone:\nMicrophone that can pick up\nthe minutest sounds. Ready w/\nAim Button (':
        '지향성 마이크:\n미세한 소리까지 포착.\n조준 버튼(',
    ') & point in\ndesired direction.\n': ')으로 준비 후\n원하는 방향을 겨냥.\n',
    'EZ GUN:\nSpecial silent tranquilizer\ngun. Ready w/ Aim Button (':
        'EZ GUN:\n특수 무음 마취총.\n조준 버튼(',
    ').\nBoosts Camo Index & stamina\nrecovery.\n': ')으로 발사.\n위장률,스태미나 회복 상승.\n',
    'Fork:\nReady w/ Aim Button (': '포크:\n조준 버튼(',
    '), press\nAttack Button (': ')으로 준비,\n공격 버튼(',
    ') to slash or\npress firmly to stab. Press\nrepeatedly to do a combo.\nPlants & animals captured with\nthis can be eaten on the spot.\n':
        ')으로 베기,\n깊게 눌러 찌르기, 연타로 연속기.\n이것으로 잡은 동식물은\n그 자리에서 섭취 가능.\n',
    'Grenade:\nReady w/ Aim Button (': '수류탄:\n조준 버튼(',
    'M1911A1:\n.45 auto. Ready w/ Aim Button\n(': 'M1911A1:\n.45 자동권총.\n조준 버튼(',
    '), fire w/ Attack Button\n(': ')으로 준비,\n공격 버튼(',
    '). Touch Supressor Icon\n(ON/OFF) to attach/detach\nsuppressor.\n':
        ')으로 발사.\n소음기 아이콘(ON/OFF)으로\n탈착.\n',
    'M37:\n12 gauge shotgun. Ready w/ Aim\nButton (': 'M37:\n12게이지 산탄총.\n조준 버튼(',
    '). A direct hit will\nsend enemies flying.\n': ')으로 발사.\n직격 시 적이 날아감.\n',
    'M63:\nAmerican light machine gun.\nReady w/ Aim Button (': 'M63:\n미국제 경기관총.\n조준 버튼(',
    'Magazine:\nEmpty mag. Ready w/ Aim Button\n(': '탄창:\n빈 탄창.\n조준 버튼(',
    'Mk22:\nTranquilizer gun. Ready w/ Aim\nButton (': 'Mk22:\n마취총.\n조준 버튼(',
    'Mousetrap:\nTrap for capturing small\nanimals alive. Ready w/ Aim\nButton (':
        '쥐덫:\n작은 동물을 산 채로 포획.\n조준 버튼(',
    '). Crawl over to\nretrieve.\n': ')으로 설치.\n포복으로 회수.\n',
    'RPG-7:\nPortable rocket launcher.\nReady w/ Aim Button (': 'RPG-7:\n휴대용 로켓 발사기.\n조준 버튼(',
    ').\nScope available in FPS Mode.\nCannot use when prone.\n':
        ')으로 발사.\nFPS 모드에서 조준경 사용.\n포복 중 사용 불가.\n',
    'Scorpion:\n.32 caliber sub machine gun.\nReady w/ Aim Button (':
        '스코피온:\n.32구경 기관단총.\n조준 버튼(',
    'Smoke Grenade:\nBlinds enemy w/ smoke.\nReady w/ Aim Button (': '연막탄:\n연기로 시야 차단.\n조준 버튼(',
    # 킴 is not in the global page; 무력화 carries the same meaning
    'Stun Grenade:\nKnocks out enemy. Ready w/ Aim\nButton (': '섬광탄:\n적 무력화.\n조준 버튼(',
    'Survival Knife:\nFor close combat. Ready w/ Aim\nButton (': '서바이벌 나이프:\n근접 전투용.\n조준 버튼(',
    '), press Attack Button\n(': ')으로 준비,\n공격 버튼(',
    ') to slash or press firmly\nto stab. Press repeatedly to\ndo a combo.\n':
        ')으로 베기,\n깊게 눌러 찌르기.\n연타로 연속기.\n',
    'TNT:\nExplosive with remote\ndetonator. Ready w/ Aim Button\n(': 'TNT:\n원격 기폭 폭약.\n조준 버튼(',
    ').\nAfter setting, press Attack\nButton (': ')으로 설치.\n설치 후 공격 버튼(',
    ') without readying\nTNT to detonate in order set.\n': ')을 준비 없이 눌러\n설치 순서대로 기폭.\n',
    'Torch:\nResin-soaked white birch torch.\nWave w/ Attack Button (':
        '횃불:\n송진 적신 자작나무 횃불.\n공격 버튼(',
    '),\npress repeatedly to swing\naround. Touch Fire Icon\n(ON/OFF) to light/extinguish.\n':
        ')으로 휘두름,\n연타로 크게 휘두름.\n불 아이콘(ON/OFF)으로 점화,소화.\n',
    'White Phosphorous Grenade:\nSets enemy on fire. Ready w/\nAim Button (':
        '백린 수류탄:\n적을 불태움.\n조준 버튼(',
    'XM16E1:\nAssault rifle. Ready w/ Aim\nButton (': 'XM16E1:\n돌격소총.\n조준 버튼(',
    'Knockout Handkerchief:\nHandkerchief with knockout\ndrug. Can be used in CQC grabs\nor dispersed by pressing Aim\nButton (':
        '마취 손수건:\n마취약을 적신 손수건.\nCQC 제압 시 사용하거나\n조준 버튼(',
    '), then Attack Button\n(': ')으로 준비 후\n공격 버튼(',
    'Book:\nPublication w/ adult-oriented\nmaterial. Full of girly photos\n& interesting columns. Ready\nw/ Aim Button (':
        '책:\n성인용 잡지.\n화보와 읽을거리가 가득.\n조준 버튼(',
    '), set w/\nAttack Button (': ')으로 준비,\n공격 버튼(',
    "Hornets\\' Nest:\nHive full of honey. Ready w/\nAim Button (": '벌집:\n꿀이 가득한 벌집.\n조준 버튼(',
    "Hornets\\' Nest:\nHive full of honey.\nReady w/ Aim Button (": '벌집:\n꿀이 가득한 벌집.\n조준 버튼(',
    "Hornets\\' Nest:\nHive with The Pain\\'s hornets &\nhoney. Ready w/ Aim Button\n(":
        '벌집:\n더 페인의 벌과 꿀이 든 벌집.\n조준 버튼(',
}

# --- food / creature items: "<name>:\nReady w/ Aim Button (" ------------------
ITEM_NAMES = {
    'Arowana Meat': '아로와나 고기', 'Baikal Scaly Tooth': '바이칼 비늘치',
    'Bigeye Trevally Meat': '무명갈전갱이 고기', 'Calorie Mate': '칼로리 메이트',
    'Cobalt Blue Tarantula Meat': '코발트블루 타란툴라 고기', 'Coral Snake Meat': '산호뱀 고기',
    'Emperor Scorpion Meat': '황제전갈 고기', 'European Rabbit Meat': '유럽토끼 고기',
    'Fly Agaric': '광대버섯', 'Giant Anaconda Meat': '아나콘다 고기',
    'Golova': '골로바', 'Green Tree Python Meat': '초록나무비단뱀 고기',
    'Indian Gavial Meat': '가비알 고기', 'Instant Noodles': '인스턴트 라면',
    'Japanese Flying Squirrel Meat': '하늘다람쥐 고기', 'Kenyan Mangrove Crab Meat': '맹그로브게 고기',
    'King Cobra Meat': '킹코브라 고기', 'Liquid Meat': '리퀴드 고기',
    'Live Arowana': '산 아로와나', 'Live Bigeye Trevally': '산 무명갈전갱이',
    'Live Cobalt Blue Tarantula': '산 코발트블루 타란툴라', 'Live Coral Snake': '산 산호뱀',
    'Live Emperor Scorpion': '산 황제전갈', 'Live European Rabbit': '산 유럽토끼',
    'Live Giant Anaconda': '산 아나콘다', 'Live Green Tree Python': '산 초록나무비단뱀',
    'Live Indian Gavial': '산 가비알', 'Live Japanese Flying Squirrel': '산 하늘다람쥐',
    'Live Kenyan Mangrove Crab': '산 맹그로브게', 'Live King Cobra': '산 킹코브라',
    'Live Liquid': '산 리퀴드', 'Live Magpie': '산 까치', 'Live Markhor': '산 마코르염소',
    'Live Maroon Shark': '산 적갈색상어', 'Live Milk Snake': '산 밀크스네이크',
    'Live Otton Frog': '산 오토톤개구리', 'Live Parrot': '산 앵무새',
    'Live Poison Dart Frog': '산 독화살개구리', 'Live Rat': '산 쥐',
    'Live Red Avadavat': '산 홍작', 'Live Reticulated Python': '산 그물무늬비단뱀',
    'Live Solid': '산 솔리드', 'Live Solidus': '산 솔리더스',
    'Live Sunda Whistling Thrush': '산 순다휘파람새', 'Live Taiwan Cobra': '산 대만코브라',
    'Live Thai Cobra': '산 태국코브라', 'Live Tree Frog': '산 청개구리',
    'Live Tsuchinoko': '산 츠치노코', 'Live Vampire Bat': '산 흡혈박쥐',
    'Live White-rumped Vulture': '산 흰등독수리', 'Magpie Meat': '까치 고기',
    'Markhor Meat': '마코르염소 고기', 'Maroon Shark Meat': '적갈색상어 고기',
    'Milk Snake Meat': '밀크스네이크 고기', 'Otton Frog Meat': '오토톤개구리 고기',
    'Parrot Meat': '앵무새 고기', 'Poison Dart Frog Meat': '독화살개구리 고기',
    'Rat Meat': '쥐 고기', 'Ration': '레이션', 'Red Avadavat Meat': '홍작 고기',
    'Reticulated Python Meat': '그물무늬비단뱀 고기', 'Russian False Mango': '러시아 가짜망고',
    'Russian Glowcap': '러시아 발광버섯', 'Russian Oyster Mushroom': '러시아 느타리버섯',
    'Siberian Ink Cap': '시베리아 먹물버섯', 'Solid Meat': '솔리드 고기',
    'Solidus Meat': '솔리더스 고기', 'Spatsa': '스파차',
    'Sunda Whistling Thrush Meat': '순다휘파람새 고기', 'Taiwan Cobra Meat': '대만코브라 고기',
    'Thai Cobra Meat': '태국코브라 고기', 'Tree Frog Meat': '청개구리 고기',
    'Tsuchinoko Meat': '츠치노코 고기', 'Ural Luminescent Mushroom': '우랄 야광버섯',
    'Vampire Bat Meat': '흡혈박쥐 고기', 'Vine Melon': '덩굴참외',
    'White-rumped Vulture Meat': '흰등독수리 고기', 'Yabloko Moloko': '야블로코 몰로코',
}

for _en, _ko in ITEM_NAMES.items():
    RUNS['%s:\nReady w/ Aim Button (' % _en] = '%s:\n조준 버튼(' % _ko

# 'Ration' and 'Instant Noodles' carry an extra origin clause
RUNS['Ration:\nMade in USSR. Ready w/ Aim\nButton ('] = '레이션:\n소련제.\n조준 버튼('
RUNS['Instant Noodles:\nMade in Japan. Ready w/ Aim\nButton ('] = '인스턴트 라면:\n일본제.\n조준 버튼('
RUNS['Calorie Mate:\nA balanced nutritional food.\nReady w/ Aim Button ('] = \
    '칼로리 메이트:\n영양 균형 식품.\n조준 버튼('

# --- donor rows: never translated -------------------------------------------
DONOR_RUNS = {
    ' : DEPLACER CURSEUR\n', ' : RETOUR\n',
}
