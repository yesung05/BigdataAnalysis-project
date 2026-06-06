"""10. AI 챗봇 — 서울 구급 분석 결과 Q&A + Tool Calling (GPT-4o)."""
import json
import math
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
from ai_tools import TOOLS, run_tool, build_analytics_context, SEOUL_DISTRICTS

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

# ── 시스템 프롬프트 구성 ─────────────────────────────────────────────────────
# 1) 역할·원칙 정의
_BASE_PROMPT = """당신은 서울시 구급 데이터를 분석한 데이터 분석 전문가입니다.
사용자의 질문에 분석 인사이트와 실시간 정보를 결합해 구체적인 행동 가이드를 제공합니다.

## 보유 도구

**[분석 데이터 조회]** (전체 CSV 사전 계산값 반환)
- query_district_transfer_rate(district?): 자치구별 뺑뺑이 발생률
- query_station_load_ranking(top_n?): 안전센터 출동 순위
- query_symptom_severity(symptom?): 주증상별 중증도 분포
- query_seasonal_demand(by): 계절·월·시간대별 출동 패턴
- query_weather_correlation(): 기상변수 Pearson 상관
- query_yearly_trend(): 연도별 출동 건수·이송률 추이
- query_transfer_analysis(): 뺑뺑이 거부 이유·추가 이동 거리
- query_er_transfer_correlation(): 응급실수 × 뺑뺑이율 상관분석
- query_dispatch_completion(): 증상별 완료이송율 상위/하위
- list_hospitals_in_district(district): 자치구 응급실 목록

**[위치 기반 추천]**
- recommend_hospitals_nearby(district, symptom?, topk?): 가까운 응급실
- recommend_stations_nearby(district, topk?): 가까운 안전센터

**[E-Gen 실시간]** ← 뺑뺑이 문제의 실시간 해결책
- get_realtime_er_beds(district): 지금 가용 병상·장비 현황
- get_severe_disease_acceptance(district, symptom?): 지금 중증질환 수용 가능 응급실

## 응답 원칙
1. 수치 질문은 반드시 도구를 호출해 정확한 값을 가져와라 (추측 금지).
2. 위치·추천 질문은 recommend 도구를 먼저 사용하라.
3. "지금", "현재", "실시간" 키워드가 있으면 E-Gen 도구를 우선 사용하라.
4. 심각한 증상(흉통·뇌졸중·중증외상)은 실시간 + 추천 도구를 함께 사용하라.
5. 답변은 한국어로, 수치·병원명·전화번호를 명시해 구체적으로 작성하라.
6. 분석 범위 외 질문은 그렇다고 안내하라.
"""

# 2) analytics JSON이 있으면 핵심 수치를 시스템 프롬프트에 직접 포함
@st.cache_data(show_spinner=False)
def _get_system_prompt() -> str:
    ctx = build_analytics_context()
    if ctx:
        return _BASE_PROMPT + "\n\n---\n\n" + ctx
    return _BASE_PROMPT

SYSTEM_PROMPT = _get_system_prompt()

EXAMPLE_QUESTIONS = [
    "뺑뺑이가 심한 자치구 TOP 5는?",
    "지금 강남구에서 받아주는 응급실 있어?",
    "흉통 환자 - 지금 강남구서 받는 병원 추천해줘",
    "계절·월별 구급 출동 패턴을 알려줘",
    "응급실 수가 많으면 뺑뺑이가 줄어들어?",
    "내 위치 근처 가장 가까운 응급실 추천해줘",
]


def _nearest_district(lat: float, lon: float) -> str:
    """위도·경도에서 가장 가까운 서울 자치구 반환."""
    return min(
        SEOUL_DISTRICTS,
        key=lambda d: math.hypot(SEOUL_DISTRICTS[d][0] - lat, SEOUL_DISTRICTS[d][1] - lon),
    )


# ── 세션 초기화 ───────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "pending_prompt" not in st.session_state:
    st.session_state["pending_prompt"] = None
if "user_location" not in st.session_state:
    st.session_state["user_location"] = None  # {"lat": float, "lon": float, "district": str}

# ── 버튼 클릭으로 들어온 입력을 꺼냄 ────────────────────────────────────────
user_input: str | None = st.session_state.pop("pending_prompt", None)

# ── 헤더 ─────────────────────────────────────────────────────────────────────
st.title("🤖 AI 분석 Q&A")
st.caption("서울 구급 데이터 분석 결과를 AI에게 자유롭게 질문하세요. 실시간 응급실 정보도 조회할 수 있습니다.")

