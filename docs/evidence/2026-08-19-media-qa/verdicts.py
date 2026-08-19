"""Hand-authored verdicts from the 2026-08-19 movie/demo contextual QA pass.

Every entry below was decided by reading the line inside its record's dialogue,
not by a regex. The extractor (`tools/mgs3d_media_register_qa.py`) produced the
candidates; this file is the judgement on them, kept as data so the proposal CSV
can be regenerated and so a later reviewer can argue with a specific line.

Keys are (media, record, entry) exactly as in translation/10_master/current/*.csv.
The English side of every one of those 2,917 rows was verified byte-identical to
the entry at that position in the clean-tree DAT, so where a pair disagrees it is
the Korean that sits on the wrong line, not the English.
"""

# --- Korean that belongs to a different line entirely -----------------------
# Read against the record's surrounding dialogue. These do not need a register
# decision or a reword: they need the correct Korean line put back.
MISMAPPED = [
    ("demo", 16, 23), ("demo", 19, 39), ("demo", 24, 14), ("demo", 26, 4),
    ("demo", 29, 13), ("demo", 41, 10), ("demo", 46, 5), ("demo", 46, 15),
    ("demo", 47, 7), ("demo", 49, 12), ("demo", 57, 17), ("demo", 59, 31),
    ("demo", 61, 30), ("demo", 62, 9), ("demo", 77, 29), ("demo", 80, 23),
    ("demo", 82, 1), ("demo", 82, 6), ("demo", 83, 11), ("demo", 85, 15),
    ("demo", 87, 0), ("demo", 100, 0), ("demo", 100, 30), ("demo", 101, 24),
    ("demo", 104, 35), ("demo", 106, 4), ("demo", 106, 34), ("demo", 107, 28),
    ("demo", 110, 29), ("demo", 115, 1), ("demo", 116, 0), ("demo", 117, 5),
    ("demo", 117, 10), ("demo", 117, 15), ("demo", 118, 29), ("demo", 119, 20),
    ("demo", 119, 25), ("demo", 122, 2), ("demo", 122, 17), ("demo", 123, 18),
    ("demo", 123, 23), ("demo", 141, 3), ("demo", 141, 23), ("demo", 144, 34),
    ("demo", 146, 2), ("demo", 148, 31), ("demo", 149, 20), ("demo", 154, 4),
    ("demo", 154, 9), ("demo", 156, 14), ("demo", 156, 29), ("demo", 157, 7),
    ("demo", 157, 27), ("demo", 158, 14), ("demo", 159, 29), ("demo", 160, 3),
    ("demo", 172, 3), ("demo", 176, 18), ("demo", 178, 35), ("demo", 179, 3),
    ("demo", 179, 13), ("demo", 180, 8), ("demo", 180, 23), ("demo", 180, 33),
    ("demo", 181, 35), ("demo", 183, 35), ("demo", 184, 3), ("demo", 184, 13),
    ("demo", 185, 8), ("demo", 185, 23), ("demo", 185, 33), ("demo", 186, 14),
    ("demo", 192, 15), ("demo", 193, 15), ("demo", 194, 24), ("demo", 194, 39),
    ("demo", 197, 0), ("demo", 197, 30), ("demo", 202, 14), ("demo", 203, 5),
    ("demo", 208, 26), ("demo", 210, 43), ("demo", 211, 1), ("demo", 225, 5),
    ("demo", 226, 16), ("demo", 228, 3), ("demo", 230, 10), ("demo", 234, 5),
    ("demo", 236, 34), ("demo", 238, 4), ("demo", 238, 9), ("demo", 238, 34),
    ("demo", 239, 1), ("demo", 240, 1), ("demo", 240, 6), ("demo", 240, 21),
    ("demo", 242, 0), ("demo", 243, 5), ("demo", 243, 10), ("demo", 259, 45),
    ("demo", 260, 5), ("demo", 269, 9), ("demo", 270, 5), ("demo", 270, 35),
    ("demo", 296, 0), ("demo", 321, 0), ("demo", 321, 10), ("demo", 322, 27),
    ("demo", 328, 0), ("demo", 328, 15), ("demo", 328, 20), ("demo", 330, 4),
    ("demo", 330, 19), ("demo", 15, 29), ("demo", 125, 0),
    ("movie", 29, 14),
]

