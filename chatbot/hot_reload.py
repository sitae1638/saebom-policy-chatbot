"""[운영] 자동 재시작 — 배포 앱이 보조 코드 변경을 스스로 반영하게 함 (재부팅 불필요).

배경: Streamlit은 app.py는 매번 다시 실행하지만, app.py가 불러 쓰는 보조 코드(llm_answer.py 등)는
      한 번 읽은 뒤 다시 읽지 않는 경우가 있어 GitHub에 올린 수정이 반영되지 않았음(2026-11-02 Gemini 404 사례).

v2 (2026-11-02) — 1차 버전의 빈틈 보완
  - 1차: 대상 목록을 손으로 적어 둠 → 새 파일(answer_eval.py)이 빠짐 / 이 파일 자체는 다시 읽지 않아 목록 수정도 반영 안 됨
  - 2차: 챗봇 폴더의 .py 파일을 직접 훑어 대상 자동 결정, app.py가 매번 이 파일을 다시 읽음,
         모듈마다 '불러올 당시 파일 지문'을 붙여 두고 현재 파일과 비교 → 앱 시작 전부터 남아 있던 옛 코드도 감지

동작 (화면 갱신·질문 때마다)
 1) 불러온 챗봇 모듈들의 파일 지문(해시)이 현재 파일과 다른 게 하나라도 있으면 아래 실행
 2) 잠금: 동시에 여러 사람이 접속해도 한 번만 실행
 3) 메모리 정리: 기존 검색 엔진(AI 모델 포함)을 먼저 비우고 운영체제에 반환 → 옛·새 모델이 동시에 메모리에 있지 않게
 4) 의존 순서대로 다시 불러오기 (ORDER에 없는 새 파일은 맨 뒤)
 대상 제외: app.py(Streamlit이 매번 실행), 이 파일(app.py가 매번 다시 읽음), evaluate*.py(명령줄 평가 도구)
"""
import gc, hashlib, importlib, sys, threading
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ORDER = ["synonyms", "search_engine", "embed_engine", "typo_fix", "granular",
         "pipeline", "scope_guard", "llm_answer", "answer_eval"]   # 앞의 것을 뒤의 것이 불러 씀
SKIP = {"app", "hot_reload"}
# 이 파일을 다시 읽어도 잠금은 하나로 유지되도록 sys에 보관
_lock = sys.__dict__.setdefault("_saebom_reload_lock", threading.Lock())


def _file_hash(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()[:8]


def _local_modules():
    """sys.modules 중 챗봇 폴더의 파일에서 온 모듈 (ORDER 순서, 나머지는 뒤에)."""
    found = {}
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None)
        if not f or name.startswith("__") or name in SKIP or name.startswith("evaluate"):
            continue   # __main__ = Streamlit이 실행 중인 app.py 자체 → 제외 (포함하면 앱이 멈춤, 시험에서 확인)
        try:
            fp = Path(f).resolve()
            if fp.parent == APP_DIR and fp.stem not in SKIP and not fp.stem.startswith("evaluate"):
                found[name] = mod
        except Exception:
            pass
    names = [n for n in ORDER if n in found] + sorted(n for n in found if n not in ORDER)
    return [(n, found[n]) for n in names]


def code_version():
    h = hashlib.md5()
    for f in sorted(APP_DIR.glob("*.py")):
        if f.stem in SKIP or f.stem.startswith("evaluate"):
            continue
        h.update(f.read_bytes())
    return h.hexdigest()[:8]


def _stale(mods):
    return [n for n, m in mods if getattr(m, "_hot_hash", None) != _file_hash(m.__file__)]


def _release_memory():
    """비운 메모리를 운영체제에 돌려줌 (리눅스 전용, 실패해도 무시). 없으면 재로딩마다 메모리 사용량이 계속 늘어남."""
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass


def check_and_reload(clear_caches):
    """코드가 바뀐 모듈이 있으면 clear_caches()로 캐시를 비우고 전부 다시 불러옴.
    반환: (현재 코드 버전, 이번에 재로딩했는지, 확인 시점에 이미 불러와져 있던 모듈 이름들)"""
    mods = _local_modules()
    before = {n for n, _ in mods}
    if not _stale(mods):
        return code_version(), False, before
    with _lock:
        mods = _local_modules()
        if not _stale(mods):                 # 다른 접속이 이미 처리함
            return code_version(), False, before
        clear_caches()
        _release_memory()
        for name, mod in mods:
            importlib.reload(mod)
            mod._hot_hash = _file_hash(mod.__file__)
        _release_memory()
        return code_version(), True, before


def stamp_new(before):
    """이번 실행에서 처음 불러온 모듈(= 최신 파일)에 지문을 붙임 → 다음 실행에서 옛 코드로 오인하지 않게."""
    for name, mod in _local_modules():
        if name not in before and getattr(mod, "_hot_hash", None) is None:
            mod._hot_hash = _file_hash(mod.__file__)
