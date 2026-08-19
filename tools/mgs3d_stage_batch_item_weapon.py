# -*- coding: utf-8 -*-
"""ITEM_WEAPON batch (plain rows): weapons, equipment, camo, face paint.

Keys are the resource's exact raw plain text. Terms verified against the codec
master before use: 볼긴 / 퓨리 / 페인 / 디 엔드 / 라이코프 / 요시 / 클레이모어 /
위장복 / 전투복 / 저격총 / 돌격소총 / 탄창 / 소음기 / 마취총 / 야간 투시경 /
열영상 / 지뢰 탐지기 / 페이스 페인트.

Where a slot is too tight for 페이스 페인트 (17-19 B rows) the block uses the
shorter 페인트, which the codec master also uses; the meaning is unambiguous
because every one of those rows sits inside the face-paint list.
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

FLAG = {
    'the American flag': '미국 국기',
    'the British flag': '영국 국기',
    'the French flag': '프랑스 국기',
    'the German flag': '독일 국기',
    'the Italian flag': '이탈리아 국기',
    'the Japanese flag': '일본 국기',
    'the Soviet flag': '소련 국기',
    'the Spanish flag': '스페인 국기',
    'the Swedish flag': '스웨덴 국기',
}

T = {
    # ---- equipment name list ------------------------------------------------
    'KNIFE': '칼',
    'UNIFORM/BANANA': '위장복/바나나',
    'UNIFORM/BLACK': '위장복/검정',
    'UNIFORM/COLD WAR': '위장복/냉전',
    'UNIFORM/FIRE': '위장복/화염',
    'UNIFORM/FLY': '위장복/파리',
    'UNIFORM/FRUIT': '위장복/과일',
    'UNIFORM/MUMMY': '위장복/미라',
    'UNIFORM/NAKED': '위장복/맨몸',
    'UNIFORM/OFFICER': '위장복/장교',
    'UNIFORM/SCIENTIST': '위장복/연구원',
    'UNIFORM/SNEAKING': '위장복/잠입',
    'UNIFORM/SNOW': '위장복/설원',
    'UNIFORM/SPIRIT': '위장복/정령',
    'UNIFORM/WATER': '위장복/수중',

    # ---- award / unlock names ----------------------------------------------
    'AUSCAM DESERT CAMO': '오스캠 사막 위장',
    'BROWN FACE PAINT': '갈색 페인트',
    'GREEN FACE PAINT': '녹색 페인트',
    'INFINITY FACE PAINT': '무한 페인트',

    # ---- menu headers -------------------------------------------------------
    'Backpack\nPick weapon & equipment to use.\n': '배낭\n사용할 무기와 장비 선택.\n',
    'Uniform\nSelect uniform to be worn.\n': '위장복\n착용할 위장복 선택.\n',
    'Weapon\nSelect weapon to place on person.\n': '무기\n소지할 무기 선택.\n',
    'Face Paint\nSelect face paint.\n': '페이스 페인트\n페인트 선택.\n',
    'Bare hands:\nNo weapon equipped.\n': '맨손:\n장비한 무기 없음.\n',

    # ---- face paint ---------------------------------------------------------
    'Black face paint.\n': '검정 페인트.\n',
    'Black:\nBlack face paint.\n': '검정:\n검정 페인트.\n',
    'Brown face paint. The O2 Gauge will not diminish.\n':
        '갈색 페인트. O2 게이지가 줄지 않는다.\n',
    'Brown:\nBrown face paint.\n': '갈색:\n갈색 페인트.\n',
    'Green face paint. The Grip Gauge will not diminish.\n':
        '녹색 페인트. 그립 게이지가 줄지 않는다.\n',
    'Green:\nGreen face paint.\n': '녹색:\n녹색 페인트.\n',
    'No face paint applied.\n': '페인트 없음.\n',
    'No Paint:\nNo face paint applied.\n': '없음:\n페인트 없음.\n',
    'Face paint that mimics a Kabuki character.\n': '가부키 분장을 흉내낸 페인트.\n',
    'Kabuki:\nFace paint that mimics a Kabuki character.\n':
        '가부키:\n가부키 분장을 흉내낸 페인트.\n',
    'Face paint that mimics a zombie.\n': '좀비를 흉내낸 페인트.\n',
    'Zombie:\nFace paint that mimics a zombie.\n': '좀비:\n좀비를 흉내낸 페인트.\n',
    "Kabuki's female role face paint.\n": '가부키 여형 분장 페인트.\n',
    "Oyama:\nKabuki's female role face paint.\n": '온나가타:\n가부키 여형 분장 페인트.\n',
    'Face paint with infinite power.\nWeapons will not run out of ammunition.\n':
        '무한의 힘을 지닌 페인트.\n무기 탄약이 떨어지지 않는다.\n',
    'Infinity:\nFace paint with infinite power.\n':
        '무한:\n무한의 힘을 지닌 페인트.\n',
}
for _en, _ko in FLAG.items():
    T['Face paint that mimics %s.\n' % _en] = '%s를 본뜬 페인트.\n' % _ko
for _head, _en in (('France:', 'the French flag'), ('Germany:', 'the German flag'),
                   ('Italia:', 'the Italian flag'), ('Japan:', 'the Japanese flag'),
                   ('Soviet:', 'the Soviet flag'), ('Spain:', 'the Spanish flag'),
                   ('Sweden:', 'the Swedish flag'), ('UK:', 'the British flag'),
                   ('USA:', 'the American flag')):
    _kohead = {'France:': '프랑스:', 'Germany:': '독일:', 'Italia:': '이탈리아:',
               'Japan:': '일본:', 'Soviet:': '소련:', 'Spain:': '스페인:',
               'Sweden:': '스웨덴:', 'UK:': '영국:', 'USA:': '미국:'}[_head]
    T['%s\nFace paint that mimics %s.\n' % (_head, _en)] = \
        '%s\n%s를 본뜬 페인트.\n' % (_kohead, FLAG[_en])

T.update({
    # ---- grenades / explosives ---------------------------------------------
    'A Soviet-made blast fragmentation grenade.\nDeals damage to enemies with both the blast\nand the ensuing shrapnel.\n':
        '소련제 파편 수류탄.\n폭풍과 뒤이은 파편으로\n적에게 피해를 준다.\n',
    'A Soviet-made incendiary grenade. The intense\nflames created by the white phosphorus inside\ncause all living beings in the area of effect to\nsuffer severe burns.\n':
        '소련제 소이 수류탄. 내부의 백린이\n만드는 강렬한 화염이 효과 범위 내\n모든 생물에게 심한 화상을 입힌다.\n',
    "A Soviet-made smoke grenade.\nUpon detonation, releases a cloud of white smoke,\nblocking the enemy's field of vision.\n":
        '소련제 연막 수류탄.\n폭발하면 흰 연기를 뿜어\n적의 시야를 가린다.\n',
    'A electronics jamming grenade developed by the\nSoviet Union. Upon detonation, scatters a large\nquantity of metal fragments into the air, jamming\nradio signals and rendering electronic devices\ninoperative.\n':
        '소련이 개발한 전자 교란 수류탄.\n폭발하면 다량의 금속 파편을 공중에\n뿌려 무선 신호를 교란하고\n전자 기기를 무력화한다.\n',
    'A flash-bang type grenade developed by the Soviet\nUnion. Upon detonation, produces an intense flash\nof light and a loud bang, disorienting and even\nknocking out human targets in the area of effect.\n':
        '소련이 개발한 섬광 수류탄.\n폭발하면 강렬한 섬광과 굉음을 내어\n효과 범위 내의 인간 표적을\n혼란시키거나 기절시킨다.\n',
    'A Western-made, military-grade plastic explosive\nobtained from EVA.\nComposed of 77% RDX and 23% plasticizer.\n':
        'EVA에게서 얻은 서방제 군용\n플라스틱 폭약.\nRDX 77%, 가소제 23% 구성.\n',
    'An American-made anti-personnel directional mine.\nModified by Soviet technicians to automatically\ndetonate when it detects a moving object within\nthe trigger areas to its front and rear.\n':
        '미국제 대인 지향성 지뢰.\n소련 기술자가 개조해 전방과 후방의\n작동 범위 안에서 움직이는 물체를\n감지하면 자동으로 폭발한다.\n',

    # ---- weapons ------------------------------------------------------------
    'A large-bladed knife for field operations.\nCan be used to defeat enemies without making\na sound.\n':
        '야전용 대형 날 나이프.\n소리 없이 적을 제압할 수 있다.\n',
    'A modified special ops version of the\nMk22, a suppressor-equipped tranquilizer\ngun being developed by the Navy.\nAs it uses a slide lock mechanism for\nadded suppression capability, it must be\nreloaded after each shot.\nTouch Suppressor Icon (ON/OFF) to\nattach/detach suppressor.\n':
        '해군이 개발 중인 소음기 장착\n마취총 Mk22의 특수부대 개조형.\n소음 성능을 높이려 슬라이드\n고정 방식을 쓰기 때문에\n한 발 쏠 때마다 재장전해야 한다.\n소음기 아이콘 (ON/OFF)을 눌러\n소음기를 착탈한다.\n',
    'A sleeping gas pistol shaped like a cigarette.\nThe gas it sprays puts enemies to sleep.\n':
        '담배 모양의 수면 가스 권총.\n분사된 가스가 적을 잠재운다.\n',
    'The AK-47. A Soviet-made assault rifle. Reliable,\ndurable, and highly precise. Uses 7.62 x 39\nammunition. Magazine size is 30 rounds.\n\n':
        'AK-47. 소련제 돌격소총. 신뢰성과\n내구성이 높고 정밀하다. 7.62x39\n탄약 사용. 탄창 30발.\n\n',
    'The M1911A1. A .45 caliber automatic\npistol that boasts high reliability and\nmassive stopping power.\nMagazine size is 7 rounds.\nTouch Suppressor Icon (ON/OFF) to\nattach/detach suppressor.\n':
        'M1911A1. .45구경 자동 권총.\n신뢰성이 높고 저지력이\n막강하다.\n탄창 7발.\n소음기 아이콘 (ON/OFF)을 눌러\n소음기를 착탈한다.\n',
    'The M37. An American-made shotgun. The stock\nand barrel have been sawed off to reduce the\nweight. Carries four 12-gauge shells.\n':
        'M37. 미국제 산탄총. 무게를 줄이려\n개머리판과 총열을 잘라냈다.\n12게이지 탄 4발 장전.\n',
    'The M63. An American-made system weapon.\nBelt-fed light machine gun version.\nUses 5.56mm x 45 ammunition. Magazine size\nis 100 rounds.\n':
        'M63. 미국제 시스템 화기.\n탄띠 급탄식 경기관총 사양.\n5.56mm x 45 탄약 사용.\n탄창 100발.\n',
    "The Mosin Nagant. A tranquilizer sniper\nrifle, and The End's weapon of choice.\nAdapted by The End from the M1891/30,\na bolt-action sniper rifle used by the\nSoviet military during World War II.\nUses special 7.62mm x 54R tranquilizer\nrounds. Magazine size is 5 rounds. Use\nslider to adjust scope magnification.\n":
        '모신 나강. 마취 저격총이며\n디 엔드가 애용하는 무기.\n2차 대전 당시 소련군이 쓰던\n볼트액션 저격총 M1891/30을\n디 엔드가 개조했다.\n전용 7.62mm x 54R 마취탄 사용.\n탄창 5발. 슬라이더로\n조준경 배율을 조절한다.\n',
    'The RPG-7. A state-of-the-art Soviet\nportable anti-tank rocket launcher.\nThe rocket-propelled grenade warheads\nare loaded with HEAT shaped charges.\nOffers a scope view in FPS Mode.\n':
        'RPG-7. 소련의 최신 휴대용\n대전차 로켓 발사기.\n로켓 추진 유탄 탄두에는\nHEAT 성형작약이 들어 있다.\nFPS 모드에서 조준경 시야 제공.\n',
    'The SVD. A state-of-the-art Soviet\nautomatic sniper rifle known for its\nhigh precision. Uses 7.62mm x 54 rimmed\ncartridges. Magazine size is 10 rounds.\nOffers a scope view in FPS Mode.\nUse slider to adjust scope magnification.\n':
        'SVD. 소련의 최신 자동 저격총.\n정밀도가 높기로 유명하다.\n7.62mm x 54 림드탄 사용.\n탄창 10발.\nFPS 모드에서 조준경 시야 제공.\n슬라이더로 조준경 배율을 조절한다.\n',
    'The XM16E1. A state-of-the-art assault\nrifle currently being field-tested by the\nU.S. Army. Uses small caliber, high\nmuzzle velocity 5.56 x 45 ammunition.\nMagazine size is 20 rounds. Features\nseveral modifications geared toward\njungle combat. Touch Suppressor Icon\n(ON/OFF) to attach/detach suppressor.\n':
        'XM16E1. 미 육군이 현재 야전\n시험 중인 최신 돌격소총.\n소구경 고초속 5.56x45 탄약 사용.\n탄창 20발. 정글전에 맞춘\n개조가 여럿 적용됐다.\n소음기 아이콘 (ON/OFF)을 눌러\n소음기를 착탈한다.\n',

    # ---- equipment ----------------------------------------------------------
    'Mine Detector:\nEmits sound upon detection of\nClaymores on the ground. Equip\nto use. Consumes battery power\nwhile used.\n':
        '지뢰 탐지기:\n지면의 클레이모어를 탐지하면\n소리를 낸다. 장비해서 사용.\n사용 중 배터리를 소모한다.\n',
    'Night Vision Goggles:\nElectronically amplifies weak\nlight. Allows one to see in\nthe dark. Consumes battery\npower while used.\n':
        '야간 투시경:\n약한 빛을 전자적으로 증폭해\n어둠 속에서도 볼 수 있다.\n사용 중 배터리를 소모한다.\n',
    'Thermal Goggles:\nVisualizes heat source\ndistribution. Allows one to\nsee in the dark. Consumes\nbattery power while used.\n':
        '열영상 고글:\n열원 분포를 시각화한다.\n어둠 속에서도 볼 수 있다.\n사용 중 배터리를 소모한다.\n',
    'Shot with a\ntranquilizer needle.\nTo extract needle,\nuse a knife.\n':
        '마취 바늘에\n맞았다.\n바늘은 나이프로\n뽑는다.\n',

    # ---- camo patterns ------------------------------------------------------
    'A desert camo pattern designed in Australia\nthat provides excellent cover against white\nbackgrounds. Also, wearing it drops any damage\nto 2/3.\n':
        '오스트레일리아에서 설계된 사막 위장 무늬.\n흰색 배경에서 은폐 효과가 뛰어나다.\n착용하면 받는 피해가 2/3로 줄어든다.\n',
    'A forest camo pattern designed in Germany that\nprovides excellent cover in forested areas. Wearing\nit prevents battery drain.\n':
        '독일에서 설계된 삼림 위장 무늬.\n숲 지대에서 은폐 효과가 뛰어나다.\n착용하면 배터리가 소모되지 않는다.\n',
    'A forest camo pattern designed in the U.K. that\nprovides excellent cover in forested areas. Wearing\nit doubles the natural LIFE recovery rate.\n':
        '영국에서 설계된 삼림 위장 무늬.\n숲 지대에서 은폐 효과가 뛰어나다.\n착용하면 LIFE 자연 회복이 2배가 된다.\n',
    'A tiger-stripe pattern designed for desert\nenvironments. It is especially effective against\nbrown backgrounds. Also, wearing it prevents\nan equipped suppressor from wearing out with use.\n':
        '사막 환경용으로 설계된 호랑이 줄무늬.\n갈색 배경에서 특히 효과적이다.\n착용하면 장착한 소음기가\n사용해도 닳지 않는다.\n',
    'Camo pattern consisting of an array of squares.\nMakes it difficult to distinguish the silhouette of\nthe wearer.\nEffective against brown backgrounds.\n':
        '사각형이 늘어선 위장 무늬.\n착용자의 윤곽을 알아보기\n어렵게 만든다.\n갈색 배경에서 효과적.\n',
    'Camo pattern designed to provide cover in snowy\nenvironments. Effective against white backgrounds.\n':
        '설원 환경용 은폐 위장 무늬.\n흰색 배경에서 효과적.\n',
    'Camo pattern designed to provide cover in the\ndesert. Named for its resemblance to a chocolate\nchip cookie. Effective in desert and mountain\nenvironments.\n':
        '사막 은폐용으로 설계된 위장 무늬.\n초콜릿 칩 쿠키를 닮아 붙은 이름.\n사막과 산악 지대에서 효과적.\n',
    'Camo pattern designed with hunters in mind.\nPasted with photos of tree trunks and leafy\nbranches.\nEffective when pressed against trees.\n':
        '사냥꾼을 염두에 둔 위장 무늬.\n나무 줄기와 잎이 무성한 가지\n사진을 붙였다.\n나무에 붙으면 효과적.\n',
    'Camo pattern developed to provide cover in\nforested areas. Effective in underbrush.\n':
        '삼림 지대 은폐용 위장 무늬.\n덤불에서 효과적.\n',
    'Camo pattern often used on German airplanes\nduring World War II. Effective in urban\nenvironments.\n':
        '2차 대전 당시 독일 항공기에 흔히\n쓰인 위장 무늬. 도시에서 효과적.\n',
    'Camo pattern used extensively by the old German\nDefense Force. Effective when underwater.\n':
        '옛 독일 국방군이 널리 쓰던 위장 무늬.\n수중에서 효과적.\n',
    'Camo pattern used extensively in Eastern Europe.\nEffective in the rain.\n':
        '동유럽에서 널리 쓰인 위장 무늬.\n빗속에서 효과적.\n',
    "Striped camo pattern resembling a tiger's coat.\nEffective in wooded and grassy areas as well as\nagainst soil and mud.\n":
        '호랑이 가죽을 닮은 줄무늬 위장.\n숲과 풀밭, 흙과 진흙에서\n효과적.\n',

    # ---- uniforms -----------------------------------------------------------
    'A foul-smelling camo uniform. It smells so bad that\nit attracts flies, but it also makes enemies think\ntwice before coming in for a proximity encounter.\n':
        '악취가 나는 위장복. 냄새가 심해\n파리가 꼬이지만, 적도 가까이\n다가오기를 꺼리게 된다.\n',
    'A grenade pattern camo uniform. Wearing it\nallows you to use grenades limitlessly.\n':
        '수류탄 무늬 위장복. 착용하면\n수류탄을 무제한 사용할 수 있다.\n',
    'An animal skin camo uniform. Wearing it removes\nany hand-shaking while aiming a gun.\n':
        '동물 가죽 위장복. 착용하면 총을\n겨눌 때 손떨림이 사라진다.\n',
    "Fruit pattern camo uniform. Wearing\nit enables you to hear Yoshi's call.\n":
        '과일 무늬 위장복. 착용하면\n요시의 울음소리를 들을 수 있다.\n',
    'Black battle uniform. Effective in the dark.\n':
        '검정 전투복. 어둠 속에서 효과적.\n',
    "Cold War:\nVolgin's camo uniform.\n": '냉전:\n볼긴의 위장복.\n',
    "Volgin's camo uniform. Enemies from the Soviet\nside will hesitate to attack.\n":
        '볼긴의 위장복. 소련 측 적이\n공격을 망설인다.\n',
    "The Fury's camo uniform. Reduces damage from\nflames and explosions by half.\n":
        '퓨리의 위장복. 화염과 폭발 피해를\n절반으로 줄인다.\n',
    "The Pain's camo uniform. Wards off hornets,\nspiders, and leeches. Also allows wearer to tame\nhornets.\n":
        '페인의 위장복. 말벌, 거미, 거머리를\n쫓는다. 말벌을 길들일 수도\n있다.\n',
    'No uniform worn on the upper body. Does not\nprovide much camouflage.\n':
        '상체에 아무것도 입지 않았다.\n위장 효과는 거의 없다.\n',
    'Olive drab. Commonly known as OD.\nA single-color battle uniform for general infantry\nuse. Does not provide much camouflage.\n':
        '올리브 드랩. 흔히 OD라고 한다.\n일반 보병용 단색 전투복.\n위장 효과는 거의 없다.\n',
    "Raikov's Uniform:\nThe uniform Major Raikov was wearing.\n":
        '라이코프 군복:\n라이코프 소령이 입던 군복.\n',
    "The officer's uniform that Raikov was wearing.\n":
        '라이코프가 입던 장교 군복.\n',
    'Scientist Uniform:\nThe uniform scientists wear.\n':
        '연구원 복장:\n연구원이 입는 복장.\n',

    # ---- photo camo ---------------------------------------------------------
    'Create Photo-Camo from a\n128x128 selection.\n': '128x128 선택 영역으로\n포토 카모 생성.\n',
    'Create Photo-Camo from a\n256x256 selection.\n': '256x256 선택 영역으로\n포토 카모 생성.\n',
    'Creating Photo-Camo data\nand extra save data.\n': '포토 카모 데이터와\n추가 세이브 데이터 생성.\n',
    'Photo-Camo not yet created.\n': '포토 카모 미생성.\n',
})

if __name__ == '__main__':
    pb.run_batch('ITEM_WEAPON', T, 'STAGE_ITEM_WEAPON_2026-08-19')
