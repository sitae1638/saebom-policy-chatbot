"""[개선 v4] 조항 세분화 검색 — 문서 구조만 이용 (예시 질문 사용 안 함).

문제: 한 조항 안에 여러 내용이 섞여 있으면(예: 출장규정 제4조 표의 국내·해외 4개 행) 질문과 직접 관련된 줄이
      다른 줄에 묻혀 점수가 흐려짐.
방법:
 1) 조항을 작은 조각으로 나눔
    - 표: 행마다 "열이름: 값" 문장으로 바꿈  (예: "구분: 해외, 지역: 미주·유럽, 1박 한도: 250,000원")
    - 번호 항목(1. 2. 3.)과 문단은 각각 한 조각
    - 조항 전체도 하나의 조각으로 유지
 2) 모든 조각 앞에 "문서명 > 조항명"을 붙여 어느 규정의 어떤 조항인지 알 수 있게 함
 3) 질문으로 조각을 검색한 뒤, 같은 조항의 조각 중 가장 높은 점수를 그 조항 점수로 사용해 조항 순위를 만듦
    → 화면·평가에는 기존처럼 '조항' 단위로 결과가 나옴
"""
import re
import numpy as np
from search_engine import BM25, load_chunks

def _table_rows(lines):
    rows = [l for l in lines if l.strip().startswith("|")]
    if len(rows) < 3:
        return []
    cells = lambda l: [c.strip() for c in l.strip().strip("|").split("|")]
    head = cells(rows[0])
    out = []
    for r in rows[2:]:
        vals = cells(r)
        out.append(", ".join(f"{h}: {v}" for h, v in zip(head, vals) if v and v != "-"))
    return out

def split_units(chunk):
    text = chunk["text"]
    lines = text.splitlines()
    units = _table_rows(lines)
    buf = []
    for l in lines:
        s = l.strip()
        if not s or s.startswith("|"):
            if buf: units.append(" ".join(buf)); buf = []
            continue
        if re.match(r"^\d+\.\s", s) and buf:
            units.append(" ".join(buf)); buf = []
        buf.append(s)
    if buf: units.append(" ".join(buf))
    units = [u for u in units if len(u) >= 4]
    prefix = f"{chunk['doc_title']} > {chunk['heading']} > "
    out = [{**chunk, "text": prefix + u, "parent_text": chunk["text"], "whole": False} for u in units]
    out.append({**chunk, "text": prefix + text, "parent_text": chunk["text"], "whole": True})   # 조항 전체
    return out

class GranularSearch:
    """조각 단위로 검색하고 조항 단위로 모아서 돌려줌. mode: bm25 / embed / hybrid"""
    def __init__(self, mode="embed", chunks=None):
        self.mode = mode
        self.chunks = chunks or load_chunks()
        self.units = [u for c in self.chunks for u in split_units(c)]
        self.key = lambda c: (c["doc_id"], c["article"])
        self.parent = {self.key(c): c for c in self.chunks}
        self.bm25 = BM25(self.units) if mode in ("bm25", "hybrid") else None
        if mode in ("embed", "hybrid"):
            from embed_engine import EmbedSearch
            # 조각 텍스트에는 이미 '문서명 > 조항명'이 들어 있음 → 제목 중복 없이 본문만 임베딩
            self.emb = EmbedSearch([{**u, "doc_title": "", "heading": ""} for u in self.units])

    ALPHA = 0.5   # 조항 점수 = 0.5×(가장 높은 조각) + 0.5×(조항 전체). 미리 정한 값, 점수 보고 조정하지 않음

    def _rank(self, scored):
        """조각이 많은 조항이 '최고 조각 점수'에서 유리해지는 쏠림을 줄이려고 조항 전체 점수와 섞음."""
        best, whole = {}, {}
        for s, u in scored:
            k = self.key(u)
            if u.get("whole"):
                whole[k] = s
            if k not in best or s > best[k]:
                best[k] = s
        mix = {k: self.ALPHA * best[k] + (1 - self.ALPHA) * whole.get(k, 0.0) for k in best}
        return sorted(mix.items(), key=lambda kv: -kv[1])

    def _bm25_rank(self, q):
        return self._rank(self.bm25.search(q, len(self.units)))

    def _emb_rank(self, q):
        s = self.emb.scores(q)
        return self._rank([(float(s[i]), self.units[i]) for i in range(len(self.units))])

    def search(self, query, k=3, rrf_k=60):
        if self.mode == "bm25":
            ranked = self._bm25_rank(query)
        elif self.mode == "embed":
            ranked = self._emb_rank(query)
        else:
            fused = {}
            for ranking in (self._bm25_rank(query), self._emb_rank(query)):
                for r, (key, _) in enumerate(ranking):
                    fused[key] = fused.get(key, 0) + 1 / (rrf_k + r + 1)
            ranked = sorted(fused.items(), key=lambda kv: -kv[1])
        return [(score, self.parent[key]) for key, score in ranked[:k]]
