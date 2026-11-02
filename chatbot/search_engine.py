"""규정 조항 단위 chunking + BM25 키워드 검색 (LLM·외부 라이브러리 없음)."""
import math, re
from collections import Counter
from pathlib import Path

REG_DIR = Path(__file__).resolve().parent.parent / "regulations"
HEAD = re.compile(r"^###\s+(.+)$", re.M)
# 질문에 자주 붙는 조사·어미 등 검색에 도움 안 되는 말
STOP = {"어떻게","얼마","얼마나","있나요","되나요","해요","돼요","인가요","이에요","예요","알려줘","알려주세요","우리","회사","그럼","혹시","몇","언제","무엇","뭐"}

def load_chunks(reg_dir=REG_DIR):
    chunks = []
    for p in sorted(Path(reg_dir).glob("*.md")):
        text = p.read_text(encoding="utf-8")
        doc_id = re.search(r"문서ID:\s*(REG-\d+)", text).group(1)
        doc_title = text.splitlines()[0].lstrip("# ").strip()
        parts = HEAD.split(text)  # [앞부분, 제목1, 본문1, 제목2, 본문2 ...]
        for i in range(1, len(parts), 2):
            head, body = parts[i].strip(), parts[i + 1].strip()
            article = head.split("(")[0].split(".")[0].strip()  # 제3조 / 별표 / 개정 이력
            chunks.append({"doc_id": doc_id, "doc_title": doc_title, "article": article,
                           "heading": head, "text": body, "file": p.name})
    return chunks

def tokenize(s):
    s = re.sub(r"[^0-9A-Za-z가-힣]+", " ", s.lower())
    toks = []
    for w in s.split():
        if w in STOP:
            continue
        toks.append(w)
        if len(w) >= 2:  # 한국어 조사 대응: 글자 2-gram 추가
            toks += [w[i:i+2] for i in range(len(w) - 1)]
    return toks

class BM25:
    def __init__(self, chunks, k1=1.5, b=0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        # 제목을 두 번 넣어 제목 일치에 가중치
        self.docs = [Counter(tokenize(c["doc_title"] + " " + c["heading"] + " " + c["heading"] + " " + c["text"])) for c in chunks]
        self.len = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.len) / len(self.len)
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query, k=3):
        q = tokenize(query)
        scored = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in q:
                f = d.get(t, 0)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            scored.append((s, i))
        scored.sort(reverse=True)
        return [(s, self.chunks[i]) for s, i in scored[:k] if s > 0]
