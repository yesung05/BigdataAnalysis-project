"""메인 홈 페이지 — 프로젝트 KPI 요약."""
import sys
from pathlib import Path

import streamlit as st

_PROJ_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJ_DIR))

st.set_page_config(
    page_title="소방청 구급 출동 데이터 분석",
    page_icon="🚑",
    layout="wide",
)

st.title("🚑 소방청 구급 출동 데이터 분석")
st.caption("데이터 범위: 구급출동현황 2017–2022 · 서울시 출동현황 2022–2024")

st.divider()

c1, c2, c3, c4 = st.columns(4)
c1.metric("전체 출동 건수", "3,291,299건", help="구급출동현황 2017–2022 파일 행수 합계")
c2.metric("2차 이송률 (뺑뺑이)", "0.19%", help="샘플 120,000건 기준 TRANS2_RSN 기재 비율")
c3.metric("분석 소방서·안전센터", "1,216개", help="소방청 전국 소방서 좌표 데이터 기준")
c4.metric("분석 기간", "2017 – 2024", help="구급출동 6개년 + 서울 Excel 3개년")

st.divider()

st.subheader("페이지 안내")
st.markdown("""
| 페이지 | 내용 |
|--------|------|
| **1. 데이터 현황** | 4개 데이터셋 기초통계 — 행수, 컬럼, 분포 |
| **2. 출동 트렌드** | 연도별·월별 출동 건수 추이 |
| **3. 뺑뺑이 분석** | 2차 이송 발생률, 거부 이유, 추가 거리 |
| **4. 증상 분석** | 증상별 정상처리율, 환자 유형, 주증상×중증도 |
| **5. 소방서 현황** | 안전센터별 출동 부하 + 전국 지도 |
| **6. 날씨 상관** | 날씨 변수 × 일별 출동 건수 Pearson 상관 |
""")

with st.sidebar:
    st.header("소방청 구급 분석")
    st.markdown("""
    **데이터 출처**
    - 소방청 공공데이터포털 구급출동현황 (2017–2022)
    - 소방청 구급상황관리현황 (2019–2023)
    - 소방청 전국소방서 좌표현황 (2024.09)
    - 서울시 소방 구급 출동 현황 Excel (2022–2024)
    """)
