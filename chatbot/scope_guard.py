"""[개선 v5] 규정 밖 질문 처리 — 3단계 응답.

  답변      : 점수 ≥ HIGH                      → 근거 조항으로 답변
  확인 필요 : LOW ≤ 점수 < HIGH                → 관련 조항을 보여주되 "정확히 일치하는 규정을 찾지 못함" 안내 + 문의처
  거절      : 점수 < LOW 또는 가장 가까운 조항이 REG-00 제6조(규정에 없는 사항) → 문의처 안내

기준값 정하는 법 (숫자를 보기 전에 정한 규칙, 개발셋만 사용)
  HIGH = 개발셋 정상 질문 점수의 하위 1%  (0.8416)
  LOW  = 개발셋 정상 질문 점수의 최저값   (0.8300) → 정상 질문이 한 번도 내려간 적 없는 점수대만 거절
도입 배경: 단일 기준(HIGH만)은 검증셋에서 정상 질문 10%를 잘못 거절 → 애매한 구간을 '확인 필요'로 분리
임베딩 + v4 조합에서 측정한 값이므로 검색 방식·단계가 바뀌면 다시 측정해야 함
"""
THRESHOLDS = {("embed", "v4"): (0.8300, 0.8416)}   # (LOW, HIGH)
OUT_OF_SCOPE_ARTICLE = ("REG-00", "제6조")
CONTACT = "경영지원팀(내선 1000, helpdesk@saebom-tech.example)"
MSG = {
    "거절": f"규정에서 확인되지 않는 내용입니다. {CONTACT}에 문의해 주세요.",
    "확인필요": f"정확히 일치하는 규정을 찾지 못했습니다. 아래 조항이 관련 있을 수 있으니 확인해 보시고, 정확한 안내는 {CONTACT}에 문의해 주세요.",
}

def decide(results, mode, stage):
    """반환: (단계, 사유). 단계 = '답변' | '확인필요' | '거절'. 기준값이 없는 조합은 항상 '답변'."""
    if not results:
        return "거절", "검색 결과 없음"
    score, top = results[0]
    if (top["doc_id"], top["article"]) == OUT_OF_SCOPE_ARTICLE:
        return "거절", "규정에 없는 사항(REG-00 제6조)에 해당"
    th = THRESHOLDS.get((mode, stage))
    if th is None:
        return "답변", "거절 기준 미설정(임베딩·v4에서만 동작)"
    low, high = th
    if score < low:
        return "거절", f"유사도 {score:.3f} < {low}"
    if score < high:
        return "확인필요", f"유사도 {score:.3f} (애매 구간 {low}~{high})"
    return "답변", f"유사도 {score:.3f}"
