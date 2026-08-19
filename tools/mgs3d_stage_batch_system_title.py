# -*- coding: utf-8 -*-
"""SYSTEM_UI + TITLE_AWARD batches.

Save/load terminology: 세이브 / 로드 / 메모리 카드(PS2) / 포맷. The two tiny
button slots ('SAVE' 4 B, 'Saving...' 10 B) fall back to 저장, which is the
same word in shorter form.

`%dKB` is a runtime format specifier and is reproduced verbatim.

The rank titles (BEAR, FOX, TSUCHINOKO ...) stay in English inside the quotes:
they are the game's award names and the surrounding sentence carries the
meaning ('칭호 "FOX" 획득.').
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

MC = '메모리 카드(PS2)'

SYSTEM = {
    'Lower-back Pain\n': '허리 통증\n',
    'No memory card (PS2) found.\n': MC + ' 없음.\n',
    'Return to previous screen.\n': '이전 화면으로 돌아간다.\n',
    'RETURN TO PREVIOUS SCREEN\n': '이전 화면으로 돌아가기\n',
    'Are you sure you wish to overwrite this\nsave data?\nYes or No\n':
        '이 세이브 데이터를\n덮어쓰시겠습니까?\n예/아니오\n',
    'Cancel load?\n': '로드 취소?\n',
    'Cancel save?\n': '세이브 취소?\n',
    'Continue with the game?\n': '게임 계속하시겠습니까?\n',
    'Create new save data on\nmemory card (PS2)?\nYes or No\n':
        MC + '에\n새 세이브 데이터 생성?\n예/아니오\n',
    'Format failed! Please check memory\ncard (PS2) and try again.\n':
        '포맷 실패! ' + MC + '를\n확인하고 다시 시도하세요.\n',
    'Formatting memory card (PS2).\nDo not remove memory card (PS2),\ncontroller, or reset/switch off the console.\n':
        MC + '를 포맷 중.\n' + MC + ', 컨트롤러를 빼거나\n본체를 리셋/전원을 끄지 마세요.\n',
    'Insufficient free space on memory card\n(PS2). At least %dKB of free space is\nrequired to save data.\n':
        MC + '의 빈 공간이\n부족합니다. 세이브에는 최소 %dKB의\n빈 공간이 필요합니다.\n',
    'Insufficient free space on memory card (PS2).\nAt least %dKB of free space is required to\nsave data. Contiune with the game?\n':
        MC + '의 빈 공간이 부족합니다.\n세이브에는 최소 %dKB의 빈 공간이\n필요합니다. 게임을 계속합니까?\n',
    'Load Successful\n': '로드 완료\n',
    'Load failed! Check memory card (PS2)\nand please try again.\n':
        '로드 실패! ' + MC + '를\n확인하고 다시 시도하세요.\n',
    'Load failed! Insert the memory card\n(PS2) that was used to load the saved\ndata.\n':
        '로드 실패! 세이브 데이터를 불러올 때\n사용한 ' + MC + '를\n넣어주세요.\n',
    'Loading data.\n': '로드 중.\n',
    'Memory card (PS2) check failed! At least\n%dKB of free space is required to save data.\nContinue with the game?\n':
        MC + ' 확인 실패! 최소\n%dKB의 빈 공간이 세이브에 필요합니다.\n게임을 계속합니까?\n',
    'Memory card (PS2) is not formatted.\nFormat memory card (PS2) and save?\n':
        MC + '가 포맷되지 않았습니다.\n포맷하고 세이브할까요?\n',
    'Memory card (PS2) was removed during\nsaving. Re-insert the memory card (PS2).\nCancel overwriting?\n':
        '세이브 중 ' + MC + '가\n제거됐습니다. 다시 넣어주세요.\n덮어쓰기를 취소할까요?\n',
    'No data present on memory card (PS2).\n': MC + '에 데이터 없음.\n',
    'No data present on memory card (PS2).\nContinue with the game?\n':
        MC + '에 데이터 없음.\n게임을 계속합니까?\n',
    'No data present on memory card (PS2).\nContinue without saving?\n':
        MC + '에 데이터 없음.\n세이브하지 않고 계속합니까?\n',
    'No loaded data found. Insert the\nmemory card (PS2) that was used\nto load the saved data.\n':
        '불러온 데이터 없음.\n세이브 데이터를 불러올 때 사용한\n' + MC + '를 넣어주세요.\n',
    'No memory card (PS2) found. At least %dKB\nof free space is required to save data.\nContinue with the game?\n':
        MC + ' 없음. 최소 %dKB의\n빈 공간이 세이브에 필요합니다.\n게임을 계속합니까?\n',
    'No memory card (PS2) found.\nContinue with the game?\n':
        MC + ' 없음.\n게임을 계속합니까?\n',
    'No memory card (PS2) found.\nContinue without saving?\n':
        MC + ' 없음.\n세이브하지 않고 계속합니까?\n',
    'No memory card (PS2) found. Insert\nthe memory card (PS2) that was used\nto load the saved data.\n':
        MC + ' 없음.\n세이브 데이터를 불러올 때 사용한\n' + MC + '를 넣어주세요.\n',
    'Please insert a different\nmemory card (PS2).\n': '다른 ' + MC + '를\n넣어주세요.\n',
    'Return to the main menu?\n': '메인 메뉴로 돌아갈까요?\n',
    'Save Successful\n': '세이브 완료\n',
    'Save failed! Check memory card (PS2)\nand please try again.\n':
        '세이브 실패! ' + MC + '를\n확인하고 다시 시도하세요.\n',
    'Saved data is broken. Insert the\nmemory card (PS2) that was used\nto load the saved data.\n':
        '세이브 데이터 손상.\n세이브 데이터를 불러올 때 사용한\n' + MC + '를 넣어주세요.\n',
    'Saved data that was loaded is not found.\nOverwrite the present saved data on\nmemory card (PS2)?\n':
        '불러온 세이브 데이터를 찾을 수 없습니다.\n' + MC + '의 현재 세이브\n데이터를 덮어쓸까요?\n',
    'Saving data.\nDo not remove memory card (PS2),\ncontroller, or reset/switch off the console.\n':
        '세이브 중.\n' + MC + ', 컨트롤러를 빼거나\n본체를 리셋/전원을 끄지 마세요.\n',
    'Select load location.\n': '로드 위치 선택.\n',
    'Select save location.\n': '세이브 위치 선택.\n',
    'Yes or No\n': '예/아니오\n',
    'LOAD GAME\n': '게임 로드\n',
    'Select First Person View control type.\n': '1인칭 시점 조작 방식 선택.\n',
    'Select difficulty.\n': '난이도 선택.\n',
    'Select language.\n': '언어 선택.\n',
    'Camouflage data on memory card (PS2)\nis broken.\n': MC + '의 위장 데이터가\n손상됐습니다.\n',
    'Equipment\nSelect equipment to place on person.\n': '장비\n소지할 장비 선택.\n',
    'Extra save data created.\n': '추가 세이브 데이터 생성.\n',
    'Loading Camouflage data from memory card\n(PS2) successfully completed.\n':
        MC + '에서 위장 데이터\n불러오기를 완료했습니다.\n',
    'No particular effective environment.\n': '특별히 효과적인 환경은 없다.\n',
    'Reading Camouflage data from memory\ncard (PS2) in MEMORY CARD slot 1.\n':
        'MEMORY CARD 슬롯 1의 메모리\n카드(PS2)에서 위장 데이터를 읽는 중.\n',
    'UNEQUIP SOMETHING, AND THEN SELECT AGAIN.\n': '장비를 해제한 뒤 다시 선택하세요.\n',
    'Formatting save data.\n': '세이브 포맷 중.\n',
    'SAVE': '저장',
    'Save data formatted.\n': '세이브 포맷 완료.\n',
    'Save data is damaged.\nFormatting save data.\n': '세이브 데이터 손상.\n세이브 포맷 중.\n',
    'Saving...\n': '저장 중\n',
    'Saving...\nDo not remove SD Card.\n': '저장 중\nSD 카드를 빼지 마세요.\n',
    "I'm Going to Lure It Back Here.": '여기로 유인해 오겠다.',
}

TITLE = {
    'You got AUSCAM desert pattern camo.': 'AUSCAM 사막 위장 획득.',
    'You got Banana pattern camo.': '바나나 무늬 위장 획득.',
    'You got Brown face paint.': '갈색 페인트 획득.',
    'You got DPM pattern camo.': 'DPM 무늬 위장 획득.',
    'You got Desert Tiger pattern camo.': '데저트 타이거 무늬 위장 획득.',
    'You got Flecktarn pattern camo.': '플렉타른 무늬 위장 획득.',
    'You got Green face paint.': '녹색 페인트 획득.',
    'You got Grenade pattern camo.': '수류탄 무늬 위장 획득.',
    'You got Infinity face paint.': '무한 페인트 획득.',
    'You got Mummy pattern camo.': '미라 무늬 위장 획득.',
    'You got National Flags face|\npaints.': '국기 페이스 페인트|\n획득.',
    'You got Stealth camo.': '스텔스 위장 획득.',
    'You got a Camera.': '카메라 획득.',
    'You got a Patriot.': '패트리어트 획득.',
    'You got a Single Action Army.': '싱글 액션 아미 획득.',
    'You got a Tuxedo.': '턱시도 획득.',
    'You got an EZ GUN.': 'EZ GUN 획득.',
}
for _t in ('BEAR', 'CAT', 'CENTIPEDE', 'CHAMELEON', 'CHICKEN', 'COW', 'CROCODILE',
           'DOBERMAN', 'EAGLE', 'FOX', 'FOXHOUND', 'GIANT PANDA', 'HOUND', 'JAGUAR',
           'LEECH', 'LEOPARD', 'PANTHER', 'PIG', 'PIGEON', 'PUMA', 'SCORPION',
           'SPIDER', 'TARANTULA', 'TORTOISE', 'TSUCHINOKO', 'WHALE', 'YOSHI'):
    TITLE['You obtained the title "%s".' % _t] = '칭호 "%s" 획득.' % _t

if __name__ == '__main__':
    pb.run_batch('SYSTEM_UI', SYSTEM, 'STAGE_SYSTEM_UI_2026-08-19')
    print()
    pb.run_batch('TITLE_AWARD', TITLE, 'STAGE_TITLE_AWARD_2026-08-19')
