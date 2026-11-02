# 새봄테크 사내 규정 Q&A 챗봇 (개인 프로젝트)

> 총무 업무 중 반복되는 "규정 문의"를 자동 응대하는 RAG 챗봇입니다.
> **모든 규정은 연습용 가상 회사(주식회사 새봄테크)의 가상 데이터**이며, 실존 기업·법령과 무관합니다.

## 무엇을 하나
- 직원이 자연어로 질문하면 관련 **규정 조항을 찾아 근거와 함께** 보여줍니다.
- 규정에 없는 질문은 **"확인 필요" 또는 "거절" + 문의처 안내**로 처리합니다.
- (선택) 무료 LLM(Gemini 무료 키)을 연결하면 근거 조항으로 답변 문장을 만듭니다.

## 성과 (검증셋 = 개선에 사용하지 않은 처음 보는 질문)
| 항목 | 기준선(v0) | 최종(v4·v5) |
|---|---|---|
| 근거 조항 검색 정답률 (Hit@3, 100문항) | 89% | **95%** |
| 정상 질문 잘못 거절 | - | 6% |
| 규정 밖 질문 처리(거절·확인 필요) | 0% | **75%** |
| "답변" 판정 시 근거 정답률 | - | **97.8%** |

개선 과정 전체(시행착오·결정·점수): [`experiments/IMPROVEMENT_LOG.md`](experiments/IMPROVEMENT_LOG.md)

## 구조
```
chatbot/            앱과 검색 코드 (app.py가 실행 파일)
  app.py            Streamlit 채팅 화면
  pipeline.py       개선 단계(v0~v4) 누적 적용
  search_engine.py  조항 단위 분할 + 키워드(BM25) 검색
  embed_engine.py   임베딩 검색(무료 다국어 모델)
  synonyms.py       v1 동의어 사전 / v2 오타 허용 매칭
  typo_fix.py       v3 질문 오타 보정(Kiwi)
  granular.py       v4 조항 세분화 검색
  scope_guard.py    v5 규정 밖 질문 3단계 응답
  llm_answer.py     (선택) 답변 문장 생성
  evaluate*.py      평가 스크립트
regulations/        가상 규정 9종 (REG-00~08)
eval_*.csv          개발용 평가 질문 (50 / 600)
holdout_questions.csv  검증용 질문 112 (개선에 사용 금지)
oos_dev_questions.csv  개발용 규정 밖 질문 40
experiments/        점수 기록·개선 일지
data_tools/         평가 질문 생성 스크립트
```

## 내 PC에서 실행
```bash
pip install -r chatbot/requirements.txt
streamlit run chatbot/app.py
```
처음 실행 시 임베딩 모델(약 470MB)을 내려받아 1~2분 걸립니다.

## 배포 (Streamlit Community Cloud, 무료)
1. 이 저장소를 GitHub에 올림 (Public)
2. https://share.streamlit.io 에서 GitHub 계정으로 로그인 → **Create app**
3. Repository: 이 저장소 / Branch: `main` / Main file path: `chatbot/app.py`
4. Advanced settings → Python version **3.11**
5. (선택) Secrets에 `GEMINI_API_KEY = "발급받은 키"` 입력
6. Deploy → 생성된 주소를 휴대폰에서 열고 "홈 화면에 추가"

## 한계와 주의
- 가상 규정 전용. 실제 회사 규정은 공개 클라우드에 올리지 말 것(사내 승인 환경에서 운영)
- 무료 호스팅은 12시간 미사용 시 절전 → 다시 깨울 때 1~2분 소요
- 거절 기준값은 "임베딩 + v4" 조합 전용
