"""새봄테크 규정 챗봇. 실행: streamlit run chatbot/app.py

화면 모드
 - 사용자 모드(기본): 채팅창 + 안내 + 예시 질문만 표시. 검색 설정은 검증셋 최고 조합(임베딩 + v4)으로 고정
 - 개발자 모드: 주소 뒤에 ?dev=1 을 붙이면 왼쪽에 검색 방식·개선 단계·답변 생성 설정과 점수·판정 사유 표시
답변 생성: Streamlit Secrets(또는 환경변수)에 GEMINI_API_KEY가 있으면 사용자 모드에서 자동으로 gemini 사용
"""
import importlib
import os
import streamlit as st
import hot_reload
importlib.reload(hot_reload)   # 자동 재시작 코드 자체의 수정도 매번 반영 (작은 파일이라 부담 없음)

st.set_page_config(page_title="새봄테크 규정 챗봇", page_icon="📘", layout="centered")


@st.cache_resource(show_spinner="규정 문서를 불러오는 중입니다... (처음이나 코드 수정 직후에는 1~2분 걸릴 수 있어요)")
def get_engine(mode, stage, version):
    from pipeline import Pipeline
    return Pipeline(mode, stage)


# 보조 코드가 바뀌었으면 검색 엔진을 비우고 새 코드로 다시 불러옴 (재부팅 불필요) — hot_reload.py 참고
CODE_VERSION, RELOADED, _before = hot_reload.check_and_reload(get_engine.clear)
from pipeline import STAGES          # 재로딩 뒤에 불러와야 새 코드가 쓰임
from llm_answer import answer
import scope_guard as G
import answer_eval

DEV = st.query_params.get("dev") == "1"
DEFAULT_MODE, DEFAULT_STAGE, DEFAULT_K = "embed", "v4", 3
EXAMPLES = ["야근하면 식대 얼마까지 돼요?", "재택근무 일주일에 며칠 가능해요?", "노트북 잃어버렸어요. 어떻게 해야 하나요?",
            "미국 출장 숙박비 한도는?", "외부 손님 방문 등록은 언제까지?"]


def has_gemini_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            os.environ.setdefault("GEMINI_API_KEY", st.secrets["GEMINI_API_KEY"])
    except Exception:
        pass   # secrets 파일이 없는 환경(내 PC)에서는 넘어감
    return bool(os.environ.get("GEMINI_API_KEY"))


# ---------------- 설정 ----------------
if DEV:
    with st.sidebar:
        st.markdown("**🛠 개발자 모드**")
        mode = st.selectbox("검색 방식", ["embed", "hybrid", "bm25"], help="embed=의미(검증셋 최고점, 기본값), hybrid=둘 다, bm25=키워드")
        stage = st.selectbox("개선 단계", list(STAGES)[::-1], help="v0=기준선, 숫자가 클수록 개선 누적")
        provider = st.selectbox("답변 생성", ["none", "gemini", "ollama"], help="none=조항만 표시 / ollama는 내 PC에서만 동작")
        k = st.slider("근거 조항 수", 1, 5, DEFAULT_K)
        show_debug = st.checkbox("확장된 질문·판정 사유 보기", value=True)
        st.caption(f"코드 버전 {CODE_VERSION}" + (" · 방금 새 코드로 다시 불러옴" if RELOADED else ""))
        with st.expander("📊 답변 평가 (개발용)"):
            eval_set = st.selectbox("평가셋", list(answer_eval.SETS))
            eval_pace = st.slider("질문 간격(초, 무료 한도 보호)", 2, 15, 6)
            run_eval = st.button("평가 실행")
else:
    mode, stage, k, show_debug = DEFAULT_MODE, DEFAULT_STAGE, DEFAULT_K, False
    provider = "gemini" if has_gemini_key() else "none"

engine = get_engine(mode, stage, CODE_VERSION)
hot_reload.stamp_new(_before)   # 엔진이 불러온 모듈(검색·임베딩 등)까지 지문 표시
if "history" not in st.session_state:
    st.session_state.history = []

