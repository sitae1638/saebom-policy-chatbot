"""검색된 조항을 근거로 답변 문장을 만드는 모듈 (무료 옵션 2가지, 표준 라이브러리만 사용).
 - ollama : 내 PC에서 도는 로컬 모델. 완전 무료·오프라인. (https://ollama.com 설치 후 `ollama pull qwen2.5:3b`)
 - gemini : Google AI Studio 무료 키(GEMINI_API_KEY 환경변수). 무료 한도·속도 제한 있음.
            기본 모델 gemini-3.5-flash-lite (무료 등급 제공, 신규 프로젝트 권장 모델 — 2026-11 공식 문서 기준)
            ※ 처음 넣었던 gemini-2.0-flash는 2026-06-01 종료 예정 모델이라 교체
            ※ 무료 등급 입력은 Google 제품 개선에 쓰일 수 있음 → 가상 규정만 사용
 - none   : LLM 없이 조항만 표시(기본값)
"""
import json, os, urllib.request

SYSTEM = (
    "너는 가상 회사 '새봄테크'의 규정 안내 도우미다. 반드시 아래 [근거 조항]에 적힌 내용만 사용해 한국어로 답한다.\n"
    "규칙: 1) 답 마지막에 근거를 (문서ID 제N조) 형식으로 적는다. 2) 근거에 없는 내용은 추측하지 말고 "
    "'규정에서 확인되지 않습니다. 경영지원팀(내선 1000)에 문의하세요.'라고 답한다. "
    "3) 금액 계산이 필요하면 계산식을 보여 준다. 4) 3~5문장 이내로 간결하게."
)

def build_prompt(question, results):
    ctx = "\n\n".join(f"[{c['doc_id']} {c['heading']}]\n{c['text']}" for _, c in results)
    return f"[근거 조항]\n{ctx}\n\n[질문]\n{question}"

def _post(url, payload, headers=None, timeout=120):
    req = urllib.request.Request(url, json.dumps(payload).encode("utf-8"),
                                 {"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def answer(question, results, provider="none", model=None):
    if provider == "none" or not results:
        return None
    prompt = build_prompt(question, results)
    if provider == "ollama":
        out = _post("http://localhost:11434/api/chat", {
            "model": model or "qwen2.5:3b", "stream": False, "options": {"temperature": 0},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]})
        return out["message"]["content"].strip()
    if provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY 환경변수가 없습니다.")
        m = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
        out = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                    {"systemInstruction": {"parts": [{"text": SYSTEM}]},
                     "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                     "generationConfig": {"temperature": 0}},
                    headers={"x-goog-api-key": key})
        parts = out["candidates"][0]["content"]["parts"]
        # 생각(thought) 부분은 빼고 답변 텍스트만 이어 붙임
        return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    raise ValueError(provider)
