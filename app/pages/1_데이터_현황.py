"""1. 데이터 현황 — 4개 데이터셋 기초통계 (Plotly 차트 포함)."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR = _PAGES_DIR.parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from cache import _load_analytics, get_dispatch, get_mgmt, get_seoul_excel, get_station_coords
from src.analysis.time_series import _count_file_rows
from src.config import DATASETS

st.set_page_config(page_title="데이터 현황", layout="wide")
st.title("📊 분석 데이터 소개")
st.caption("어떤 데이터를 어떻게 사용했나 | 4개 원천 데이터셋의 규모·분포·샘플")

tab_a, tab_b, tab_c, tab_d = st.tabs([
    "구급출동현황 (A)", "소방서 좌표 (B)", "구급상황관리 (C)", "서울시 Excel (D)"
])

# ── 탭 A: 구급출동현황 ──────────────────────────────────────────────────────
with tab_a:
    st.subheader("구급출동현황 (A)")

    dispatch_dir = DATASETS["구급출동"]["dir"]
    year_counts = {}
    for yr in range(2017, 2023):
        fpath = dispatch_dir / f"구급출동_{yr}.csv"
        if fpath.exists():
            cnt = _count_file_rows(fpath)
            if cnt:
                year_counts[yr] = cnt

    total_rows = sum(year_counts.values())
    c1, c2, c3 = st.columns(3)
    c1.metric("전체 출동 건수", f"{total_rows:,}건")
    c2.metric("분석 연도", "2017 – 2022")
    c3.metric("컬럼 수", "92개")

    if year_counts:
        df_yr = pd.DataFrame({
            "연도": list(year_counts.keys()),
            "출동 건수": list(year_counts.values())
        })
        fig = px.bar(
            df_yr, x="연도", y="출동 건수",
            text=df_yr["출동 건수"].map("{:,}".format),
            color="출동 건수",
            color_continuous_scale="Blues",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            coloraxis_showscale=False,
            xaxis=dict(tickvals=df_yr["연도"].tolist(), type="category"),
            yaxis=dict(tickformat=","),
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig, width='stretch')

    st.divider()
    _trmn = _load_analytics("trmn_distribution")
    _occ  = _load_analytics("occurrence_type")

    if _trmn and _occ:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**종결구분 분포 (TRMN_SE_NM)**")
            trmn_df = pd.DataFrame(_trmn["distribution"]).rename(columns={"label": "종결구분", "count": "건수"})
            fig2 = px.pie(trmn_df, names="종결구분", values="건수", hole=0.3)
            fig2.update_traces(textposition="inside", textinfo="percent+label")
            fig2.update_layout(margin=dict(t=20, b=20))
            st.plotly_chart(fig2, width='stretch')
        with col2:
            st.markdown("**환자발생유형 분포 (PTN_OCRN_TYPE_NM)**")
            occ_df = pd.DataFrame(_occ["types"]).rename(columns={"type": "발생유형", "count": "건수"})
            fig3 = px.pie(occ_df, names="발생유형", values="건수", hole=0.3)
            fig3.update_traces(textposition="inside", textinfo="percent+label")
            fig3.update_layout(margin=dict(t=20, b=20))
            st.plotly_chart(fig3, width='stretch')
        st.caption("전체 330만 건 기반 (2017–2022)")
    else:
        st.warning("analytics JSON 없음 — `python scripts/generate_analytics.py` 실행 후 새로고침하세요.")

    dispatch_df = get_dispatch()
    with st.expander("샘플 5행 미리보기"):
        st.dataframe(dispatch_df.head().astype(str), width='stretch')

    with st.expander("💡 이 시각화로 알 수 있는 것"):
        st.markdown("""
        - **연도별 출동 건수**: 2017년 약 54만 건에서 2022년 약 62만 건으로 증가. 2020년(약 48만 건)만 COVID-19 영향으로 감소했다가 이후 반등해 6년 최고치를 기록했습니다.
        - **환자발생유형 파이**: 질병외(사고·외상, 50.3%, 60,305건)와 질병(47.1%, 56,508건)이 거의 절반씩입니다. 서울은 고령화 질병 수요와 도시형 사고 수요가 동시에 높은 구조입니다.
        - **종결구분 파이**: 대부분의 증상에서 정상처리(완료이송)율이 95% 이상으로 출동 건수 대부분이 병원 이송으로 완료됩니다.
        """)

# ── 탭 B: 소방서 좌표 ──────────────────────────────────────────────────────
with tab_b:
    st.subheader("소방서 좌표 (B)")
    station_df = get_station_coords()

    c1, c2 = st.columns(2)
    c1.metric("전국 소방서·안전센터", f"{len(station_df):,}개")
    c2.metric("데이터 기준일", "2024-09-01")

    col1, col2 = st.columns(2)
    with col1:
        if "유형" in station_df.columns:
            st.markdown("**유형별 분포**")
            vc = station_df["유형"].value_counts().reset_index()
            vc.columns = ["유형", "개수"]
            fig4 = px.bar(
                vc.sort_values("개수"), x="개수", y="유형",
                orientation="h", color="개수",
                color_continuous_scale="Reds",
                text="개수",
            )
            fig4.update_traces(textposition="outside")
            fig4.update_layout(coloraxis_showscale=False, margin=dict(t=20, b=20))
            st.plotly_chart(fig4, width='stretch')

    with col2:
        if "관할소방서" in station_df.columns:
            st.markdown("**관할소방서별 센터 수 (상위 15개)**")
            vc2 = station_df["관할소방서"].value_counts().head(15).reset_index()
            vc2.columns = ["관할소방서", "센터 수"]
            fig5 = px.bar(
                vc2.sort_values("센터 수"), x="센터 수", y="관할소방서",
                orientation="h", color="센터 수",
                color_continuous_scale="Blues",
                text="센터 수",
            )
            fig5.update_traces(textposition="outside")
            fig5.update_layout(coloraxis_showscale=False, margin=dict(t=20, b=20))
            st.plotly_chart(fig5, width='stretch')

    with st.expander("샘플 5행 미리보기"):
        st.dataframe(station_df.head().astype(str), width='stretch')

    with st.expander("💡 이 시각화로 알 수 있는 것"):
        st.markdown("""
        - **유형별 분포**: 안전센터 수가 소방서보다 훨씬 많으면, 현장 대응 네트워크가 세분화되어 있어 출동 반경이 짧음을 의미합니다.
        - **관할소방서별 센터 수**: 특정 소방서 관할에 센터가 집중될수록 해당 지역의 인구 밀도나 위험 지역 분포가 불균등함을 나타냅니다. 이 분포를 통해 소방 자원 배치의 지역 격차를 파악할 수 있습니다.
        """)

# ── 탭 C: 구급상황관리 ──────────────────────────────────────────────────────
with tab_c:
    st.subheader("구급상황관리현황 (C)")
    _mgmt = _load_analytics("mgmt_summary")
    if _mgmt:
        c1, c2 = st.columns(2)
        total_mgmt = sum(y["count"] for y in _mgmt["yearly"])
        c1.metric("전체 건수", f"{total_mgmt:,}행")
        c2.metric("분석 연도", f"{min(y['year'] for y in _mgmt['yearly'])} – {max(y['year'] for y in _mgmt['yearly'])}")

        col1, col2 = st.columns(2)
        with col1:
            if _mgmt.get("severity"):
                st.markdown("**중증도 분포**")
                sev_df = pd.DataFrame(_mgmt["severity"]).rename(columns={"label": "중증도", "count": "건수"})
                fig6 = px.pie(sev_df, names="중증도", values="건수", hole=0.3)
                fig6.update_traces(textposition="inside", textinfo="percent+label")
                fig6.update_layout(margin=dict(t=20, b=20))
                st.plotly_chart(fig6, width='stretch')
        with col2:
            if _mgmt.get("top_symptoms"):
                st.markdown("**주증상 분포 (상위 15개)**")
                sym_df = pd.DataFrame(_mgmt["top_symptoms"][:15]).rename(columns={"symptom": "주증상", "count": "건수"})
                sym_df = sym_df.sort_values("건수")
                fig7 = px.bar(sym_df, x="건수", y="주증상", orientation="h", color="건수", color_continuous_scale="Oranges", text="건수")
                fig7.update_traces(textposition="outside")
                fig7.update_layout(coloraxis_showscale=False, margin=dict(t=20, b=20))
                st.plotly_chart(fig7, width='stretch')

        if _mgmt.get("yearly"):
            st.markdown("**연도별 건수**")
            yr_df = pd.DataFrame(_mgmt["yearly"])
            fig8 = px.bar(yr_df, x="year", y="count", text=yr_df["count"].map("{:,}".format), color_discrete_sequence=["#2ecc71"])
            fig8.update_traces(textposition="outside")
            fig8.update_layout(xaxis=dict(type="category"), yaxis=dict(tickformat=","), margin=dict(t=20, b=20))
            st.plotly_chart(fig8, width='stretch')
        st.caption("전체 구급상황관리 CSV 기반 (2019–2023)")
    else:
        st.warning("analytics JSON 없음 — `python scripts/generate_analytics.py` 실행 후 새로고침하세요.")

    with st.expander("샘플 5행 미리보기"):
        mgmt_df = get_mgmt()
        st.dataframe(mgmt_df.head().astype(str), width='stretch')

    with st.expander("💡 이 시각화로 알 수 있는 것"):
        st.markdown("""
        - **중증도 분포**: 경증 비율이 높을수록 비응급 환자의 구급 이용이 많음을 의미하며, 경증 환자를 위한 대체 의료 접근 체계의 필요성을 시사합니다.
        - **주증상 분포**: 상위에 오른 증상(의식변화, 호흡곤란, 흉통 등)은 중증 응급 환자와 직결되는 경우가 많습니다. 이 목록은 의료지도 역량 강화가 필요한 주요 증상군을 나타냅니다.
        - **연도별 건수**: 구급상황관리센터의 의료지도 건수 추이를 통해 원격 의료지도 활용도 변화를 파악할 수 있습니다.
        """)

# ── 탭 D: 서울 Excel ──────────────────────────────────────────────────────
with tab_d:
    st.subheader("서울시 구급 출동 현황 Excel (D)")
    sheets = get_seoul_excel()

    c1, c2, c3 = st.columns(3)
    c1.metric("시트 수 (연도)", f"{len(sheets)}개")
    c2.metric("분석 연도", "2022 – 2024")
    first_df = next(iter(sheets.values()))
    c3.metric("기관 수", f"{len(first_df) - 1}개", help="합계행 제외")

    monthly_data = {}
    for sheet_name, df in sheets.items():
        month_cols = [
            c for c in df.columns
            if str(c).replace("월", "").strip().isdigit()
            and 1 <= int(str(c).replace("월", "").strip()) <= 12
        ]
        if not month_cols:
            continue
        row = df.iloc[0]
        vals = {}
        for mc in month_cols:
            try:
                vals[str(mc)] = int(float(row[mc]))
            except (ValueError, TypeError):
                pass
        if vals:
            monthly_data[str(sheet_name).replace("년", "").strip()] = vals

    if monthly_data:
        rows = []
        for yr, vals in sorted(monthly_data.items()):
            for m, v in vals.items():
                rows.append({"연도": yr, "월": m, "건수": v})
        df_long = pd.DataFrame(rows)
        fig9 = px.line(
            df_long, x="월", y="건수", color="연도",
            markers=True,
            labels={"건수": "출동 건수"},
            color_discrete_sequence=["#2ecc71", "#3498db", "#e74c3c"],
        )
        fig9.update_layout(
            hovermode="x unified",
            yaxis=dict(tickformat=","),
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig9, width='stretch')

    with st.expander("💡 이 시각화로 알 수 있는 것"):
        st.markdown("""
        - **연도별 월간 출동 추이**: 3개 연도의 선이 유사한 패턴을 보인다면, 구급 수요에 뚜렷한 계절성이 존재함을 의미합니다.
        - **여름철(7–8월) 피크**: 폭염과 야외 활동 증가로 인한 온열 질환·사고 출동이 집중되는 시기입니다. 이 기간 구급 자원의 집중 배치가 필요합니다.
        - **2–3월 저점**: 실내 활동이 많고 외상·온열 사고가 적어 출동 건수가 감소합니다.
        - **연도간 수준 비교**: 같은 월이라도 연도별 절대 수치 차이를 통해 구급 수요의 장기 증가 추세를 확인할 수 있습니다.
        """)

    for sheet_name, df in sheets.items():
        with st.expander(f"{sheet_name} 전체 테이블"):
            st.dataframe(df, width='stretch')
