# -*- coding: utf-8 -*-
"""AREA_NAME batch.

Three terminal states, decided from the raw text, not from the scanner's
language column (which marks these rows english because the EN and FR/ES branch
strings sit at structurally identical offsets):

  DONOR_MISCLASSIFIED  the string itself is French or Spanish and has an English
                       counterpart elsewhere in the same list
                       (Egouts/Alcantarillado/Crevasse/Grieta/Pont/Puente/
                        Salle de torture/Tunnel souterrain/Oeste/Ouest/Norte/
                        Noreste/Noroeste/Sudoeste/Sur/Base de/Tunnel de)
  KEEP_ENGLISH         romanized Russian proper noun with nothing translatable
                       ('Rassvet', 'Groznyj Grad B1', 'Rassvet - P1' ...).
                       The codec master already keeps these in Latin --
                       Groznyj 34 vs 그로즈니 6, Bolshaya 5 vs 볼샤야 1,
                       Dremuchij/Zaozyorje/Svyatogornyj/Rokovoj 100% Latin --
                       and the Korean transliteration does not fit anyway
                       (그로즈니 그라드 = 15 B into a 13 B slot).
  TRANSLATED           proper noun kept in Latin, descriptor translated
                       (East 동부 / Sewers 하수도 / Weapons Lab 무기 연구소 ...)
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
    'Base de Bolshaya Past\n', 'Alcantarillado de Groznyj Grad\n',
    'Crevasse de Bolshaya Past\n', 'Egouts de Groznyj Grad\n',
    'Grieta de Bolshaya Past\n', 'Oeste de Zaozyorje\n',
    'Pont ferroviaire de Groznyj Grad\n', 'Puente ferroviario de Groznyj Grad\n',
    'Sur de Bolshaya Past\n', 'Tunnel de Krasnogorje\n',
    'Tunnel souterrain de Groznyj Grad\n', 'Zaozyorje Ouest\n',
    'Noreste de Groznyj Grad\n', 'Noroeste de Groznyj Grad\n',
    'Norte de Lazorevo\n', 'Salle de torture de Groznyj Grad\n',
    'Sudoeste de Groznyj Grad\n',
]

KEEP = [
    'Rassvet\n', 'Rokovoj Bereg\n', 'Groznyj Grad\n', 'Zaozyorje',
    'Groznyj Grad +1\n', 'Groznyj Grad +2\n', 'Groznyj Grad +3\n',
    'Groznyj Grad -1\n', 'Groznyj Grad 1F\n', 'Groznyj Grad 2F\n',
    'Groznyj Grad 3F\n', 'Groznyj Grad B1\n', 'Groznyj Grad P1\n',
    'Groznyj Grad P2\n', 'Groznyj Grad P3\n', 'Groznyj Grad S1\n',
    'Rassvet - P1\n', 'Rassvet - P2\n', 'Rassvet - S1\n',
]

T = {
    'Bolshaya Past Base\n': 'Bolshaya Past 기지\n',
    'Bolshaya Past Crevice\n': 'Bolshaya Past 균열\n',
    'Bolshaya Past South\n': 'Bolshaya Past 남부\n',
    'Dremuchij East\n': 'Dremuchij 동부\n',
    'Dremuchij North\n': 'Dremuchij 북부\n',
    'Dremuchij South\n': 'Dremuchij 남부\n',
    'Dremuchij Swampland\n': 'Dremuchij 습지\n',
    'Groznyj Grad Rail Bridge\n': 'Groznyj Grad 철교\n',
    'Groznyj Grad Rail Bridge North\n': 'Groznyj Grad 철교 북부\n',
    'Groznyj Grad Sewers\n': 'Groznyj Grad 하수도\n',
    'Groznyj Grad Underground Tunnel\n': 'Groznyj Grad 지하 터널\n',
    'Groznyj Grad Northeast\n': 'Groznyj Grad 북동부\n',
    'Groznyj Grad Northwest\n': 'Groznyj Grad 북서부\n',
    'Groznyj Grad Southeast\n': 'Groznyj Grad 남동부\n',
    'Groznyj Grad Southwest\n': 'Groznyj Grad 남서부\n',
    'Groznyj Grad Runway\n': 'Groznyj Grad 활주로\n',
    'Groznyj Grad Runway South\n': 'Groznyj Grad 활주로 남부\n',
    'Groznyj Grad Torture Room\n': 'Groznyj Grad 고문실\n',
    'Groznyj Grad Weapons Lab :\nMain Wing\n': 'Groznyj Grad 무기 연구소 :\n본관\n',
    'Groznyj Grad Weapons Lab :\nMain Wing B1\n': 'Groznyj Grad 무기 연구소 :\n본관 B1\n',
    'Groznyj Grad Weapons Lab :\nEast Wing\n': 'Groznyj Grad 무기 연구소 :\n동관\n',
    'Groznyj Grad Weapons Lab :\nWest Wing\n': 'Groznyj Grad 무기 연구소 :\n서관\n',
    'Groznyj Grad Weapons Lab :\nWest Wing Corridor\n': 'Groznyj Grad 무기 연구소 :\n서관 복도\n',
    'Krasnogorje Mountaintop Ruins : Back\n': 'Krasnogorje 산정 폐허 : 후면\n',
    'Krasnogorje Mountaintop : Behind Ruins\n': 'Krasnogorje 산정 : 폐허 뒤\n',
    'Lazorevo North\n': 'Lazorevo 북부\n',
    'Lazorevo South\n': 'Lazorevo 남부\n',
    'Sokrovenno South\n': 'Sokrovenno 남부\n',
    'Sokrovenno West\n': 'Sokrovenno 서부\n',
    'Svyatogornyj West\n': 'Svyatogornyj 서부\n',
    'Svyatogornyj East 1F\n': 'Svyatogornyj 동부 1F\n',
    'Svyatogornyj East 2F\n': 'Svyatogornyj 동부 2F\n',
    'Svyatogornyj East B1\n': 'Svyatogornyj 동부 B1\n',
    'Zaozyorje East\n': 'Zaozyorje 동부\n',
    'Zaozyorje West\n': 'Zaozyorje 서부\n',
    'Explosion of the Hangar': '격납고 폭발',
    'Groznyj Grad Again': '다시 Groznyj Grad',
    'Infiltrating Groznyj Grad': 'Groznyj Grad 잠입',
    'Reaching the Rail Bridge': '철교 도달',
}

if __name__ == '__main__':
    pb.run_batch('AREA_NAME', T, 'STAGE_AREA_NAME_2026-08-19')