# ── 사이드바: 내 위치 감지 ────────────────────────────────────────────────────
with st.sidebar:
    st.header("📍 내 위치")

    loc = st.session_state["user_location"]

    if loc:
        st.success(
            f"**{loc['district']}** 감지됨  \n"
            f"위도 {loc['lat']:.4f} / 경도 {loc['lon']:.4f}"
        )
        if st.button("위치 초기화", key="loc_clear"):
            st.session_state["user_location"] = None
            st.rerun()
    else:
        st.info("아래 버튼을 누르면 브라우저에서 위치 권한을 요청합니다.")
        if st.button("📍 내 위치 감지", key="loc_detect", use_container_width=True):
            st.session_state["_loc_requested"] = True
            st.rerun()

    # JS 실행: 위치 권한 요청 후 결과를 컴포넌트로 반환
    if st.session_state.get("_loc_requested") and not loc:
        try:
            from streamlit_js_eval import get_geolocation
            raw = get_geolocation()
            if raw and raw.get("coords"):
                lat = float(raw["coords"]["latitude"])
                lon = float(raw["coords"]["longitude"])
                district = _nearest_district(lat, lon)
                st.session_state["user_location"] = {"lat": lat, "lon": lon, "district": district}
                st.session_state.pop("_loc_requested", None)
                st.rerun()
        except Exception as e:
            st.warning(f"위치를 가져올 수 없습니다: {e}")
            st.session_state.pop("_loc_requested", None)

    st.markdown("---")
    st.caption("위치 정보는 이 세션에서만 사용되며 외부에 전송되지 않습니다.")

# ── 위치 컨텍스트를 시스템 프롬프트에 주입 ──────────────────────────────────
_loc = st.session_state["user_location"]
if _loc:
    _location_ctx = (
        f"\n\n## 현재 사용자 위치\n"
        f"GPS 좌표: 위도 {_loc['lat']:.4f}, 경도 {_loc['lon']:.4f}\n"
        f"가장 가까운 자치구: **{_loc['district']}**\n"
        f"사용자가 위치 기반 질문을 하면 이 자치구를 기본값으로 사용하라."
    )
    EFFECTIVE_SYSTEM_PROMPT = SYSTEM_PROMPT + _location_ctx
else:
    EFFECTIVE_SYSTEM_PROMPT = SYSTEM_PROMPT

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
    if msg["role"] in ("user", "assistant"):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ── 채팅 입력 (루트 레벨 → 화면 하단 고정) ──────────────────────────────────
if typed := st.chat_input("분석 결과 또는 실시간 응급실 정보를 질문하세요…"):
    user_input = typed

# ── AI 응답 처리 (Tool Calling 루프) ─────────────────────────────────────────
if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        answer = ""
        try:
            # OpenAI API에 전달할 메시지 (tool result 포함 전체 히스토리)
            api_msgs = [{"role": "system", "content": EFFECTIVE_SYSTEM_PROMPT}]
            # tool 메시지는 그대로, user/assistant 메시지만 포함
            for m in st.session_state["messages"]:
                if m["role"] in ("user", "assistant", "tool"):
                    api_msgs.append(m)

            max_rounds = 5  # 무한루프 방지
            for _round in range(max_rounds):
                # 도구 판단 단계 (비스트리밍)
                resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=api_msgs,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=1200,
                )
                choice = resp.choices[0]

                if choice.finish_reason == "tool_calls":
                    # 도구 호출 처리
                    tool_msg = choice.message
                    api_msgs.append(tool_msg)

                    for tc in tool_msg.tool_calls:
                        fn_name = tc.function.name
                        fn_args = json.loads(tc.function.arguments)

                        with st.status(f"🔧 `{fn_name}` 호출 중…", expanded=False) as status:
                            st.write(f"**인자:** `{json.dumps(fn_args, ensure_ascii=False)}`")
                            result = run_tool(fn_name, fn_args)
                            st.write(result)
                            status.update(
                                label=f"✅ `{fn_name}` 완료",
                                state="complete",
                                expanded=False,
                            )

                        api_msgs.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        })
                    continue  # 도구 결과 넣고 다시 요청

                # 도구 호출 없음 → 최종 답변을 스트리밍으로 요청
                stream = client.chat.completions.create(
                    model="gpt-4o",
                    messages=api_msgs,
                    temperature=0.3,
                    max_tokens=1200,
                    stream=True,
                )
                answer = st.write_stream(
                    chunk.choices[0].delta.content or "" for chunk in stream
                )
                break

        except Exception as e:
            answer = f"오류가 발생했습니다: {e}"
            st.error(answer)

    # 대화 이력에는 user/assistant 텍스트만 저장 (tool 메시지는 api_msgs에만)
    if answer:
        st.session_state["messages"].append({"role": "assistant", "content": answer})

if not st.session_state["messages"]:
    st.info("위 예시 질문을 클릭하거나 아래 입력창에 직접 질문하세요.")
