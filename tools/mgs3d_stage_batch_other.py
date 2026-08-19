# -*- coding: utf-8 -*-
"""OTHER batch: rank conditions/hints, equipment, camo, status, scene titles.

Whole-string translation rather than the line-composed path used for
FLORA_FAUNA: the Hint/Condition rows share their first line but nothing else,
and composing them line by line produced Korean that read as three disconnected
fragments. Translating the row lets the Korean carry its own clause order while
still preserving the source's line count.

DONOR below is classified from the raw neighbourhood, same method as
SHORT_LABEL: R.SPT/R.OIS/R.SET/R.PSN/R.FRT are the Spanish and French
serpiente/oiseau/seta/poisson/fruit lists, and the food names sit in the FR/ES
menu blocks.
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
    'Alubias frias\n', 'Carpaccio de poulpe\n', 'Carpaccio de pulpo\n',
    'Cobra Real\n', 'Cobra real\n', 'EQUIPEMENT SUPPLEMENTAIRE IMPOSSIBLE.\n',
    'Foie gras de pato\n', 'Gelatina china\n', 'Gyoza de crevette cuit\n',
    'Hueso roto.\n', 'MAJOR ZERO\nContacta con Major Zero.\n',
    'Marinade de saumon\n', 'Pan Foccacia\n', 'Pato Peking\n',
    'Rollo de mantequilla\n', 'Rouleau de printemps\n',
    'Salade de pissenlits,\n', "Soupe d'aileron de\n", 'Terreur nocturne\n',
    'Terror nocturno\n', 'Tortilla de queso\n', 'ACTIONS DE BASE\n',
    'Chico temerario...', 'Plataforma volante', 'Rescata a Sokolov',
    'Teatro Demo "Peep"', 'The End muere de viejo',
] + ['R.SPT %s' % c for c in 'ABCDEFGHIJK'] \
  + ['R.OIS %s' % c for c in 'ABCDE'] \
  + ['R.SET %s' % c for c in 'ABCDEFG'] \
  + ['R.PSN A', 'R.PSN B', 'R.FRT A', 'R.FRT B']

KEEP = [
    'ROCK ME BABY', "DON'T BE AFRAID", 'Chyornyj Prud\n',
]

HINT = '힌트 :\n'
COND = '조건 :\n'
AWARD = '완수한 자에게\n주어진다.\n'

T = {
    # ---- difficulty / mode blurbs ------------------------------------------
    'For beginners.\n': '초보자용.\n',
    'For confident players.\n': '숙련자용.\n',
    'Standard difficulty level.\n': '표준 난이도.\n',
    'Game ends when being seen by enemy.\n': '적에게 발각되면 게임 종료.\n',
    'Not Change yet.\n': '아직 변경 없음.\n',
    'WIG : Interior\n': 'WIG : 실내\n',
    'METAL GEAR ACID LINK\n': 'METAL GEAR ACID 연동\n',

    # ---- camo effect lines --------------------------------------------------
    'Effective in black environments.\n': '검은 환경에서 효과적.\n',
    'Effective in gray environments.\n': '회색 환경에서 효과적.\n',
    'Effective in white environments.\n': '흰색 환경에서 효과적.\n',
    'Effective in blue environments.\n': '푸른 환경에서 효과적.\n',
    'Effective in dark green environments.\n': '짙은 녹색 환경에서 효과적.\n',
    'Effective in green environments.\n': '녹색 환경에서 효과적.\n',
    'Effective in light brown environments.\n': '연갈색 환경에서 효과적.\n',
    'Effective in mountainous terrain.\n': '산악 지형에서 효과적.\n',
    'Effective in water.\n': '물속에서 효과적.\n',
    'Effective when underwater.\n': '수중에서 효과적.\n',
    'For cold environments.\n': '한랭지용.\n',
    'For indoor-ops.\n': '실내 작전용.\n',
    'For use in forested areas.\n': '삼림 지대용.\n',
    'Water:\nEffective when underwater.\n': '수중:\n수중에서 효과적.\n',
    'AUSCAM Desert:\nEspecially effective against white backgrounds.\n':
        'AUSCAM 사막:\n흰색 배경에서 특히 효과적.\n',
    'Black:\nEffective in dark areas or against black ground.\n':
        '검정:\n어두운 곳이나 검은 지면에서 효과적.\n',
    'Chocolate Chip:\nEffective in desert or mountain environments.\n':
        '초콜릿 칩:\n사막이나 산악 환경에서 효과적.\n',
    'Desert Tiger:\nEspecially effective against brown backgrounds.\n':
        '데저트 타이거:\n갈색 배경에서 특히 효과적.\n',
    'Desert:\nEffective in mountainous terrain.\n': '사막:\n산악 지형에서 효과적.\n',
    'Rain Drop:\nEffective in the rain.\n': '레인 드롭:\n빗속에서 효과적.\n',
    'Snow:\nEffective against white backgrounds.\n': '설원:\n흰색 배경에서 효과적.\n',
    'Snow:\nFor cold environments.\n': '설원:\n한랭지용.\n',
    'Splitter:\nEffective in an urban environment.\n': '스플리터:\n도시 환경에서 효과적.\n',
    'Splitter:\nFor indoor-ops.\n': '스플리터:\n실내 작전용.\n',
    'Squares:\nEffective against brown backgrounds.\n': '사각형:\n갈색 배경에서 효과적.\n',
    'Tiger Stripe:\nEffective in trees, grass, or against soil.\n':
        '타이거 스트라이프:\n숲, 풀밭, 흙에서 효과적.\n',
    'Tree Bark:\nEffective when pressed against trees.\n': '나무껍질:\n나무에 붙으면 효과적.\n',
    'Woodland:\nFor use in forested areas.\n': '우드랜드:\n삼림 지대용.\n',
    'Naked:\nNothing worn on the upper body.\n': '맨몸:\n상체에 아무것도 입지 않음.\n',
    'Mask used for disguise.\n': '변장용 가면.\n',
    'Mask:\nMask used for disguise.\n': '가면:\n변장용 가면.\n',
    'Formal dress coat.\n': '정장 코트.\n',
    'Sneaking Suit:\nAdvanced combat suit developed by the USSR.\n':
        '스니킹 슈트:\n소련이 개발한 고성능 전투복.\n',
    'Camouflage pattern made using a\nphotograph. Various camouflage\neffects are possible depending on\nthe photograph used.\n':
        '사진으로 만든 위장 무늬.\n사용한 사진에 따라\n다양한 위장 효과를\n얻을 수 있다.\n',

    # ---- survival viewer ----------------------------------------------------
    "Baltic Hornets' Nest\n": '발트 말벌집\n',
    'Green Tree Python\n': '그린 트리 파이톤\n',
    'Kenyan Mangrove Crab\n': '케냐 맹그로브 게\n',
    'King Cobra\n': '킹코브라\n',
    'Taiwanese Cobra\n': '대만코브라\n',
    'Thai Cobra\n': '태국코브라\n',
    'Fly Agaric\n': '광대버섯\n',
    'Russian Glowcap\n': '러시아 발광버섯\n',
    'Baikal Scaly Tooth\nTasted terrible.\n': '바이칼 비늘치\n맛이 끔찍했다.\n',
    'Bigeye Trevally\nTasted bad.\n': '큰눈전갱이\n맛없었다.\n',
    'Cobalt Blue Tarantula\nTasted bad.\n': '코발트블루 타란툴라\n맛없었다.\n',
    'Fly Agaric\nWas poisonous.\n': '광대버섯\n독이 있었다.\n',
    "Green Tree Python\nAsked about flavor, but wasn't answered.\n":
        '그린 트리 파이톤\n맛을 물었지만 답을 듣지 못했다.\n',
    'King Cobra\nWas not bad.\n': '킹코브라\n괜찮았다.\n',
    'Magpie\nTasted bad.\n': '까치\n맛없었다.\n',
    'Markhor\nTasted great.\n': '마코르\n아주 맛있었다.\n',
    'Maroon Shark\nNot half bad.\n': '마룬 샤크\n제법이었다.\n',
    "Red Avadavat\nAsked about flavor, but wasn't answered.\n":
        '홍작\n맛을 물었지만 답을 듣지 못했다.\n',
    'Russian Glowcap\nRecharged the battery after eating.\n':
        '러시아 발광버섯\n먹었더니 배터리가 충전됐다.\n',
    'Siberian Ink Cap\nTasted bad.\n': '시베리아 먹물버섯\n맛없었다.\n',
    'Spatsa\nBecame sleepy after eating.\n': '스파차\n먹은 뒤 졸음이 왔다.\n',
    'Sunda Whistling-Thrush\nWas not bad.\n': '순다 휘파람지빠귀\n괜찮았다.\n',
    'Taiwanese Cobra\nNot half bad.\n': '대만코브라\n제법이었다.\n',
    'Thai Cobra\nNot half bad.\n': '태국코브라\n제법이었다.\n',
    'F.DEATH.P': '가사약',
    'F.DEATH.P\n': '가사약\n',

    # ---- food menu ----------------------------------------------------------
    'Chilled Red Beans with\n': '차가운 붉은콩과\n',
    'Chinese Almond Jelly\n': '행인두부\n',
    'Cold Vegetables\n': '냉채\n',
    'Duck Foie Gras\n': '오리 푸아그라\n',
    'Green Tea\n': '녹차\n',
    'Matsutake Mushrooms\n': '송이버섯\n',
    'Rice with Dried Sardines\n': '멸치 덮밥\n',
    'Salmon and\n': '연어와\n',
    'Shrimp and Russian\n': '새우와 러시아\n',
    'Tofu with\n': '두부와\n',
    'Tuna, Sea Bream and\n': '참치, 도미와\n',
    'Feed EVA.\n': 'EVA 급식\n',
    'EAT\nFeed EVA.\n': '식사\nEVA 급식\n',
    "EVA doesn't seem to be hungry.\n": 'EVA는 배고프지 않은 듯하다.\n',
    'EVA looks sleepy.\n': 'EVA가 졸려 한다.\n',
    'Not hungry.\n': '배부르다.\n',
    'Seems to have been rotten.\nEVA seems to have a stomach ache.\n':
        '상한 듯하다.\nEVA가 복통을 앓는 듯하다.\n',
    'Was rotten. Stomach starting to ache.\n': '상해 있었다. 배가 아프기 시작.\n',
    'Became sleepy.\n': '졸음이 왔다.\n',
    'Battery has recovered.\n': '배터리 회복.\n',

    # ---- wounds / status ----------------------------------------------------
    'Abdomen pierced by\ntree branch.\nSuffering from deep\ncut.\n':
        '나뭇가지에 복부가\n관통됐다.\n깊은 상처를\n입었다.\n',
    'Almost healed.\n': '거의 나았다.\n',
    'Almost healed.\nShould soon heal\ncompletely.\n': '거의 나았다.\n곧 완전히\n낫는다.\n',
    'Bone fractured.\n': '뼈가 부러졌다.\n',
    'Bullet Bee:\n': '총알벌:\n',
    'Bullet bee eating\naway at inside of\nbody.\n': '총알벌이\n몸속을 파먹고\n있다.\n',
    'Gunshot wound\ninflicted by The\nBoss. Bullet has\nbecome lodged in\nbody.\n':
        '더 보스에게\n입은 총상.\n탄환이\n몸에 박혀\n있다.\n',
    'Hardly healed at all.\n': '거의 낫지 않았다.\n',
    'Healing nicely.\n': '잘 낫고 있다.\n',
    'Needs an operation.\n': '수술이 필요하다.\n',
    'Night Terror\n': '야경증\n',
    'Not yet disinfected.\n': '아직 소독 안 함.\n',
    'Nothing in cage.\n': '우리가 비었다.\n',
    'Plastic Surgery\n': '성형수술\n',
    'Starting to heal a\nlittle.\n': '조금씩 낫기\n시작했다.\n',
    'Stomach Ache:\n': '복통:\n',
    'Suffering from\nsevere burns.\n': '심한 화상을\n입었다.\n',
    'Tick-borne Encephalitis\n': '진드기 뇌염\n',

    # ---- menus / system -----------------------------------------------------
    "CAN'T EQUIP ANY MORE.\n": '더 장비할 수 없다.\n',
    'Call\nUse the radio.\n': '통신\n무전기 사용.\n',
    'Data\nView data.\n': '기록\n기록 보기.\n',
    'Map\nDisplay area map.\n': '지도\n지역 지도 표시.\n',
    'Change Settings?\n': '설정 변경?\n',
    'Restore default settings?\n': '기본 설정으로 되돌릴까요?\n',
    'HEALING RADIO\nListen to the Healing Radio.\n': '힐링 라디오\n힐링 라디오를 듣는다.\n',
    'Insecticide :\nSpray insecticide.\n': '살충제 :\n살충제를 뿌린다.\n',
    'MAJOR ZERO\nContact Major Zero.\n': '제로 소령\n제로 소령에게 연락.\n',
    'Over the Soviet border.\n': '소련 국경을 넘었다.\n',
    'Read Successful\n': '읽기 완료\n',
    'Transfer failed.\n': '전송 실패.\n',
    'Transfer succeeded.\n': '전송 완료.\n',
    'Set camera speed.\n': '카메라 속도 설정.\n',
    'Set camera controls.\n': '카메라 조작 설정.\n',
    'Set FPS camera controls.\n': 'FPS 카메라 조작 설정.\n',
    'Set FPS camera speed.\n': 'FPS 카메라 속도 설정.\n',
    'Set TPS camera controls.\n': 'TPS 카메라 조작 설정.\n',
    'Set TPS camera speed.\n': 'TPS 카메라 속도 설정.\n',
    'Set quick change method.\n': '빠른 교체 방식 설정.\n',
    'Adjust screen brightness.\n': '화면 밝기 조정.\n',
    'Adjust screen position.\n': '화면 위치 조정.\n',
    'Adjust the monitor brightness so that the gray\nscale under the orange line is no longer seen\nto obtain optimal brightness for this game.\n':
        '주황색 선 아래 회색조가 보이지 않도록\n모니터 밝기를 조절하면\n이 게임에 최적인 밝기가 됩니다.\n',
    'I like MGS1!\n': 'MGS1 좋아!\n',
    'I like MGS2!\n': 'MGS2 좋아!\n',
    'I like MGS3!\n': 'MGS3 좋아!\n',
    'I like MGS4!\n': 'MGS4 좋아!\n',
    "I'm playing MGS for the first time!\n": 'MGS는 처음이야!\n',
    "What's your favorite METAL GEAR SOLID?\n": '가장 좋아하는 METAL GEAR SOLID는?\n',
    'PLANTS & ANIMALS CAPTURED': '포획한 동식물',
    'YOUR TITLE IS ...': '당신의 칭호는 ...',
    'Really delete this data?\n(Deleted data cannot be\nrecovered.)\n':
        '이 데이터를 삭제할까요?\n(삭제 후에는 복구할 수\n없습니다.)\n',
    'About this screen :\nHere you choose which character to\nheal. Select EVA when you want to\nheal her.\n':
        '이 화면 설명 :\n치료할 대상을 선택한다.\nEVA를 치료하려면\nEVA를 선택한다.\n',
    'SINGLE ACTION ARMY': '싱글 액션 아미',
    'NATIONAL FLAG FACE PAINTS': '국기 페이스 페인트',

    # ---- SD card / extra data ----------------------------------------------
    'Could not recognize SD Card.\n': 'SD 카드를 인식할 수 없음.\n',
    'Not enough free space on SD\nCard.\n': 'SD 카드의 빈 공간이\n부족합니다.\n',
    'SD Card is read-only.\n': 'SD 카드가 읽기 전용.\n',
    'This SD Card cannot store any\nmore photos.\n': '이 SD 카드에는\n사진을 더 저장할 수 없음.\n',
    'Could not process SD Card.\n': 'SD 카드를 처리할 수 없음.\n',
    'An unexpected error has been detected.\n': '예기치 못한 오류가 발생했습니다.\n',
    'Create new extra data.\n': '추가 데이터 새로 작성.\n',
    'Creating extra data...\n': '추가 데이터 작성 중\n',
    'Damaged extra data can be\ndeleted in System Settings.\n':
        '손상된 추가 데이터는 본체\n설정에서 삭제 가능.\n',
    'Deleting extra data.\n': '추가 데이터 삭제 중.\n',
    'Extra data created.\n': '추가 데이터 작성.\n',
    'Extra data deleted.\n': '추가 데이터 삭제.\n',
    'Extra data is damaged.\nDeleting extra data.\n': '추가 데이터 손상.\n추가 데이터 삭제 중.\n',
    'Extra data preparation complete.\n': '추가 데이터 준비 완료.\n',
    'Prepare extra data.\n': '추가 데이터 준비.\n',
    'Preparing extra data.\n': '추가 데이터 준비 중.\n',
    'Saved successfully.\n': '저장 완료.\n',
    'Unable to read extra data.\n': '추가 데이터 읽기 실패.\n',
    'Connection failed.\nCheck that the Circle Pad Pro is attached\ncorrectly and the battery has enough power.\n':
        '연결 실패.\n서클 패드 프로가 올바로 장착됐는지,\n배터리 잔량이 충분한지 확인하세요.\n',
    "The Circle Pad Pro's remaining battery\npower is low.\n":
        '서클 패드 프로의 배터리\n잔량이 부족합니다.\n',

    # ---- equipment descriptions --------------------------------------------
    'A handkerchief soaked in anesthetic.\nCan be used to put enemies to sleep after\ngrabbing them with CQC.\n':
        '마취제를 적신 손수건.\nCQC로 붙잡은 적을\n잠재울 때 쓴다.\n',
    'A high-performance directional microphone.\nPicks up sound in the direction it is pointed.\nCan be used to pick up the footsteps of distant\nenemies and other sounds normally too faint to\nhear.\n':
        '고성능 지향성 마이크.\n향한 방향의 소리를 잡아낸다.\n멀리 있는 적의 발소리처럼\n평소에는 들리지 않는 소리도\n들을 수 있다.\n',
    'A picture book for "gentlemen." Full of stunning\nphotos of young, female models.\n':
        '"신사"를 위한 화보집. 젊은 여성\n모델의 화려한 사진이 가득하다.\n',
    'Active Sonar:\nSensor that detects animals w/\nsound waves. Touch Use Icon to\nemit waves. Consumes battery\npower while used.\n':
        '액티브 소나:\n음파로 동물을 탐지하는 센서.\n사용 아이콘으로 음파 발신.\n사용 중 배터리를\n소모한다.\n',
    'Binoculars:\nMilitary binoculars allowing\nlong-distance reconnaissance.\nUse slider to adjust\nmagnification.\n':
        '쌍안경:\n원거리 정찰이 가능한\n군용 쌍안경.\n슬라이더로 배율을\n조절한다.\n',
    'Bug Juice:\nBug repellent. Keeps away\nhornets & leeches while it\nlasts. Touch Use Icon to apply.\n':
        '방충제:\n벌레 기피제. 효과가 지속되는\n동안 말벌과 거머리를\n막는다. 사용 아이콘으로 사용.\n',
    'Camera:\nMilitary-grade camera. Touch\nUse Icon to take a photo. Use\nslider to adjust magnification.\n':
        '카메라:\n군용 카메라. 사용 아이콘으로\n사진 촬영. 슬라이더로\n배율을 조절한다.\n',
    'Cardboard Box A:\nEquip to wear. Says "To the\nWeapons Lab: East Wing" on\nthe side.\n':
        '골판지 상자 A:\n장비하면 쓴다. 옆면에\n"무기 연구소: 동관"이라고\n적혀 있다.\n',
    'Cardboard Box B:\nEquip to wear. Says "To the\nWeapons Lab: Hangar" on the\nside.\n':
        '골판지 상자 B:\n장비하면 쓴다. 옆면에\n"무기 연구소: 격납고"라고\n적혀 있다.\n',
    'Cardboard Box C:\nEquip to wear. Letters on the\nside cannot be read.\n':
        '골판지 상자 C:\n장비하면 쓴다. 옆면 글자는\n읽을 수 없다.\n',
    'Cigar:\nHighly addictive and hazardous\nto your health.\n':
        '시가:\n중독성이 강하고 건강에\n해롭다.\n',
    'Key A:\nPunch card type card key\nobtained from Granin. Opens\nred door in the southeast of\nPonizovje warehouse.\n':
        '열쇠A:\n그라닌에게 받은 펀치카드식\n카드 키. Ponizovje 창고\n남동쪽 붉은 문을 연다.\n',
    'Key B:\nKey obtained from EVA.\nOpens door in the east of\nKrasnogorje mountaintop.\n':
        '열쇠B:\nEVA에게 받은 열쇠.\nKrasnogorje 산정\n동쪽 문을 연다.\n',
    'Key C:\nKey obtained from EVA.\nOpens door to hangar at\nweapons lab main wing.\n':
        '열쇠C:\nEVA에게 받은 열쇠.\n무기 연구소 본관\n격납고 문을 연다.\n',
    "Motion Detector:\nSensor that detects an\nobject\\'s motion. Does not\ndetect stationary objects.\nConsumes battery power\nwhile used.\n":
        '움직임 감지기:\n물체의 움직임을 감지하는\n센서. 정지한 물체는\n감지하지 못한다.\n사용 중 배터리를\n소모한다.\n',

    # ---- rank conditions ----------------------------------------------------
    'Condition :\nAlert Modes : 0\n': COND + '경계 : 0\n',
    'Condition :\nAlert Modes : 250 or more\n': COND + '경계 : 250회 이상\n',
    'Condition :\nPeople Killed : 0\n': COND + '살상 : 0\n',
    'Condition :\nPeople Killed : 250 or more\n': COND + '살상 : 250명 이상\n',
    'Condition :\nPlay Time : 5 hours or less\n': COND + '플레이 시간 : 5시간 이하\n',
    'Condition :\nPlay Time : 50 hours or more\n': COND + '플레이 시간 : 50시간 이상\n',
    'Condition :\nSaves : 100 or more\n': COND + '세이브 : 100회 이상\n',
    'Condition :\nSerious Injuries : 20 or less\n': COND + '중상 : 20회 이하\n',
    'Condition :\nSerious Injuries : 250 or more\n': COND + '중상 : 250회 이상\n',
    'Condition :\nClear the game having captured\nevery plant and animal.\n':
        COND + '모든 동식물을 포획한 채로\n게임 클리어.\n',
    'Condition :\nClear the game having shaken\nall the Yoshi dolls (multiple\nclears allowed).\n':
        COND + '요시 인형을 모두 흔든 채로\n게임 클리어 (여러 번\n클리어 가능).\n',
    'Condition :\nClear the game with a leech\nattached to your body.\n':
        COND + '몸에 거머리가 붙은 채로\n게임 클리어.\n',

    # ---- combined rank conditions ------------------------------------------
    'Conditions :\nContinues : 50 or less\nAlert Modes : 35 or less\nPeople Killed : 100 or less\n':
        '조건 :\n컨티뉴 : 50회 이하\n경계 : 35회 이하\n살상 : 100명 이하\n',
    'Conditions :\nContinues : 50 or less\nAlert Modes : 35 or less\nPeople Killed : 101 or more\n':
        '조건 :\n컨티뉴 : 50회 이하\n경계 : 35회 이하\n살상 : 101명 이상\n',
    'Conditions :\nContinues : 50 or less\nAlert Modes : 36 or more\nPeople Killed : 100 or less\n':
        '조건 :\n컨티뉴 : 50회 이하\n경계 : 36회 이상\n살상 : 100명 이하\n',
    'Conditions :\nContinues : 50 or less\nAlert Modes : 36 or more\nPeople Killed : 101 or more\n':
        '조건 :\n컨티뉴 : 50회 이하\n경계 : 36회 이상\n살상 : 101명 이상\n',
    'Conditions :\nContinues : 51 or more\nAlert Modes : 35 or less\nPeople Killed : 100 or less\n':
        '조건 :\n컨티뉴 : 51회 이상\n경계 : 35회 이하\n살상 : 100명 이하\n',
    'Conditions :\nContinues : 51 or more\nAlert Modes : 35 or less\nPeople Killed : 101 or more\n':
        '조건 :\n컨티뉴 : 51회 이상\n경계 : 35회 이하\n살상 : 101명 이상\n',
    'Conditions :\nContinues : 51 or more\nAlert Modes : 36 or more\nPeople Killed : 100 or less\n':
        '조건 :\n컨티뉴 : 51회 이상\n경계 : 36회 이상\n살상 : 100명 이하\n',
    'Conditions :\nContinues : 51 or more\nAlert Modes : 36 or more\nPeople Killed : 101 or more\n':
        '조건 :\n컨티뉴 : 51회 이상\n경계 : 36회 이상\n살상 : 101명 이상\n',

    # ---- rank hints ---------------------------------------------------------
    'Hint :\nAwarded to those who achieve\na mediocre result in any difficulty.\n':
        HINT + '어떤 난이도에서든 평범한\n결과를 낸 자에게 주어진다.\n',
    'Hint :\nAwarded to those who achieve\nthe highest result in EXTREME\ndifficulty.\n':
        HINT + 'EXTREME 난이도에서 최고\n결과를 낸 자에게\n주어진다.\n',
    'Hint:\nAwarded to those who achieve\na distinguished result in HARD\ndifficulty or higher.\n':
        '힌트:\nHARD 난이도 이상에서\n뛰어난 결과를 낸 자에게\n주어진다.\n',
    'Hint:\nAwarded to those who achieve\na distinguished result in NORMAL\ndifficulty or higher.\n':
        '힌트:\nNORMAL 난이도 이상에서\n뛰어난 결과를 낸 자에게\n주어진다.\n',
    'Hint:\nAwarded to those who achieve\na distinguished result.\n':
        '힌트:\n뛰어난 결과를 낸 자에게\n주어진다.\n',
    'Hint :\nAwarded to those who complete\ntheir mission having avoided\ndanger.\n':
        HINT + '위험을 피하며 임무를\n' + AWARD,
    'Hint :\nAwarded to those who complete\ntheir mission after a long\namount of time.\n':
        HINT + '오랜 시간에 걸쳐 임무를\n' + AWARD,
    'Hint :\nAwarded to those who complete\ntheir mission having been\ninjured countless times.\n':
        HINT + '수없이 부상당하며 임무를\n' + AWARD,
    'Hint :\nAwarded to those who complete\ntheir mission having captured\nevery plant and animal.\n':
        HINT + '모든 동식물을 포획하고\n임무를 완수한 자에게\n주어진다.\n',
    'Hint :\nAwarded to those who complete\ntheir mission having exposed\nthemselves to danger and failed\nmany times.\n':
        HINT + '위험에 노출되고 여러 번\n실패하며 임무를 완수한\n자에게 주어진다.\n',
    'Hint :\nAwarded to those who complete\ntheir mission having exposed\nthemselves to danger and left\nmany victims in their wake.\n':
        HINT + '위험에 노출되고 수많은\n희생자를 남기며 임무를\n완수한 자에게 주어진다.\n',
    'Hint :\nAwarded to those who complete\ntheir mission having exposed\nthemselves to danger countless\ntimes.\n':
        HINT + '수없이 위험에 노출되며\n임무를 완수한 자에게\n주어진다.\n',
    'Hint :\nAwarded to those who complete\ntheir mission having exposed\nthemselves to danger, failed\nmany times, and left many\nvictims in their wake.\n':
        HINT + '위험에 노출되고 여러 번\n실패하며 수많은 희생자를\n남기고 임무를 완수한\n자에게 주어진다.\n',
    'Hint :\nAwarded to those who complete\ntheir mission having exposed\nthemselves to danger.\n':
        HINT + '위험에 노출된 채 임무를\n' + AWARD,
    'Hint :\nAwarded to those who complete\ntheir mission having failed many\ntimes, and left many victims in\ntheir wake.\n':
        HINT + '여러 번 실패하고 수많은\n희생자를 남기며 임무를\n완수한 자에게 주어진다.\n',
    'Hint :\nAwarded to those who complete\ntheir mission having failed many\ntimes.\n':
        HINT + '여러 번 실패하며 임무를\n' + AWARD,
    'Hint :\nAwarded to those who complete\ntheir mission having left\ncountless victims in their wake.\n':
        HINT + '수없는 희생자를 남기며\n임무를 완수한 자에게\n주어진다.\n',
    'Hint :\nAwarded to those who complete\ntheir mission having left many\nvictims in their wake.\n':
        HINT + '수많은 희생자를 남기며\n임무를 완수한 자에게\n주어진다.\n',
    'Hint :\nAwarded to those who complete\ntheir mission having saved\ncountless times.\n':
        HINT + '수없이 세이브하며 임무를\n' + AWARD,
    'Hint :\nAwarded to those who complete\ntheir mission while having their\nblood sucked.\n':
        HINT + '피를 빨린 채 임무를\n' + AWARD,
    'Hint :\nAwarded to those who complete\ntheir mission within a short\namount of time.\n':
        HINT + '짧은 시간에 임무를\n' + AWARD,
    'Hint :\nAwarded to those who complete\ntheir mission without exposing\nthemselves to danger.\n':
        HINT + '위험에 노출되지 않고\n임무를 완수한 자에게\n주어진다.\n',
    'Hint :\nAwarded to those who complete\ntheir mission without hurting\nthemselves.\n':
        HINT + '부상 없이 임무를\n' + AWARD,
    'Hint :\nAwarded to those who complete\ntheir mission without killing\nanyone.\n':
        HINT + '아무도 죽이지 않고\n임무를 완수한 자에게\n주어진다.\n',
    'Hint :\nAwarded to those who receive\nhelp from all the Yoshis\n(multiple clears allowed).\n':
        HINT + '모든 요시의 도움을 받은\n자에게 주어진다 (여러 번\n클리어 가능).\n',

    # ---- scene titles -------------------------------------------------------
    'Air-raid': '공습',
    'Chasing Enemies': '적 추격',
    'Commencing Virtuous Mission.': '버추어스 미션 개시.',
    'Contacting EVA': 'EVA와 교신',
    'Contacting Sokolov': '소콜로프와 교신',
    'Duel with Ocelot': '오셀롯과 결투',
    'Duel with Volgin': '볼긴과 결투',
    'Facing the Shagohod': '샤고호드와 대치',
    'Final Battle with Ocelot': '오셀롯과 최종 결전',
    'Finding the Enemy Unit': '적 부대 발견',
    'Flying Platform': '비행 플랫폼',
    'Ocelot Rebels': '오셀롯 반란',
    "Ocelot's Chase": '오셀롯의 추격',
    'Peep Demo Theater': 'Peep 데모 시어터',
    'Reckless Boy...': '무모한 녀석...',
    'Release of the Bullet Bees': '총알벌 방출',
    'Returning to Tselinoyarsk': '첼리노야르스크로 귀환',
    'Reuniting with Ocelot': '오셀롯과 재회',
    'Reuniting with The Boss': '더 보스와 재회',
    'Seizing the Shagohod': '샤고호드 탈취',
    'Shagohod Destroys Hind': '샤고호드가 하인드 격파',
    'Sokolov is Taken': '소콜로프 연행',
    'The Bike Crashes': '바이크 추락',
    "The Boss' Confession": '더 보스의 고백',
    'The Death of The Boss': '더 보스의 죽음',
    'The Death of The End': '디 엔드의 죽음',
    'The Death of The Fear': '피어의 죽음',
    'The Death of The Fury': '퓨리의 죽음',
    'The Death of The Pain': '페인의 죽음',
    'The Death of Volgin': '볼긴의 죽음',
    'The End Dies of Old Age': '디 엔드, 노쇠사',
    'The Fear Appears': '피어 등장',
    'The Pain Appears': '페인 등장',
    'To the Lake': '호수로',
}
for _c in 'ABCDE':
    T['R.MUSHRM %s' % _c] = '희귀버섯%s' % _c

if __name__ == '__main__':
    pb.run_batch('OTHER', T, 'STAGE_OTHER_2026-08-19')