# --- register drift, decided against the confirmed speaker policy ------------
# Para-Medic / EVA -> 존댓말;  Zero / Sigint / Snake / The Boss -> 반말;
# Sokolov -> 하오체;  Ocelot and other subordinates addressing Volgin -> 존댓말.
# `korean_new` is a proposal, not an applied edit. Every one of these is
# byte-checked before it can be applied.
REGISTER_FIX = [
    # Snake reporting to Major Zero. The codec pass normalised Snake to 반말
    # across 135 lines; these demo lines are the same speaker in 존댓말.
    ("demo", 6, 4, "Snake", "polite->plain", "소령, 적병 두 명을 발견했다..."),
    ("demo", 7, 5, "Snake", "polite->plain", "소코로프가 잡혀 있다는 폐공장에 도착했다."),
    ("demo", 7, 15, "Snake", "polite->plain", "여기선 소코로프가 안 보인다..."),
    ("demo", 7, 20, "Snake", "polite->plain", "경비가 상당히 삼엄하다..."),
    ("demo", 7, 25, "Snake", "polite->plain", "주변 곳곳에 보초가 배치돼 있다..."),
    # Snake to Sokolov: the rest of both records is 반말, these two are not.
    ("demo", 8, 4, "Snake", "polite->plain", "소코로프로군."),
    ("demo", 9, 0, "Snake", "polite->plain", "2년 전 당신을 구출한 제로 소령의 명령으로 왔다."),
    ("demo", 9, 40, "Snake", "polite->plain", "하지만 이럴 시간이 없다."),
    # Zero answering Snake. Zero is 반말 by the confirmed policy.
    ("demo", 39, 11, "Zero", "polite->plain", "그렇다."),
    # Sokolov speaks 하오체 through these records; these lines slip to 반말.
    ("demo", 11, 24, "Sokolov", "plain->archaic", "날 가둬 두는 데 저렇게 많은 병력은 필요 없소."),
    ("demo", 12, 40, "Sokolov", "plain->archaic", "미국은 정말 무서운 나라요."),
    ("demo", 159, 39, "Sokolov", "plain->archaic", "조국으로 돌아갈 수 없소."),
]

# --- register questions that need a person, not a rule ----------------------
REGISTER_HUMAN = {
    # "...The Pain is dead." answers Volgin's "Has the CIA dog been disposed of
    # yet?". 하오체 is right if The Boss is answering as Volgin's equal and wrong
    # if it is Ocelot reporting to his colonel, and the line carries no vocative
    # either way. The 존댓말 rewrite is also 4 bytes over its fixed slot, so it
    # would need shortening on top of the speaker call.
    ("demo", 74, 12): "speaker ambiguous (The Boss vs Ocelot) and the 존댓말 "
                      "rewrite is 4 bytes over the fixed slot",
}

# --- MT-literal candidates that are actually defects -------------------------
# Read in context, the great majority of the `MT_LITERAL` hits are fine: a
# `그는`/`그녀는` opener is ordinary Korean when the referent has to be marked, and
# the Ocelot epilogue genuinely does talk about The Boss in the third person for
# minutes at a time. These are the ones that are wrong on their own terms.
MT_FIX = [
    ("demo", 319, 21, "two-dot ellipsis", "그녀의 이야기..."),
    ("demo", 320, 5, "missing sentence-final period", "그녀는 진정 영웅이었어."),
    ("demo", 79, 16, "인정받아 받은 repeats 받",
     "사회에 기여한 나의 빛나는 공로로 수여된 것이다."),
    ("demo", 207, 22, "literal rendering leaves the sentence ambiguous",
     "그는 네가 신분을 속이고 있다고 의심해."),
    ("demo", 293, 2, "two-dot ellipsis", "나의 잠은..."),
]

# --- register splits read as correct: two speakers, not one drifting --------
# Recorded so a later pass does not re-open them. The reason is the speaker.
REGISTER_KEEP = {
    "EVA speaking (존댓말 by confirmed policy)": [
        ("demo", 46, 10), ("demo", 47, 27), ("demo", 49, 17), ("demo", 50, 3),
        ("demo", 50, 23), ("demo", 51, 29), ("demo", 54, 14), ("demo", 54, 24),
        ("demo", 55, 37), ("demo", 57, 22), ("demo", 58, 27), ("demo", 61, 10),
        ("demo", 61, 20), ("demo", 100, 5), ("demo", 100, 20), ("demo", 106, 9),
        ("demo", 106, 24), ("demo", 331, 5),
    ],
    "Snake replying inside an EVA/Sokolov scene (반말 is correct)": [
        ("demo", 7, 10), ("demo", 7, 30), ("demo", 12, 15), ("demo", 12, 20),
        ("demo", 61, 15), ("demo", 61, 25), ("demo", 106, 14), ("demo", 106, 19),
        ("demo", 106, 39), ("demo", 159, 4),
    ],
    "subordinate addressing Volgin or The Boss (존댓말 is correct)": [
        ("demo", 25, 14), ("demo", 25, 19), ("demo", 31, 34), ("demo", 32, 25),
        ("demo", 33, 24), ("demo", 118, 9), ("demo", 118, 14), ("demo", 118, 24),
        ("demo", 122, 27), ("demo", 122, 32), ("demo", 124, 0), ("demo", 134, 5),
        ("demo", 134, 10), ("demo", 134, 25), ("demo", 163, 0), ("demo", 163, 5),
        ("demo", 165, 15), ("demo", 170, 20), ("demo", 170, 25), ("demo", 171, 4),
    ],
    "Sokolov 하오체, classifier read it as 존댓말 or 반말 but it is right": [
        ("demo", 10, 11), ("demo", 11, 9), ("demo", 13, 13), ("demo", 20, 19),
        ("demo", 158, 34),
    ],
    "minor NPC reporting to a superior (존댓말 is correct)": [
        ("demo", 40, 16), ("demo", 40, 26),
    ],
}
