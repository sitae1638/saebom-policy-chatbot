"""새봄테크 규정 챗봇 (무료판). 실행: streamlit run app.py
검색: bm25 / embed / hybrid, 답변 생성: none / ollama / gemini (사이드바에서 선택)"""
import streamlit as st
from pipeline import Pipeline, STAGES, LATEST
from llm_answer import answer
import scope_guard as G

st.set_page_config(page_title="새봄테크 규정 챗봇", page_icon="📘")

@st.cache_resource
def get_engine(mode, stage):
    return Pipeline(mode, stage)   # 처음 embed/hybrid 선택 시 모델 다운로드(약 470MB)

st.title("📘 새봄테크 규정 챗봇")
st.caption("가상 회사 규정 기반 연습용 · 근거 조항을 함께 보여줍니다.")

with st.sidebar:
    mode = st.selectbox("검색 방식", ["embed", "hybrid", "bm25"], help="embed=의미(검증셋 최고점, 기본값), hybrid=둘 다, bm25=키워드")
    stage = st.selectbox("개선 단계", list(STAGES)[::-1], help="v0=기준선, 숫자가 클수록 개선 누적")
    show_rw = st.checkbox("확장된 질문·판정 사유 보기", value=False)
    provider = st.selectbox("답변 생성", ["none", "ollama", "gemini"], help="none은 조항만 표시")
    k = st.slider("근거 조항 수", 1, 5, 3)

engine = get_engine(mode, stage)
if "history" not in st.session_state:
    st.session_state.history = []

def render(item):
    text, results, tier = item
    if tier == "거절":
        st.info("🙅 " + G.MSG["거절"])
        if results:
            with st.expander("참고: 가장 가까운 조항 (관련 없을 가능성이 높음)"):
                st.markdown(f"**{results[0][1]['doc_id']} {results[0][1]['heading']}**\n\n{results[0][1]['text']}")
        return
    if tier == "확인필요":
        st.warning("⚠️ " + G.MSG["확인필요"])
    if text:
        st.markdown(text)
    for i, (score, c) in enumerate(results):
        with st.expander(f"근거 {i+1}: {c['doc_id']} {c['doc_title']} · {c['heading']} (점수 {score:.2f})", expanded=(not text and i == 0)):
            st.markdown(c["text"])

for role, content in st.session_state.history:
    with st.chat_message(role):
        if role == "user":
            st.write(content)
        else:
            render(content)

if q := st.chat_input("규정에 대해 질문해 보세요"):
    st.session_state.history.append(("user", q))
    with st.chat_message("user"):
        st.write(q)
    with st.chat_message("assistant"):
        if show_rw:
            st.caption("검색에 쓴 질문: " + engine.rewrite(q))
        res = engine.search(q, k)
        tier, why = G.decide(res, mode, stage)
        if show_rw:
            st.caption(f"판정: {tier} ({why})")
        text = None
        if tier != "거절":
            try:
                with st.spinner("답변 생성 중..."):
                    text = answer(q, res, provider)
            except Exception as e:
                text = f"⚠️ 답변 생성에 실패해 근거 조항만 보여드립니다. ({type(e).__name__}: {e})"
        item = (text, res, tier)
        render(item)
    st.session_state.history.append(("assistant", item))
