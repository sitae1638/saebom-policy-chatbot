"""검증용(holdout) 평가 — 개선 단계의 '일반화 성능' 확인용.
원칙: 개별 실패 문항을 보고 사전·규칙을 고치지 않는다. (보면 검증셋이 아니라 또 하나의 학습셋이 됨)
화면에는 집계만 출력. 문항별 결과는 ../experiments/holdout_results/ 에 저장(최종 분석 때만 열람).
사용: python evaluate_holdout.py --stages v0 v1 v2 --modes bm25 embed hybrid
"""
import argparse, csv, collections, datetime
from pathlib import Path
from pipeline import Pipeline, STAGES

ap = argparse.ArgumentParser()
ap.add_argument("--stages", nargs="+", default=[list(STAGES)[-1]])
ap.add_argument("--modes", nargs="+", default=["bm25", "embed", "hybrid"])
ap.add_argument("--k", type=int, default=3)
ap.add_argument("--note", default="")
a = ap.parse_args()
ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "experiments"; (EXP / "holdout_results").mkdir(parents=True, exist_ok=True)
rows = list(csv.DictReader(open(ROOT / "holdout_questions.csv", encoding="utf-8-sig")))
ans = [r for r in rows if r["답변가능여부"] == "Y"]

for stage in a.stages:
    for mode in a.modes:
        p = Pipeline(mode, stage)
        cat, out = collections.Counter(), []
        for r in ans:
            gold = {tuple(s.split(" ", 1)) for s in r["근거조항"].split(";")}
            got = [(c["doc_id"], c["article"]) for _, c in p.search(r["질문"], a.k)]
            ok = bool(gold & set(got)); cat[(r["분류"], ok)] += 1
            out.append({"id": r["id"], "분류": r["분류"], "질문": r["질문"], "성공": int(ok),
                        "상위k": "; ".join(f"{d} {x}" for d, x in got), "정답": r["근거조항"]})
        with open(EXP / "holdout_results" / f"{stage}_{mode}.csv", "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
        tot = sum(v for (c, ok), v in cat.items() if ok)
        per = {c: f"{cat[(c, True)]}/{cat[(c, True)] + cat[(c, False)]}" for c in sorted({c for c, _ in cat})}
        print(f"[{stage}/{mode}] 검증100: {tot}/100 ({tot}%) | " + " | ".join(f"{k}: {v}" for k, v in per.items()))
        log = EXP / "holdout_log.csv"; new = not log.exists()
        with open(log, "a", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            if new: w.writerow(["실행시각", "단계", "검색방식", "k", "검증100", "N새조항77", "R새표현13", "T자연오타10", "메모"])
            w.writerow([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), stage, mode, a.k, tot,
                        cat[("N 새조항", True)], cat[("R 새표현", True)], cat[("T 자연오타", True)], a.note])
