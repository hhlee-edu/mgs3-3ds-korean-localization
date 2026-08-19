# -*- coding: utf-8 -*-
"""Field-split Korean for the 47 PERSONAL DATA rows that already have Korean.

The clean English resource is the layout authority: 10 display lines, control
stream 0A x 9 + 00, with line 1 and line 9 empty and lines 2-8 carrying the
seven fields. The shipped Korean collapsed all ten onto one line, so this
re-splits the SAME Korean onto the same field boundaries.

What is preserved
-----------------
Every Korean value is the one already in the master. Wording is not rewritten.

What is restored
----------------
1. Field labels that the one-line form had dropped. The compressed rows wrote
   e.g. `여 28세 USA` with no labels at all, and a few had labels collide
   (`머리:적안:갈색` = HAIR:RED + EYE:BROWN run together, `혈액형:과거 질병:통풍`
   = BLOOD TYPE + PAST ILLNESSES run together, losing the blood type value).
2. Verbatim data values that the one-line form had truncated for space
   (`출생:EXETER` -> `출생지:EXETER,ENG.`). These are source data, not
   translation choices.
3. Labels are made consistent across the screen (암호명 / 성별 / 나이 / 국적 /
   생년월일 / 출생지 / 주소 ...), since the same screen previously used
   암호명·코드명·CODE and 나이·연령 interchangeably.

One correction: gcx 445 / res 7 had `암호명: 서명`. SIGINT is the character's
codename, not the word "signature"; the other five SIGINT rows already use
Sigint / SIGINT, so this row follows them.
"""

HEADER = '개인 데이터'

