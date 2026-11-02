"""개선 단계를 누적해서 적용하는 검색 파이프라인.
새 개선을 추가할 때: STAGES에 이전 단계 목록 + 새 단계 이름을 넣고, _PRE 또는 search()에 처리 로직을 추가한다.
"""
from search_engine import BM25, load_chunks
import synonyms

STAGES = {
    "v0": [],              # 기준선: 질문 그대로 검색
    "v1": ["synonym"],     # + 동의어 사전 질문 확장
    "v2": ["synonym", "fuzzy"],  # + 사전 트리거를 오타 허용(자모 편집거리)으로 매칭
    "v3": ["typofix", "synonym", "fuzzy"],  # + 질문 오타 보정(Kiwi로 모르는 단어 찾아 규정 용어로 교정)
    "v4": ["typofix", "synonym", "fuzzy", "granular"],  # + 조항 세분화 검색(표 행·항목 단위 조각)
}
LATEST = list(STAGES)[-1]


_engine_cache = {}
def base_engine(mode, chunks=None):
    if mode not in _engine_cache:
        chunks = chunks or load_chunks()
        if mode == "bm25":
            _engine_cache[mode] = BM25(chunks)
        else:
            from embed_engine import EmbedSearch, HybridSearch
            emb = _engine_cache.get("embed") or EmbedSearch(chunks)
            _engine_cache["embed"] = emb
            if mode == "hybrid":
                _engine_cache[mode] = HybridSearch(chunks, emb)
    return _engine_cache[mode]

class Pipeline:
    def __init__(self, mode="hybrid", stage=LATEST):
        self.mode, self.stage, self.steps = mode, stage, STAGES[stage]
        if "granular" in self.steps:
            key = ("granular", mode)
            if key not in _engine_cache:
                from granular import GranularSearch
                _engine_cache[key] = GranularSearch(mode)
            self.engine = _engine_cache[key]
        else:
            self.engine = base_engine(mode)

    def rewrite(self, query):
        if "typofix" in self.steps:
            import typo_fix
            query = typo_fix.fix(query)[0]
        if "synonym" in self.steps:
            query = synonyms.expand(query, fuzzy="fuzzy" in self.steps)
        return query

    def search(self, query, k=3):
        return self.engine.search(self.rewrite(query), k)
