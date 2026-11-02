"""무료 로컬 임베딩 검색 (sentence-transformers, 한국어 지원 다국어 모델).
- 모델은 처음 한 번만 내려받고(약 470MB) 이후 오프라인 동작, API 키·비용 없음.
- E5 모델 규칙: 문서는 'passage: ', 질문은 'query: ' 접두어를 붙인다.
"""
import numpy as np
from search_engine import load_chunks, BM25

MODEL_NAME = "intfloat/multilingual-e5-small"

class EmbedSearch:
    def __init__(self, chunks=None, model_name=MODEL_NAME):
        from sentence_transformers import SentenceTransformer
        self.chunks = chunks or load_chunks()
        self.model = SentenceTransformer(model_name)
        texts = ["passage: " + c["doc_title"] + " " + c["heading"] + "\n" + c["text"] for c in self.chunks]
        self.vecs = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=8)  # 작은 묶음으로 나눠 메모리 최대치 절감

    def scores(self, query):
        q = self.model.encode(["query: " + query], normalize_embeddings=True)[0]
        return self.vecs @ q  # 코사인 유사도

    def search(self, query, k=3):
        s = self.scores(query)
        idx = np.argsort(-s)[:k]
        return [(float(s[i]), self.chunks[i]) for i in idx]

class HybridSearch:
    """BM25 + 임베딩 순위를 RRF(Reciprocal Rank Fusion)로 합침."""
    def __init__(self, chunks=None, embed=None):
        self.chunks = chunks or load_chunks()
        self.bm25 = BM25(self.chunks)
        self.emb = embed or EmbedSearch(self.chunks)

    def search(self, query, k=3, rrf_k=60):
        n = len(self.chunks)
        key = lambda c: (c["doc_id"], c["article"])
        pos = {key(c): i for i, c in enumerate(self.chunks)}
        fused = np.zeros(n)
        for res in (self.bm25.search(query, n), self.emb.search(query, n)):
            for r, (_, c) in enumerate(res):
                fused[pos[key(c)]] += 1 / (rrf_k + r + 1)
        idx = np.argsort(-fused)[:k]
        return [(float(fused[i]), self.chunks[i]) for i in idx]
