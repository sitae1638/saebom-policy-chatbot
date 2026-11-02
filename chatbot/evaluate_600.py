"""단계별 누적 평가. 사용 예:
  python evaluate_600.py --stage v1 --modes bm25 embed hybrid
결과:
  ../experiments/results/<단계>_<방식>.csv   문항별 성공/실패
  ../experiments/score_log.csv               점수 누적 기록(실행할 때마다 한 줄씩 추가)
  화면 출력: 점수 + 직전 단계 대비 새로 맞힌/새로 틀린 문항
"""
import argparse, csv, collections, datetime
from pathlib import Path
from pipeline import Pipeline, STAGES

ap = argparse.ArgumentParser()
ap.add_argument("--stage", default=list(STAGES)[-1])
ap.add_argument("--modes", nargs="+", default=["bm25", "embed", "hybrid"])
ap.add_argument("--k", type=int, default=3)
ap.add_argument("--note", default="")
a = ap.parse_args()

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "experiments"; (EXP / "results").mkdir(parents=True, exist_ok=True)
rows600 = list(csv.DictReader(open(ROOT / "eval_600.csv", encoding="utf-8-sig")))
rows50 = list(csv.DictReader(open(ROOT / "eval_questions.csv", encoding="utf-8-sig")))
stages = list(STAGES); prev = stages[stages.index(a.stage) - 1] if stages.index(a.stage) > 0 else None
pct = lambda x, n: f"{x}/{n} ({x/n:.1%})"

def gold(r): return {tuple(s.split(" ", 1)) for s in r["근거조항"].split(";")}

for mode in a.modes:
    p = Pipeline(mode, a.stage)
    out, grp = [], collections.Counter()
    for r in rows600:
        got = [(c["doc_id"], c["article"]) for _, c in p.search(r["질문"], a.k)]
        ok = bool(gold(r) & set(got))
        grp[(r["그룹"], ok)] += 1
        out.append({"id": r["id"], "그룹": r["그룹"], "원문id": r["원문id"], "변형유형": r["변형유형"], "질문": r["질문"],
                    "확장된질문": p.rewrite(r["질문"]), "성공": int(ok),
                    "상위k": "; ".join(f"{d} {x}" for d, x in got), "정답": r["근거조항"]})
    s50 = sum(bool(gold(r) & {(c["doc_id"], c["article"]) for _, c in p.search(r["질문"], a.k)}) for r in rows50)
    f = EXP / "results" / f"{a.stage}_{mode}.csv"
    with open(f, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    v, t = grp[("변형", True)], grp[("오타", True)]
    print(f"\n=== {a.stage} / {mode} / Hit@{a.k} ===")
    print(f"기본50: {pct(s50,50)} | 변형300: {pct(v,300)} | 오타300: {pct(t,300)} | 합계600: {pct(v+t,600)}")
    if prev and (EXP / "results" / f"{prev}_{mode}.csv").exists():
        old = {r["id"]: r["성공"] for r in csv.DictReader(open(EXP / "results" / f"{prev}_{mode}.csv", encoding="utf-8-sig"))}
        fixed = [r for r in out if old.get(r["id"]) == "0" and r["성공"] == 1]
        broke = [r for r in out if old.get(r["id"]) == "1" and r["성공"] == 0]
        print(f"{prev} 대비: 새로 맞힘 {len(fixed)} / 새로 틀림 {len(broke)}")
        for r in broke: print("   [새로 틀림]", r["id"], r["질문"], "→", r["상위k"])
    log = EXP / "score_log.csv"; new = not log.exists()
    with open(log, "a", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        if new: w.writerow(["실행시각", "단계", "적용개선", "검색방식", "k", "기본50", "변형300", "오타300", "합계600", "메모"])
        w.writerow([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), a.stage, "+".join(STAGES[a.stage]) or "-", mode, a.k,
                    s50, v, t, v + t, a.note])
