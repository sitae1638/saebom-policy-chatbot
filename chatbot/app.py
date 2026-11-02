"""새봄테크 규정 챗봇. 실행: streamlit run chatbot/app.py

화면 모드
 - 사용자 모드(기본): 채팅창 + 안내 + 예시 질문만 표시. 검색 설정은 검증셋 최고 조합(임베딩 + v4)으로 고정
 - 개발자 모드: 주소 뒤에 ?dev=1 을 붙이면 왼쪽에 검색 방식·개선 단계·답변 생성 설정과 점수·판정 사유 표시
답변 생성: Streamlit Secrets(또는 환경변수)에 GEMINI_API_KEY가 있으면 사용자 모드에서 자동으로 gemini 사용
"""
import os
import streamlit as st
from pipeline import Pipeline, STAGES
from llm_answer import answer
import scope_guard as G

st.set_page_config(page_title="새봄테크 규정 챗봇", page_icon="📘", layout="centered")

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


@st.cache_resource(show_spinner="규정 문서를 불러오는 중입니다... (처음 한 번만 1~2분 걸릴 수 있어요)")
def get_engine(mode, stage):
    return Pipeline(mode, stage)


# ---------------- 설정 ----------------
if DEV:
    with st.sidebar:
        st.markdown("**🛠 개발자 모드**")
        mode = st.selectbox("검색 방식", ["embed", "hybrid", "bm25"], help="embed=의미(검증셋 최고점, 기본값), hybrid=둘 다, bm25=키워드")
        stage = st.selectbox("개선 단계", list(STAGES)[::-1], help="v0=기준선, 숫자가 클수록 개선 누적")
        provider = st.selectbox("답변 생성", ["none", "gemini", "ollama"], help="none=조항만 표시 / ollama는 내 PC에서만 동작")
        k = st.slider("근거 조항 수", 1, 5, DEFAULT_K)
        show_debug = st.checkbox("확장된 질문·판정 사유 보기", value=True)
else:
    mode, stage, k, show_debug = DEFAULT_MODE, DEFAULT_STAGE, DEFAULT_K, False
    provider = "gemini" if has_gemini_key() else "none"

engine = get_engine(mode, stage)
if "history" not in st.session_state:
    st.session_state.history = []

# ---------------- 머리말 ----------------
# 배포 환경 상단 막대(Fork·GitHub)에 제목이 가리지 않도록 여백 확보, 휴대폰에서 제목 크기 축소
st.markdown("""<style>
.block-container {padding-top: 4rem;}
@media (max-width: 640px) { h1 {font-size: 1.7rem !important;} }
</style>""", unsafe_allow_html=True)
st.title("📘 새봄테크 규정 챗봇")
st.caption("근무·휴가·경비·출장·비품·구매·시설·보안 규정을 찾아 근거 조항과 함께 알려드립니다.")
st.info("이 챗봇은 **연습용 가상 회사(새봄테크)** 의 규정으로 만들어졌습니다. 실제 회사 규정이 아닙니다.", icon="ℹ️")


# ---------------- 답변 표시 ----------------
def render(item):
    text, results, tier, why = item
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
    if DEV:
        st.caption(f"판정: {tier} ({why})")


def ask(q):
    res = engine.search(q, k)
    tier, why = G.decide(res, mode, stage)
    text = None
    if tier != "거절" and provider != "none":
        try:
            text = answer(q, res, provider)
        except Exception as e:
            text = "⚠️ 답변 문장을 만들지 못해 근거 조항만 보여드립니다." + (f" ({type(e).__name__}: {e})" if DEV else "")
    return (text, res, tier, why)


# ---------------- 대화 ----------------
for role, content in st.session_state.history:
    with st.chat_message(role):
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
    with st.chat_message("assistant"):
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
