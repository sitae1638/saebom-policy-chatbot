"""50문항 검색 평가: 정답 근거 조항이 상위 k개 안에 있는가(Hit@k). 사용: python evaluate.py [bm25|embed|hybrid]"""
import csv, sys
from pathlib import Path
from search_engine import BM25, load_chunks

mode = sys.argv[1] if len(sys.argv) > 1 else "bm25"
chunks = load_chunks()
if mode == "bm25":
    engine = BM25(chunks)
else:
    from embed_engine import EmbedSearch, HybridSearch
    engine = EmbedSearch(chunks) if mode == "embed" else HybridSearch(chunks)

ROOT = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(ROOT / "eval_questions.csv", encoding="utf-8-sig")))
K = 3
stat, misses = {}, []
for r in rows:
    gold = {tuple(s.split(" ", 1)) for s in r["근거조항"].split(";")}
    got = [(c["doc_id"], c["article"]) for _, c in engine.search(r["질문"], K)]
    ok = bool(gold & set(got))
    stat.setdefault(r["분류"], [0, 0]); stat[r["분류"]][1] += 1; stat[r["분류"]][0] += ok
    if not ok:
        misses.append((r["id"], r["질문"], sorted(gold), got))
tot = sum(v[0] for v in stat.values()); n = sum(v[1] for v in stat.values())
print(f"[{mode}] Hit@{K}: {tot}/{n} = {tot/n:.0%}")
for k, (a, b) in sorted(stat.items()): print(f"  {k}: {a}/{b}")
print("\n[실패 문항]")
for m in misses: print(m)
