"""[운영] 자동 재시작 — 배포 앱이 보조 코드 변경을 스스로 반영하게 함.

배경: Streamlit은 app.py는 매번 다시 실행하지만, app.py가 불러 쓰는 보조 코드(llm_answer.py 등)는
      한 번 읽은 뒤 다시 읽지 않는 경우가 있어 GitHub에 올린 수정이 반영되지 않았음(2026-11-02 Gemini 404 사례).

동작 (질문·화면 갱신 때마다)
 1) chatbot 폴더 보조 코드 파일들의 '내용'으로 버전값(해시)을 계산 → 실제로 바뀌었을 때만 아래 실행
 2) 잠금: 동시에 여러 사람이 접속해도 한 번만 실행
 3) 메모리 정리: 기존 검색 엔진(AI 모델 포함)을 먼저 비우고 정리 → 새 모델과 옛 모델이 동시에 메모리에 있지 않게
 4) 의존 순서대로 다시 불러오기 (아래 RELOAD_ORDER)
 이 파일 자체와 app.py, 평가 스크립트는 대상에서 제외 (app.py는 Streamlit이 매번 다시 실행)
"""
import gc, hashlib, importlib, sys, threading
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
RELOAD_ORDER = ["synonyms", "search_engine", "embed_engine", "typo_fix", "granular",
                "pipeline", "scope_guard", "llm_answer", "answer_eval"]   # 앞의 것을 뒤의 것이 불러 씀
_lock = threading.Lock()


def _release_memory():
    """비운 메모리를 운영체제에 돌려줌 (리눅스 전용, 실패해도 무시). 없으면 재로딩마다 메모리 사용량이 계속 늘어남."""
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass
_state = {"version": None, "reloads": 0}


def code_version():
    h = hashlib.md5()
    for name in RELOAD_ORDER:
        f = APP_DIR / f"{name}.py"
        if f.exists():
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


def check_and_reload(clear_caches):
    """코드가 바뀌었으면 clear_caches()로 캐시를 비우고 모듈을 다시 불러옴. 반환: (현재 버전, 이번에 재로딩했는지)"""
    cur = code_version()
    if _state["version"] is None:
        _state["version"] = cur
        return cur, False
    if cur == _state["version"]:
        return cur, False
    with _lock:
        if code_version() == _state["version"]:      # 다른 접속이 이미 처리함
            return _state["version"], False
        clear_caches()
        _release_memory()
        for name in RELOAD_ORDER:
            if name in sys.modules:
                importlib.reload(sys.modules[name])
        _release_memory()
        _state["version"] = code_version()
        _state["reloads"] += 1
        return _state["version"], True