# ---------------- 머리말 ----------------
# 배포 환경 상단 막대(Fork·GitHub)에 제목이 가리지 않도록 여백 확보, 휴대폰에서 제목 크기 축소
# ---------------- 화면 디자인: 메신저형 · 초록 테마 (2026-11-02) ----------------
# 말풍선은 Streamlit이 메시지에 붙이는 aria-label("Chat message from user/assistant")로 구분 → 업데이트에 비교적 안정적
# 무료 배포 상단의 Fork·GitHub 막대와 하단 로고는 제거 불가
GREEN, GREEN_DARK, GREEN_SOFT, BG = "#2F9E5A", "#23784A", "#EAF6EE", "#F4F8F5"
st.markdown(f"""<style>
.stApp {{ background: {BG}; }}
.block-container {{ padding-top: 4rem; max-width: 760px; }}
h1 {{ color: {GREEN_DARK}; font-size: 2rem !important; }}
@media (max-width: 640px) {{ h1 {{ font-size: 1.6rem !important; }} }}

/* 안내 배너 */
.notice {{ background: {GREEN_SOFT}; border: 1px solid #CFE8D7; color: #24543A; border-radius: 12px;
           padding: 10px 14px; font-size: 0.92rem; margin: 4px 0 18px; }}

/* 공통: 메시지 줄 배경 없애기 */
[data-testid="stChatMessage"] {{ background: transparent !important; padding: 4px 0; gap: 8px; }}

/* 내 질문: 오른쪽 초록 말풍선, 아이콘 숨김 */
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {{ justify-content: flex-end; }}
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) > div:first-child {{ display: none; }}
[aria-label="Chat message from user"] {{
    flex: 0 1 auto !important; max-width: 78%; margin-left: auto !important; margin-right: 0 !important; background: {GREEN}; color: #fff;
    border-radius: 18px 18px 0 18px; padding: 10px 16px; box-shadow: 0 1px 2px rgba(0,0,0,.08);
    position: relative; overflow: visible !important; }}
/* 말풍선 꼬리 (2026-11-02 사용자 요청: 더 길게) — 오른쪽 아래로 14px 튀어나온 삼각형 */
[aria-label="Chat message from user"]::after {{
    content: ""; position: absolute; right: -13px; bottom: 0; width: 16px; height: 20px;
    background: {GREEN}; clip-path: polygon(0 0, 0 100%, 100% 100%); }}
[aria-label="Chat message from user"] p, [aria-label="Chat message from user"] * {{ color: #fff !important; margin: 0; }}

/* 챗봇 답변: 왼쪽 흰 말풍선 */
[aria-label="Chat message from assistant"] {{
    flex: 1 1 auto; max-width: 92%; background: #fff; border: 1px solid #E2ECE5;
    border-radius: 18px 18px 18px 0; padding: 12px 16px; box-shadow: 0 1px 3px rgba(0,0,0,.06);
    position: relative; overflow: visible !important; }}
/* 답변 말풍선 꼬리 — 왼쪽 아래, 테두리색 삼각형 위에 흰 삼각형을 겹쳐 테두리선 유지 */
[aria-label="Chat message from assistant"]::before {{
    content: ""; position: absolute; left: -15px; bottom: -1px; width: 16px; height: 21px;
    background: #E2ECE5; clip-path: polygon(100% 0, 100% 100%, 0 100%); }}
[aria-label="Chat message from assistant"]::after {{
    content: ""; position: absolute; left: -13px; bottom: 0; width: 14px; height: 19px;
    background: #fff; clip-path: polygon(100% 0, 100% 100%, 0 100%); }}
[aria-label="Chat message from assistant"] [data-testid="stExpander"] details {{ border-color: #DDEAE1; border-radius: 10px; }}
[aria-label="Chat message from assistant"] [data-testid="stVerticalBlockBorderWrapper"] {{ border-color: #DDEAE1; }}

/* 예시 질문 버튼: 둥근 칩 */
[data-testid="stButton"] button {{ border-radius: 999px; border: 1px solid #CFE8D7; background: #fff; color: #24543A; }}
[data-testid="stButton"] button:hover {{ border-color: {GREEN}; color: {GREEN_DARK}; background: {GREEN_SOFT}; }}

/* 입력창 */
[data-testid="stChatInput"] > div {{ border-radius: 24px; border: 1px solid #CFE8D7; background: #fff; }}
[data-testid="stBottom"] > div {{ background: {BG}; }}
</style>""", unsafe_allow_html=True)
st.title("📘 새봄테크 규정 챗봇")
st.caption("근무·휴가·경비·출장·비품·구매·시설·보안 규정을 찾아 근거 조항과 함께 알려드립니다.")
st.markdown('<div class="notice">🌱 이 챗봇은 <b>연습용 가상 회사(새봄테크)</b>의 규정으로 만들어졌습니다. 실제 회사 규정이 아닙니다.</div>', unsafe_allow_html=True)


# ---------------- 답변 평가 (개발자 모드) ----------------
if DEV and run_eval:
    if not has_gemini_key():
        st.error("GEMINI_API_KEY가 없어 답변 평가를 할 수 없습니다.")
    else:
        bar = st.progress(0.0, text="답변 평가 중...")
        results = answer_eval.run(eval_set, engine, G.decide, answer, mode, stage, k=k, pace=eval_pace,
                                  progress=lambda i, n: bar.progress(i / n, text=f"답변 평가 중... {i}/{n}"))
        st.session_state.eval = (eval_set, results)
