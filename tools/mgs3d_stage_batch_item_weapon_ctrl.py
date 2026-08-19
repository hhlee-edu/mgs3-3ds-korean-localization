# -*- coding: utf-8 -*-
"""ITEM_WEAPON control-bearing rows: Photo-Camo cutscene entries.

These 9 rows carry the 0x80 0x7C line-break token, so they go through the
control-aware path; the token bytes are reproduced verbatim and only the ASCII
runs between them are translated.
"""
import sys
import os
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location(
    'cb', os.path.join(ROOT, 'tools/mgs3d_stage_control_batch.py'))
cb = importlib.util.module_from_spec(_s)
sys.modules['cb'] = cb
_s.loader.exec_module(cb)

RUNS = {
    '(No camo reflected.)': '(위장 미반영)',
    'Commencing Virtuous Mission.': '버추어스 미션 개시.',
    'HALO Jump (mask)': 'HALO 강하 (마스크)',
    "Jailguard Johnny's": '교도관 조니의',
    'Family Talk': '가족 이야기',
    'Meeting up with EVA': 'EVA와 합류',
    'behind the Waterfall 1': '폭포 뒤에서 1',
    'behind the Waterfall 2': '폭포 뒤에서 2',
    'Removing a transmitter': '발신기 제거',
    'Returning to this World': '현세로 귀환',
    'Reuniting with Sokolov': '소콜로프와 재회',
    'Waking out of a Nightmare': '악몽에서 깨어남',
}

if __name__ == '__main__':
    cb.run_batch('ITEM_WEAPON', RUNS, 'STAGE_ITEM_WEAPON_CTRL_2026-08-19')
