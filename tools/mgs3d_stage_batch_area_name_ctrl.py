# -*- coding: utf-8 -*-
"""AREA_NAME control-bearing row: the two-line Photo-Camo scene label.

The 0x80 0x7C token separates the two display lines. Korean puts the object on
line 1 and the action on line 2, which is the natural order in Korean; both
runs are translated, no token is added, removed or moved.
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
    'Reconnaissance of': '\ud3d0\uacf5\uc7a5',
    'Deserted Factory': '\uc815\ucc30',
}

if __name__ == '__main__':
    cb.run_batch('AREA_NAME', RUNS, 'STAGE_AREA_NAME_CTRL_2026-08-19')
