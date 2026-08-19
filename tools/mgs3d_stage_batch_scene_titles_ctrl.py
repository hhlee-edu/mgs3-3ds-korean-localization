# -*- coding: utf-8 -*-
"""Control-bearing Photo-Camo scene titles in FLORA_FAUNA and OTHER.

The 0x80 0x7C token separates display lines and is reproduced verbatim; only
the ASCII runs between the tokens are translated. Names follow the codec
master: 스네이크, 오셀롯, EVA.
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

FLORA = {
    'Russian Roulette:': '러시안 룰렛:',
    'Snake Misses Shooting': '스네이크 빗맞힘',
    'Time for the Snake': '뱀이 허물을',
    'to Shed His Skin': '벗을 때',
    '(No camo reflected.)': '(위장 미반영)',
    'You Disappoint Me,': '실망이군,',
    'Young Snake...': '애송이 스네이크...',
}

OTHER = {
    'Russian Roulette:': '러시안 룰렛:',
    'Ocelot Loses': '오셀롯 패배',
    "I'm defecting": '나는 소련으로',
    'to the Soviet Union.': '망명한다.',
    'Meeting up with EVA': 'EVA와 합류',
    'in the Mountains': '산속에서',
}

if __name__ == '__main__':
    cb.run_batch('FLORA_FAUNA', FLORA, 'STAGE_FLORA_FAUNA_CTRL_2026-08-19')
    print()
    cb.run_batch('OTHER', OTHER, 'STAGE_OTHER_CTRL_2026-08-19')
