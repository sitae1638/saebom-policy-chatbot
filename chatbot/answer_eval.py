"""[평가] 답변 문장 평가 — 배포 앱(키가 있는 서버)에서 개발자 모드로 실행.

자동 채점 기준 (문항별)
  - 숫자 사실 포함률: 정답_핵심에 나오는 숫자+단위(250,000원, 7영업일, 2시간, 80%, 17:00 등)가 답변에 들어 있는 비율
  - 근거 표기: 답변에 정답 근거(예: REG-04 제4조)가 적혀 있는가
  - 처리 단계: 답변 가능한 질문이 '거절'되지 않았는가 / 범위 밖 질문이 '거절' 또는 "확인되지 않습니다"로 처리됐는가
자동 채점은 거친 기준 → 기본 50문항은 사람이(개발 중에는 Claude가) 직접 읽고 '정확/부분/오답'을 판정해 보완
검증셋은 자동 채점만 사용(개별 답변을 읽고 지시문을 맞추지 않기 위해)
"""
import csv, re, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETS = {
    "기본50 (개발셋)": "eval_questions.csv",
    "검증112 (검증셋)": "holdout_questions.csv",
}
UNIT = r"(?:원|영업일|일|시간|개월|년|회|명|%|km|인|대|박스|분|자리)"
NUM_FACT = re.compile(r"\d[\d,]*(?:\.\d+)?\s*" + UNIT + r"|\d{1,2}:\d{2}")


def facts(answer_key):
    out = []
    for m in NUM_FACT.findall(answer_key):
        f = re.sub(r"\s+", "", m)
        if f not in out:
            out.append(f)
    return out


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def score_row(row, text, tier):
    gold_refs = [g.strip() for g in row.get("근거조항", "").split(";") if g.strip()]
    fs = facts(row.get("정답_핵심", ""))
    ans = _norm(text)
    hit = [f for f in fs if f in ans or f.replace(",", "") in ans.replace(",", "")]
    cite = any(_norm(g) in ans for g in gold_refs) if gold_refs else None
    answerable = row.get("답변가능여부", "Y") == "Y"
    if answerable:
        handled = tier != "거절"
    else:
        handled = tier == "거절" or ("확인되지" in (text or ""))
    return {
        "숫자사실수": len(fs), "숫자사실포함": len(hit),
        "숫자포함률": round(len(hit) / len(fs), 2) if fs else None,
        "누락사실": ", ".join(f for f in fs if f not in hit),
        "근거표기": cite, "처리적절": handled,
    }


def load(set_name):
    return list(csv.DictReader(open(ROOT / SETS[set_name], encoding="utf-8-sig")))


def run(set_name, engine, decide, answer, mode, stage, k=3, pace=6.0, progress=None):
    """질문마다 검색→3단계 판정→Gemini 답변→자동 채점. 한도 초과(429)면 기다렸다 최대 3번 재시도."""
    import llm_answer
    rows, results = load(set_name), []
    for i, r in enumerate(rows, 1):
        res = engine.search(r["질문"], k)
        tier, why = decide(res, mode, stage)
        text, err = None, ""
        if tier != "거절":
            for attempt in range(4):
                try:
                    text = answer(r["질문"], res, "gemini")
                    break
                except llm_answer.LLMError as e:
                    err = str(e)[:200]
                    if e.status == 429 and attempt < 3:
                        time.sleep(30 * (attempt + 1)); continue
                    break
                except Exception as e:
                    err = f"{type(e).__name__}: {str(e)[:150]}"; break
            time.sleep(pace)
        else:
            text = "(거절) 규정에서 확인되지 않는 내용입니다."
        sc = score_row(r, text if tier != "거절" else text, tier)
        top = res[0][1] if res else {}
        results.append({"id": r["id"], "분류": r.get("분류", ""), "질문": r["질문"], "정답_핵심": r.get("정답_핵심", ""),
                        "근거조항": r.get("근거조항", ""), "답변가능여부": r.get("답변가능여부", "Y"),
                        "판정": tier, "검색1위": f"{top.get('doc_id','')} {top.get('article','')}",
                        "답변": text or "", "오류": err, "모델": llm_answer.LAST_MODEL or "", **sc})
        if progress:
            progress(i, len(rows))
    return results


def summary(results):
    ans = [r for r in results if r["답변가능여부"] == "Y"]
    oos = [r for r in results if r["답변가능여부"] != "Y"]
    fs = [r for r in ans if r["숫자사실수"]]
    out = {
        "답변가능 문항": len(ans),
        "답변 생성 오류": sum(1 for r in results if r["오류"]),
        "숫자 사실 전부 포함": f"{sum(1 for r in fs if r['숫자사실포함'] == r['숫자사실수'])}/{len(fs)}",
        "숫자 사실 포함률(전체)": f"{sum(r['숫자사실포함'] for r in fs)}/{sum(r['숫자사실수'] for r in fs)}",
        "근거 조항 표기": f"{sum(1 for r in ans if r['근거표기'])}/{len(ans)}",
        "정상 질문 거절됨": sum(1 for r in ans if r["판정"] == "거절"),
    }
    if oos:
        out["범위 밖 적절 처리"] = f"{sum(1 for r in oos if r['처리적절'])}/{len(oos)}"
    return out
