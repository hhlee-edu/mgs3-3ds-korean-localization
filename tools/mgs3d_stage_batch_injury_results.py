# -*- coding: utf-8 -*-
"""INJURY + RESULTS + STATUS_MESSAGE batches.

Wound labels are medical terms kept short because the slots are tiny (4-16 B):
타박상 / 총상 / 자상 / 골절 / 화상 / 염좌 / 위염 / 전기 화상.

Four labels have no fitting Korean and are left for the batch runner to report
as NOT_IN_BATCH so they can be escalated to HUMAN:
  'Cut\n' (4 B), 'CUT\n' (4 B), 'Cut:\n' (5 B) -- 열상/상처/베임 are all 2
  syllables = 4 B and leave no room for the line break; and 'LEECH' (5 B),
  where 거머리 is 6 B and no 2-syllable Korean carries "leech".
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

INJURY = {
    'Blow Sustained\n': '타박상\n',
    'Gunshot Wound\n': '총상\n',
    'Gunshot Wound:\n': '총상:\n',
    'GUNSHOT WOUND\n': '총상\n',
    'Electrical Burn\n': '전기 화상\n',
    'Broken Nail\n': '손톱 파손\n',
    'Burn\n': '화상\n',
    'BURN\n': '화상\n',
    'Burn:\n': '화상:\n',
    'Gastritis\n': '위염\n',
    'Sprain\n': '염좌\n',
    'Finger Sprain\n': '손가락 염좌\n',
    'Stab Wound\n': '자상\n',
    'BROKEN BONE\n': '골절\n',
    'Broken Bone:\n': '골절:\n',
    'Fracture :\n': '골절 :\n',
    'No Wound:\n': '없음:\n',
    'Data on memory card (PS2) is broken.\n': '메모리 카드(PS2) 데이터가 손상.\n',
    'Poison Dart Frog\nCaused food poisoning.\n': '독화살개구리\n식중독에 걸렸다.\n',
    'Small transmitter\nfound buried in\nwound.\n': '상처 속에서\n소형 발신기를\n발견했다.\n',
    'Suffering from a\nbullet bee wound.\n': '총알벌에\n쏘였다.\n',
    'Suffering from a\ncrossbow bolt\nwound.\n': '석궁 화살에\n맞았다.\n',
    'Suffering from a\ndeep cut.\n': '깊은 상처를\n입었다.\n',
    'Suffering from a\ngunshot wound.\n': '총상을\n입었다.\n',
}

RESULTS = {
    'TIMES': '횟수',
    'CONTINUES': '컨티뉴',
    'DATA > TOTAL': '데이터>총계',
    'MODE SPECIAL\n': '특수 모드\n',
    'PLAY TIME': '경과 시간',
    'SPECIAL ITEMS': '특수 아이템',
    'TOTAL DAMAGE TAKEN': '받은 총 피해량',
}

STATUS = {
    'Virtuous Mission completed.\n': '버추어스 미션 완료.\n',
}

if __name__ == '__main__':
    pb.run_batch('INJURY', INJURY, 'STAGE_INJURY_2026-08-19')
    print()
    pb.run_batch('RESULTS', RESULTS, 'STAGE_RESULTS_2026-08-19')
    print()
    pb.run_batch('STATUS_MESSAGE', STATUS, 'STAGE_STATUS_2026-08-19')