# (gcx, resource) -> (page, [seven fields])
ROWS = {
    # ---- page 1: CODENAME / SEX / AGE / NATIONALITY / BIRTHDATE / BIRTHPLACE / ADDRESS
    (1480, 9): ('[1/1]', ['암호명:EVA', '성별:여성', '나이:28', '국적:미국',
                          '생년월일:1936년 5월 15일', '출생지:MERIDIEN,ID.', '주소:불명']),
    (15, 12): ('[1/1]', ['암호명:MAJOR TOM', '성별:남성', '나이:55', '국적:영국',
                         '생년월일:1909/8/12', '출생지:EXETER,ENG.', '주소:PORTSMOUTH,NH.']),
    (15, 13): ('[1/1]', ['암호명:MAJOR ZERO', '성별:남성', '나이:55', '국적:영국',
                         '생년월일:8/12/1909', '출생지:EXETER,ENG.', '주소:PORTSMOUTH,NH.']),
    (28, 23): ('[1/1]', ['암호명:PARA-MEDIC', '성별:여성', '나이:28', '국적:미국',
                         '생년월일:6/22/1936', '출생지:BOSTON,MA.', '주소:BOSTON,MA.']),
    (445, 9): ('[1/1]', ['암호명:Sigint', '성별:남성', '나이:24', '국적:미국',
                         '생년월일:1939년 11월 11일', '출생지:NASHVILLE,TN.',
                         '주소:랭글리, 버지니아.']),
    (32, 14): ('[1/1]', ['암호명:THE BOSS', '성별:여성', '나이:불명', '국적:미국',
                         '생년월일:불명', '출생지:불명', '주소:불명']),

    (1480, 7): ('[1/2]', ['암호명:EVA', '성별:여', '나이:28', '국적:미국',
                          '생년월일:1936년 5월 15일', '출생지:MERIDIEN,ID.', '주소:불명']),
    (15, 9): ('[1/2]', ['암호명:MAJOR TOM', '성별:남성', '나이:55', '국적:영국',
                        '생년월일:1909/8/12', '출생지:EXETER,ENG.', '주소:PORTSMOUTH,NH.']),
    (15, 10): ('[1/2]', ['암호명:Major Zero', '성별:남성', '나이:55', '국적:영국',
                         '생년월일:1909년 8월 12일', '출생지:EXETER,ENG.',
                         '주소:포츠머스,NH.']),
    (28, 21): ('[1/2]', ['암호명:PARA-MEDIC', '성별:여성', '나이:28', '국적:미국',
                         '생년월일:1936년 6월 22일', '출생지:Boston, MA.',
                         '주소:보스턴, 매사추세츠.']),
    (445, 7): ('[1/2]', ['암호명:Sigint', '성별:남성', '나이:24', '국적:미국',
                         '생년월일:1939년 11월 11일', '출생지:NASHVILLE,TN.',
                         '주소:랭글리, 버지니아.']),
    (32, 15): ('[1/2]', ['암호명:The Boss', '성별:여', '나이:불명', '국적:미국',
                         '생년월일:불명', '출생지:불명', '주소:불명']),

    (1480, 4): ('[1/3]', ['암호명:EVA', '성별:여', '나이:28', '국적:미국',
                          '생년월일:5/15/1936', '출생지:MERIDIEN,ID.', '주소:불명']),
    (15, 5): ('[1/3]', ['암호명:MAJOR TOM', '성별:남', '나이:55', '국적:영국',
                        '생년월일:8/12/1909', '출생지:EXETER,ENG.', '주소:PORTSMOUTH,NH.']),
    (15, 6): ('[1/3]', ['암호명:MAJOR ZERO', '성별:남성', '나이:55', '국적:영국',
                        '생년월일:1909/8/12', '출생지:EXETER,ENG.', '주소:PORTSMOUTH,NH.']),
    (28, 18): ('[1/3]', ['암호명:Para-Medic', '성별:여성', '나이:28', '국적:미국',
                         '생년월일:1936년 6월 22일', '출생지:BOSTON,MA.',
                         '주소:보스턴, 매사추세츠.']),
    (445, 4): ('[1/3]', ['암호명:SIGINT', '성별:남', '나이:24', '국적:미국',
                         '생년월일:11/11/1939', '출생지:NASHVILLE,TN.', '주소:LANGLEY,VA.']),

    (1480, 0): ('[1/4]', ['암호명:EVA', '성별:여성', '나이:28', '국적:미국',
                          '생년월일:1936년 5월 15일', '출생지:MERIDIEN,ID.', '주소:불명']),
    (15, 0): ('[1/4]', ['암호명:MAJOR TOM', '성별:남성', '나이:55', '국적:영국',
                        '생년월일:1909/8/12', '출생지:EXETER,ENG.', '주소:PORTSMOUTH,NH.']),
    (15, 1): ('[1/4]', ['암호명:MAJOR ZERO', '성별:남', '나이:55', '국적:영국',
                        '생년월일:8/12/1909', '출생지:EXETER,ENG.', '주소:PORTSMOUTH,NH.']),
    (28, 14): ('[1/4]', ['암호명:PARA-MEDIC', '성별:여', '나이:28', '국적:미국',
                         '생년월일:6/22/1936', '출생지:BOSTON,MA.', '주소:BOSTON,MA.']),
    (445, 0): ('[1/4]', ['암호명:Sigint', '성별:남성', '나이:24', '국적:미국',
                         '생년월일:1939년 11월 11일', '출생지:NASHVILLE,TN.',
                         '주소:랭글리, 버지니아.']),

    # ---- page 2: HEIGHT / WEIGHT / HAIR / EYE / SKIN / VOICE / MTN ACTR (or BLOOD TYPE / EYESIGHT)
    (1480, 8): ('[2/2]', ['키:5%10 1/4~', '몸무게:149q', '머리:금발', '눈:BLUE',
                          '피부:WHITE', '음성:SUZETTA MINET', 'MTN 배우:YUMIKO DAIKOKU']),
    (32, 16): ('[2/2]', ['키:5% 10~', '몸무게:불명', '머리:갈색 회색', '눈:파랑',
                         '음성:LORI ALAN', 'MTN 배우:ERIKO HIRATA', '혈액형:불명']),
    (28, 22): ('[2/2]', ['키:5%5 7/8~', '몸무게:TOP SECRET', '머리:RED', '눈:BROWN',
                         '피부:WHITE', '음성:HEATHER HALLEY', 'MTN 배우:ERIKO HIRATA']),
    (445, 8): ('[2/2]', ['키:6%5/8~', '몸무게:171q', '머리:BALD', '눈:BROWN',
                         '피부:BLACK', '음성:JAMES MATHIS', '시력:20/16']),
    (15, 11): ('[2/2]', ['키:6% 5/8~', '몸무게:174q', '머리:회색', '눈:회색 파란색',
                         '피부:흰색', '음성:JIM PIDDOCK', 'MTN 배우:TAKASHI KUBO']),

    (1480, 5): ('[2/3]', ['키:5% 10 1/4~', '몸무게:149q', '머리:금발', '눈:파란색',
                          '피부:백색', '음성:SUZETTA MInET', 'MTN 배우:YUMIKO DAIKOKU']),
    (28, 19): ('[2/3]', ['키:5% 5 7/8~', '몸무게:일급비밀', '머리:빨강', '눈:갈색',
                         '피부:화이트', '음성:헤더 핼리', 'MTN 배우:에리코 히라타']),
    (445, 5): ('[2/3]', ['키:6% 5/8~', '몸무게:171q', '머리:대머리', '눈:갈색',
                         '피부:검은색', '음성:JAMES MATHIS', '시력:20/16']),
    (15, 7): ('[2/3]', ['키:6%5/8~', '몸무게:174q', '머리:GREY', '눈:GREYISH BLUE',
                        '피부:WHITE', '음성:JIM PIDDOCK', 'MTN 배우:TAKASHI KUBO']),

    (1480, 1): ('[2/4]', ['키:5% 10 1/4~', '몸무게:149q', '머리:금발', '눈:파란색',
                          '피부:흰색', '음성:SUZETTA MInET', 'MTN 배우:YUMIKO DAIKOKU']),
    (28, 15): ('[2/4]', ['키:5% 5 7/8~', '몸무게:일급비밀', '머리:빨강', '눈:갈색',
                         '피부:화이트', '음성:헤더 핼리', 'MTN 배우:에리코 히라타']),
    (445, 1): ('[2/4]', ['키:6% 5/8~', '몸무게:171q', '머리:대머리', '눈:갈색',
                         '피부:검은색', '음성:JAMES MATHIS', '시력:20/16']),
    (15, 2): ('[2/4]', ['키:6% 5/8~', '몸무게:174q', '머리:회색', '눈:회색 파란색',
                        '피부:흰색', '음성:JIM PIDDOCK', 'MTN 배우:TAKASHI KUBO']),

    # ---- page 3: BLOOD TYPE / EYESIGHT / PAST ILLNESSES / FAMILY / HOBBY / FOOD
    (445, 6): ('[3/3]', ['혈액형:O', '병력:없음', '가족:부모,SISTER 1', '취미:BASKETBALL',
                         '선호 음식:BUFFALO WINGS', '기피 음식:FISH & CHIPS',
                         '관심 기술:COMPUTER']),
    (15, 8): ('[3/3]', ['시력:20/13', '혈액형:A', '병력:통풍', '가족:부모님,자매',
                        '취미:영화,사냥', '선호 음식:셰퍼드 파이', '기피 음식:햄버거']),
    (1480, 6): ('[3/3]', ['시력:20/16', '혈액형:A', '병력:없음', '가족:부모',
                          '취미:MOTORBIKE', '선호 음식:INSTANT NOODLES',
                          '기피 음식:POTATOS']),
    (28, 20): ('[3/3]', ['시력:20/25', '혈액형:B', '병력:없음', '가족:부모,BROTHERS 2',
                         '취미:MOVIE', '선호 음식:SUSHI', '기피 음식:CRAB']),

    (445, 2): ('[3/4]', ['혈액형:O', '병력:없음', '가족:부모,자매', '취미:농구',
                         '선호 음식:버팔로 윙스', '기피 음식:피쉬 앤 칩스',
                         '관심 기술:컴퓨터']),
    (15, 3): ('[3/4]', ['시력:20/13', '혈액형:A', '병력:통풍', '가족:부모님,자매',
                        '취미:영화,사냥', '선호 음식:셰퍼드 파이', '기피 음식:햄버거']),
    (1480, 2): ('[3/4]', ['시력:20/16', '혈액형:A', '병력:없음', '가족:부모님',
                          '취미:오토바이', '선호 음식:인스턴트 라면', '기피 음식:감자']),
    (28, 16): ('[3/4]', ['시력:20/25', '혈액형:B', '병력:없음', '가족:부모님, 형제 2명',
                         '취미:영화', '선호 음식:스시', '기피 음식:CRAB']),

    # ---- page 4: preferences
    (445, 3): ('[4/4]', ['선호 동물:CAT', '선호 주류:BEER', '선호 UMA:SNOWMAN',
                         '선호 UFO:ADAMSKI', '주요 발명:EZ GUN', '올해 작성한',
                         '시말서:21']),
    (28, 17): ('[4/4]', ['선호 영화:전부', '선호 동물:LITTLE BIRD', '선호 주류:SAKE',
                         '신체 치수:TOP SECRET!', '치료 전문:INJECTION',
                         '선호 마스코트:KEROTAN,GA-KO', '선호 괴수:VENUSIAN']),
    (1480, 3): ('[4/4]', ['선호 영화:안 봄', '선호 동물:DOG', '선호 주류:WINE',
                          '신체 치수:36-23-33', '선호 꽃:ROSE', '선호 보석:EMERALD',
                          '반지 호수:5 1/2']),
    (15, 4): ('[4/4]', ['선호 영화:스파이/전쟁 영화', '선호 동물:말', '선호 주류:위스키',
                        '선호 스포츠:럭비', '선호 차:DIMBULA', '선호 UMA:NESSIE',
                        '좌우명:WHO DARES WINS']),
}


def rendered(key):
    """(gcx, resource) -> parse_rendered source with 0A x 9 + 00."""
    page, fields = ROWS[key]
    assert len(fields) == 7, key
    lines = ['%s %s' % (HEADER, page), ''] + fields + ['']
    assert len(lines) == 10, key
    return '<0A>'.join(lines) + '<00>'
