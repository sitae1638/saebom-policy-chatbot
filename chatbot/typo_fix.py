"""[개선 v3] 질문 오타 보정 (무료 한국어 형태소 분석기 Kiwi 사용).

1차 시도(규정 문서 단어만으로 판단)는 '있어?', '알려주세요' 같은 일상어까지 오타로 보고 고쳐서 폐기.
→ 일상어를 아는 한국어 사전이 필요 → Kiwi의 단어 점수로 '모르는 단어(=오타 의심)'만 골라냄.

동작
 1) Kiwi로 질문을 형태소 분석, 명사로 분석됐는데 점수가 매우 낮은(사전에 없는) 단어만 오타 의심
    예) 시간 -7.9 / 아내 -7.9 / 호텔 -9.5 (정상)  vs  싀간 -27 / 탯시 -23 / 즤원 -32 (오타 의심)
 2) 오타 의심 단어를 '규정 용어 목록'(규정 문서의 명사 + 동의어 사전 단어)과 비교
    - 자모 차이 1개, 이웃 글자 맞바꿈, 중복 글자 제거 중 하나로 같아지면 교정 후보
    - 2글자는 초성이 모두 같을 때만 (v2에서 확인한 오탐 방지 규칙)
    - 단어 전체가 안 맞으면 단어 안의 2~4글자 조각도 비교 (야그밥겂 → 야근, 밥값)
 3) 원래 단어는 그대로 두고 교정 단어를 질문 뒤에 덧붙임
"""
import re
from functools import lru_cache
from pathlib import Path
from synonyms import jamo, edit, syl_transposed, cho, RULES

REG_DIR = Path(__file__).resolve().parent.parent / "regulations"
UNKNOWN_SCORE = -18.0   # 이보다 낮으면 '사전에 없는 단어'로 판단 (정상 단어는 대략 -16 이상)
def kiwi():
    """Kiwi 분석기는 코드 재로딩과 무관하게 한 번만 불러와 재사용 (자동 재시작 시 메모리 증가 방지)."""
    import sys
    if getattr(sys, "_saebom_kiwi", None) is None:
        from kiwipiepy import Kiwi
        sys._saebom_kiwi = Kiwi()
    return sys._saebom_kiwi

def _build_vocab():
    vocab = set()
    for p in REG_DIR.glob("*.md"):
        for t in kiwi().tokenize(p.read_text(encoding="utf-8")):
            if t.tag in ("NNG", "NNP") and len(t.form) >= 2 and re.fullmatch(r"[가-힣]+", t.form):
                vocab.add(t.form)
    for canon, trig, _ in RULES:
        for w in re.findall(r"[가-힣]{2,}", canon + " " + " ".join(trig)):
            vocab.add(w)
    return vocab

_vocab = None
def vocab():
    global _vocab
    if _vocab is None:
        _vocab = _build_vocab()
    return _vocab

def _close(a, b):
    if a == b: return False
    if len(a) == 2 and len(b) == 2 and [cho(x) for x in a] != [cho(x) for x in b]:
        return False
    if abs(len(a) - len(b)) > 1: return False
    return edit(jamo(a), jamo(b), 1) <= 1 or syl_transposed(a, b)

@lru_cache(maxsize=4096)
def correct_word(word):
    V = vocab()
    # 중복 글자 제거 (기기본 → 기본)
    for i in range(len(word) - 1):
        if word[i] == word[i + 1] and word[:i] + word[i + 1:] in V:
            return [word[:i] + word[i + 1:]]
    whole = sorted((v for v in V if _close(word, v)), key=lambda v: (abs(len(v) - len(word)), v))
    if whole:
        return whole[:1]
    if len(word) >= 4:   # 조각 비교
        out = []
        for L in (3, 2):
            for i in range(len(word) - L + 1):
                piece = word[i:i + L]
                hit = next((v for v in sorted(V) if len(v) == L and _close(piece, v)), None)
                if hit and hit not in out: out.append(hit)
        return out[:2]
    return []

def suspects(query):
    return [t.form for t in kiwi().tokenize(query)
            if t.tag in ("NNG", "NNP") and t.score < UNKNOWN_SCORE and len(t.form) >= 2
            and re.fullmatch(r"[가-힣]+", t.form) and t.form not in vocab()]

def fix(query):
    adds = []
    for w in suspects(query):
        for c in correct_word(w):
            if c not in adds and c not in query:
                adds.append(c)
    return query + (" " + " ".join(adds) if adds else ""), adds
