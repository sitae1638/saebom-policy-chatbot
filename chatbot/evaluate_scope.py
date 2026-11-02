"""규정 밖 질문 3단계 응답 평가. 사용: python evaluate_scope.py --set dev|holdout
 dev    : 개발셋 정상 588 + 범위 밖 52 (기준 결정용, 문항 확인 가능)
 holdout: 검증셋 정상 100 + 범위 밖 12 (집계만 출력, 단계당 1회)
좋은 결과: 정상 질문의 '거절'이 적고, 범위 밖 질문의 '답변'이 적을 것"""
import argparse, csv, datetime, collections
from pathlib import Path
from pipeline import Pipeline
import scope_guard as G

ap = argparse.ArgumentParser(); ap.add_argument("--set", default="dev"); ap.add_argument("--stage", default="v4")
ap.add_argument("--mode", default="embed"); a = ap.parse_args()
ROOT = Path(__file__).resolve().parent.parent
p = Pipeline(a.mode, a.stage)
if a.set == "dev":
    rows = list(csv.DictReader(open(ROOT / "eval_600.csv", encoding="utf-8-sig")))
    ins = [r["질문"] for r in rows if r["답변가능여부"] == "Y"]
    oos = [r["질문"] for r in rows if r["답변가능여부"] == "N"] + \
          [r["질문"] for r in csv.DictReader(open(ROOT / "oos_dev_questions.csv", encoding="utf-8-sig"))]
else:
    rows = list(csv.DictReader(open(ROOT / "holdout_questions.csv", encoding="utf-8-sig")))
    ins = [r["질문"] for r in rows if r["답변가능여부"] == "Y"]
    oos = [r["질문"] for r in rows if r["답변가능여부"] == "N"]
res = {}
for name, qs in (("정상", ins), ("범위밖", oos)):
    c = collections.Counter(G.decide(p.search(q, 3), a.mode, a.stage)[0] for q in qs)
    res[name] = (c, len(qs))
    print(f"[{a.set}] {name} {len(qs)}개 → 답변 {c['답변']} / 확인필요 {c['확인필요']} / 거절 {c['거절']}")
log = ROOT / "experiments" / "scope_log.csv"
with open(log, "a", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), a.set, a.stage, a.mode,
                "3단계 " + str(G.THRESHOLDS.get((a.mode, a.stage))),
                f"정상: 답변{res['정상'][0]['답변']}/확인{res['정상'][0]['확인필요']}/거절{res['정상'][0]['거절']}", res['정상'][1],
                f"범위밖: 답변{res['범위밖'][0]['답변']}/확인{res['범위밖'][0]['확인필요']}/거절{res['범위밖'][0]['거절']}", res['범위밖'][1]])
