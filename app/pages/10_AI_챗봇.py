"""10. AI 챗봇 — 서울 구급 분석 결과 Q&A (GPT-4o)."""
import os
import sys
from pathlib import Path

import streamlit as st

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR = _PAGES_DIR.parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from dotenv import load_dotenv
from src.config import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env", override=False)

st.set_page_config(page_title="AI 챗봇", layout="wide")

# ── API Key / OpenAI 클라이언트 초기화 ──────────────────────────────────────
api_key = os.environ.get("OPENAI_API_KEY", "")
if not api_key:
    st.warning(
        "OpenAI API 키가 설정되지 않았습니다.  \n"
        "프로젝트 루트의 `.env` 파일에 `OPENAI_API_KEY=sk-...` 를 추가하세요."
    )
    st.stop()

try:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
except ImportError:
    st.error("`openai` 패키지 미설치 — `pip install openai`를 실행하세요.")
    st.stop()

# ── 시스템 프롬프트 ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """당신은 서울시 구급 데이터를 분석한 데이터 분석 전문가입니다.
아래의 핵심 분석 결과를 바탕으로 사용자의 질문에 데이터 근거를 들어 명확하게 답변하세요.
답변은 한국어로, 간결하고 이해하기 쉽게 작성하세요.

## 핵심 분석 결과

### 출동 트렌드
- 서울 2022년 구급 출동 약 62만 건 (6년 최고)
- 2020년 약 48만 건으로 COVID-19 영향으로 감소 후 반등
- 7–8월 여름철 피크(3,688–3,781건/일), 2월 최저(2,660–2,700건/일)

### 2차 이송(뺑뺑이) 문제
- 2019년 최저 0.11% → 2021년 최고 0.26%로 급증
- 자치구 격차: 서대문구 0.42% vs 강동구 0.04% (10배 차이)
- 거부 이유: 진료불가(72건) > 응급실포화(65건) > 병상부족(15건)
- 추가 이동 거리 중앙값 2.0km, 평균 3.4km (최대 25km 사례 있음)

### 응급실 접근성
- 서울 76개 응급실: 권역응급의료센터 8개, 지역응급의료센터 19개, 지역응급의료기관 49개
- 자치구별 응급실 수와 2차 이송률 간 Pearson 상관계수 약 -0.3 수준
- 응급실이 많을수록 2차 이송률이 낮아지는 경향 있으나 강한 인과관계는 아님

### 소방 안전센터 부하
- 역삼119안전센터 1위(2,055건), 상위-하위 약 2.1배 격차
- 강남·노원·송파 지역 안전센터에 출동 집중

### 환자 특성
- 질병외(사고·외상) 50.3% vs 질병 47.1% (거의 절반씩)
- 저혈당 응급 92.7%, 의식기능저하 응급 81.8%, 흉통 응급 77.8%
- 호흡정지: 긴급 54.0% + 지연사망 27.5% (가장 위험한 증상군)

### 날씨와 구급 출동
- 기온만 유의미한 상관관계(r=0.267, p=0.012)
- 강수량 r=0.128(통계적으로 비유의)
- 기온 변수만으로 출동 건수 변동의 약 7% 설명

### 119 신고 유형 (2011–2023)
- 구급 신고가 전체 유형 중 압도적으로 많고 지속 증가 추세
- 오접속(잘못 연결된 전화)이 장난전화보다 훨씬 많음

### 추천 서비스
- Haversine 거리 기반 소방 안전센터 TOP-3 추천
- 응급의료기관 분류 가중치 적용: 권역(×0.70) > 지역센터(×0.85) > 지역기관(×1.00)

위 정보에 없는 질문은 "해당 데이터는 분석 범위에 포함되지 않았습니다"라고 안내하세요.
"""

EXAMPLE_QUESTIONS = [
    "2차 이송이 가장 많이 발생하는 자치구는?",
    "뺑뺑이 문제의 주요 원인은?",
    "가장 위험한 증상은 무엇인가요?",
    "출동 부하가 가장 높은 안전센터는?",
    "날씨가 구급 출동에 얼마나 영향을 미치나요?",
]

# ── 세션 초기화 ───────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "pending_prompt" not in st.session_state:
    st.session_state["pending_prompt"] = None

# ── 버튼 클릭으로 들어온 입력을 꺼냄 (렌더링 전에 처리) ─────────────────────
user_input: str | None = st.session_state.pop("pending_prompt", None)

# ── 헤더 ─────────────────────────────────────────────────────────────────────
st.title("🤖 AI 분석 Q&A")
st.caption("서울 구급 데이터 분석 결과를 AI에게 자유롭게 질문하세요.")

# ── 예시 질문 버튼 ────────────────────────────────────────────────────────────
with st.container():
    cols = st.columns(len(EXAMPLE_QUESTIONS) + 1)
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        if cols[i].button(q, key=f"eq_{i}"):
            st.session_state["pending_prompt"] = q
            st.rerun()
    if cols[-1].button("🗑️ 대화 초기화", key="clear"):
        st.session_state["messages"] = []
        st.session_state["pending_prompt"] = None
        st.rerun()

st.divider()

# ── 대화 이력 표시 ────────────────────────────────────────────────────────────
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── 채팅 입력 (루트 레벨 → 화면 하단 고정) ──────────────────────────────────
if typed := st.chat_input("분석 결과에 대해 질문하세요…"):
    user_input = typed

# ── AI 응답 처리 ──────────────────────────────────────────────────────────────
if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        try:
            stream = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *st.session_state["messages"],
                ],
                temperature=0.3,
                max_tokens=800,
                stream=True,
            )
            answer = st.write_stream(
                chunk.choices[0].delta.content or "" for chunk in stream
            )
        except Exception as e:
            answer = f"오류가 발생했습니다: {e}"
            st.error(answer)

    st.session_state["messages"].append({"role": "assistant", "content": answer})

if not st.session_state["messages"]:
    st.info("위 예시 질문을 클릭하거나 아래 입력창에 직접 질문하세요.")
