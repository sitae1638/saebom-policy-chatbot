# 규정 챗봇 (무료판)

## 실행
```
pip install -r requirements.txt
python evaluate.py bm25      # 키워드 검색 채점
python evaluate.py embed     # 임베딩 검색 채점 (첫 실행 시 모델 약 470MB 다운로드)
python evaluate.py hybrid    # 둘 합친 검색 채점
streamlit run app.py         # 챗봇 화면 (사이드바에서 검색·답변 방식 선택)
```
## 개선 단계 (누적)
- `pipeline.py`의 STAGES에 단계별 적용 개선이 정리됨 (v0 기준선 → v1 동의어 사전 → v2 사전 오타 허용 → v3 질문 오타 보정 → v4 조항 세분화)
- 검증셋 평가: `python evaluate_holdout.py --stages v4` (개별 문항은 보지 말 것)
- 규정 밖 질문 3단계 응답: `scope_guard.py` / 평가 `python evaluate_scope.py --set dev` (기준값은 임베딩·v4 전용)
- 평가: `python evaluate_600.py --stage v1 --note "메모"` → `../experiments/`에 점수·문항별 결과 자동 기록
- 개선 내용과 점수 추이: `../experiments/IMPROVEMENT_LOG.md`
- 화면: 사이드바에서 개선 단계 선택, "확장된 질문 보기"로 사전이 붙인 용어 확인

## 답변 생성 (llm_answer.py)
- none: 조항만 표시(기본) / ollama: 내 PC 로컬 모델(무료) / gemini: 무료 키(GEMINI_API_KEY)
- ollama·gemini는 개발 환경에서 직접 실행해 보지 못했습니다. 본인 PC에서 첫 실행 시 확인하세요.
