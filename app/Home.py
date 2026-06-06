"""메인 홈 페이지 — 분석 동기·흐름·데이터 출처."""
import sys
from pathlib import Path

import streamlit as st

_PROJ_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJ_DIR))

st.set_page_config(
    page_title="서울 구급·응급 인프라 분석",
    page_icon="🚑",
    layout="wide",
)

# ── 타이틀 ────────────────────────────────────────────────────────────────
st.title("🚑 서울 구급·응급 인프라 실태 분석")
st.caption("소방청 구급출동현황 2017–2022 · 서울시 출동현황 2022–2024 · ASOS 기상 관측 2019–2024")

st.divider()

# ── 문제 제기 ──────────────────────────────────────────────────────────────
st.subheader("📌 왜 이 분석인가")
st.markdown("""
서울에서는 하루 평균 **약 1,700건**의 구급 출동이 발생합니다.
2017년 약 54만 건이던 연간 출동 건수는 2022년 약 62만 건으로 **6년간 15% 증가**했습니다.

이 증가의 구조적 배경에는 **인구 고령화**가 있습니다.
서울 65세 이상 고령 인구는 2022년 기준 약 **172만 명(15.8%)** 으로, 고령자는 낙상·심뇌혈관 질환·만성질환 악화로 인해
비고령자 대비 구급 이송 비율이 현저히 높습니다.
고령화가 계속될수록 구급 수요는 더욱 가파르게 증가할 것이며, 현재의 인프라 불균형 문제는 더 심각한 위기로 발전할 수 있습니다.

이 가운데 일부 환자는 첫 병원에서 수용을 거부당해 두 번째, 세 번째 병원을 찾아 헤매야 합니다.
이른바 **"뺑뺑이"(2차 이송)** 문제입니다.
2차 이송은 단순 불편이 아닙니다. **골든타임을 직접 침해**하며, 심정지·뇌졸중 환자에게는 생존율 저하로 이어집니다.

본 분석은 구급 출동 데이터를 통해 뺑뺑이가 **어디서·왜 발생하는지**, 응급 인프라와 어떤 관계가 있는지를 파악하고,
나아가 **실시간 응급실 추천**과 **AI 기반 인사이트 탐색**까지 연결합니다.
""")

st.divider()

# ── 분석 흐름 ──────────────────────────────────────────────────────────────
st.subheader("🗺 분석 흐름")

_PHASES = [
    {
        "label": "현황 파악",
        "color": "#2980b9",
        "steps": [
            ("📊", "1. 데이터 현황", "어떤 데이터를 얼마나 사용했나"),
            ("📈", "2. 출동 트렌드", "수요가 연도별·계절별로 어떻게 변화했나"),
        ],
    },
    {
        "label": "문제 규명",
        "color": "#e74c3c",
        "steps": [
            ("🚨", "3. 뺑뺑이 분석", "어느 구에서·왜 2차 이송이 발생하나"),
            ("🏥", "4. 응급실 상관", "응급실 수가 많으면 뺑뺑이가 줄어드나"),
            ("🔥", "5. 소방서 현황", "출동 부하가 어느 안전센터에 집중됐나"),
        ],
    },
    {
        "label": "요인 탐색",
        "color": "#8e44ad",
        "steps": [
            ("💊", "6. 증상 분석", "어떤 증상이 어떤 중증도로 이어지나"),
            ("🌡️", "7. 날씨 상관", "기온·강수·습도가 출동 건수와 관련 있나"),
        ],
    },
    {
        "label": "실시간 활용",
        "color": "#27ae60",
        "steps": [
            ("🗺️", "8. 지도 시각화", "서울 구급 인프라를 공간적으로 확인"),
            ("🏆", "9. 추천 서비스", "지금 내 위치에서 가장 적합한 응급실은"),
            ("🤖", "10. AI 챗봇",   "분석 결과를 AI에게 자유롭게 질문"),
        ],
    },
]

# 타임라인 헤더 행 (Phase 박스 + 화살표)
arrow = '<div style="display:flex; align-items:center; justify-content:center; font-size:1.6em; color:#bbb; padding-top:12px">→</div>'

header_cols = st.columns([6, 1, 6, 1, 5, 1, 6])
col_indices  = [0, 2, 4, 6]  # Phase 열

for ci, phase in zip(col_indices, _PHASES):
    c   = phase["color"]
    lbl = phase["label"]
    icons = " ".join(s[0] for s in phase["steps"])
    header_cols[ci].markdown(
        f"""<div style="text-align:center; padding:14px 10px;
            background:{c}15; border:2px solid {c}; border-radius:10px;">
            <div style="font-size:1.4em; letter-spacing:2px; margin-bottom:4px">{icons}</div>
            <div style="font-weight:700; color:{c}; font-size:0.95em">{lbl}</div>
        </div>""",
        unsafe_allow_html=True,
    )

for ci in [1, 3, 5]:
    header_cols[ci].markdown(arrow, unsafe_allow_html=True)

st.write("")

# 각 Phase 아래 페이지 목록
detail_cols = st.columns([6, 1, 6, 1, 5, 1, 6])
for ci, phase in zip(col_indices, _PHASES):
    c = phase["color"]
    lines = "".join(
        f'<div style="padding:3px 0; border-bottom:1px solid #f0f0f0; font-size:0.8em">'
        f'<span style="font-size:1em">{icon}</span> '
        f'<strong>{name}</strong><br>'
        f'<span style="color:#888; font-size:0.9em; margin-left:1.6em">{desc}</span></div>'
        for icon, name, desc in phase["steps"]
    )
    detail_cols[ci].markdown(
        f'<div style="border-left:3px solid {c}; padding-left:10px; margin-top:4px">{lines}</div>',
        unsafe_allow_html=True,
    )

st.divider()

# ── 데이터 출처 ────────────────────────────────────────────────────────────
st.subheader("📁 데이터 출처")
st.markdown("""
| 데이터 | 출처 | 기간 | 규모 |
|--------|------|------|------|
| 구급출동현황 | 소방청 공공데이터포털 | 2017–2022 | 약 330만 행 |
| 전국 소방서 좌표 | 소방청 공공데이터포털 | 2024.09 기준 | 1,216개소 |
| 구급상황관리현황 | 소방청 공공데이터포털 | 2019–2023 | 약 730만 행 |
| 서울시 구급출동현황 | 서울 열린데이터광장 | 2022–2024 | 월별 집계 Excel |
| 서울시 응급실 위치 정보 | 서울 열린데이터광장 | 현재 | 76개소 |
| ASOS 서울(108) 시간별 관측 | 기상자료개방포털 | 2019–2024 | 시간별 기온·강수·풍속·습도 |
| NEMC Mediboard 실시간 응급실 | 중앙응급의료센터 | 실시간 | 서울 51개소 |
""")

# ── 사이드바 ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🚑 서울 구급 분석")
    st.markdown("""
**분석 목적**
서울 구급 수요 증가와 2차 이송(뺑뺑이) 문제의 실태 파악 및 응급 인프라 개선 방향 도출

---
**데이터 출처**
소방청 공공데이터포털
서울 열린데이터광장
기상자료개방포털
중앙응급의료센터
""")