if DEV and "eval" in st.session_state:
    import csv as _csv, io as _io
    name, results = st.session_state.eval
    st.success(f"평가 완료: {name}")
    st.json(answer_eval.summary(results))
    buf = _io.StringIO(); w = _csv.DictWriter(buf, fieldnames=list(results[0])); w.writeheader(); w.writerows(results)
    st.download_button("결과 CSV 내려받기", buf.getvalue().encode("utf-8-sig"),
                       file_name=f"answer_eval_{'base50' if '기본' in name else ('holdout_a' if '앞' in name else 'holdout_b')}_prompt{results[0].get('지시문','')}_{CODE_VERSION}.csv", mime="text/csv")
    with st.expander("문항별 결과 보기"):
        st.dataframe(results)


# ---------------- 답변 표시 ----------------
def render(item):
    text, results, tier, why = item[:4]
    llm_failed = len(item) > 4 and item[4]
    if tier == "거절":
        st.markdown("🙅 " + G.MSG["거절"])
        if DEV and results:
            with st.expander("참고: 가장 가까운 조항 (관련 없을 가능성이 높음)"):
                st.markdown(f"**{results[0][1]['doc_id']} {results[0][1]['heading']}**\n\n{results[0][1]['text']}")
        if DEV:
            st.caption(f"판정: {tier} ({why})")
        return
    if tier == "확인필요":
        st.warning(G.MSG["확인필요"], icon="⚠️")
    if text:
        st.markdown(text)
    elif results and tier == "답변":
        top = results[0][1]
        st.markdown(f"가장 관련 있는 규정은 **{top['doc_title']} {top['heading']}** 입니다.")
    for i, (score, c) in enumerate(results):
        label = f"{c['doc_title']} · {c['heading']}"
        if i == 0 and tier == "답변" and not text:
            with st.container(border=True):
                st.markdown(c["text"])
            continue
        if DEV:
            label += f"  (점수 {score:.2f})"
        title = "근거 조항" if i == 0 else "다른 관련 조항"
        with st.expander(f"{title}: {label}", expanded=False):
            st.markdown(c["text"])
    if llm_failed:
        st.caption("※ 지금은 답변 문장 생성이 잠시 어려워 규정 원문으로 안내드렸습니다.")
    if DEV:
        st.caption(f"판정: {tier} ({why})")


def ask(q):
    """반환: (답변문장 또는 None, 검색결과, 판정, 사유, 답변생성 실패 여부)
    답변 문장 생성(LLM)이 실패하면(무료 한도 초과·네트워크 오류 등) 문장 없이 처리 →
    'LLM을 쓰지 않을 때'와 같은 화면(첫 조항 펼침)에 작은 안내만 덧붙임."""
    import llm_answer
    ctx = engine.search(q, max(k, llm_answer.ANSWER_CONTEXT_K))   # 답변 생성용(5개)
    res = ctx[:k]                                                 # 화면 표시용(3개) — 검색 순위는 동일
    tier, why = G.decide(res, mode, stage)                        # 거절 판정은 1위 점수 기준이라 변화 없음
    text, failed = None, False
    if tier != "거절" and provider != "none":
        try:
            text = answer(q, ctx, provider) or None
            if DEV and provider == "gemini":
                import llm_answer
                why += f" / 답변 모델: {llm_answer.LAST_MODEL}"
        except Exception as e:
            failed = True
            if DEV:
                why += f" / 답변 생성 실패: {type(e).__name__}: {str(e)[:400]}"
    return (text, res, tier, why, failed)


# ---------------- 대화 ----------------
for role, content in st.session_state.history:
    with st.chat_message(role, avatar=("🌱" if role == "assistant" else None)):
        if role == "user":
            st.write(content)
        else:
            render(content)

picked = None
if not st.session_state.history:
    st.markdown("**이런 질문을 해 보세요**")
    cols = st.columns(2)
    for i, ex in enumerate(EXAMPLES):
        if cols[i % 2].button(ex, key=f"ex{i}", use_container_width=True):
            picked = ex

typed = st.chat_input("규정에 대해 질문해 보세요")
q = typed or picked
if q:
    st.session_state.history.append(("user", q))
    with st.chat_message("user"):
        st.write(q)
    with st.chat_message("assistant", avatar="🌱"):
        if DEV and show_debug:
            st.caption("검색에 쓴 질문: " + engine.rewrite(q))
        with st.spinner("규정을 찾는 중..."):
            item = ask(q)
    st.session_state.history.append(("assistant", item))
    st.rerun()   # 다시 그려서 예시 버튼을 없애고 대화 기록으로 답변 표시

if st.session_state.history:
    if st.button("🗑 대화 지우기"):
        st.session_state.history = []
        st.rerun()

st.caption("정확한 안내가 필요하면 경영지원팀(내선 1000, helpdesk@saebom-tech.example)에 문의하세요.")
