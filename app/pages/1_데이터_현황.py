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

from cache import get_dispatch, get_mgmt, get_seoul_excel, get_station_coords
from src.analysis.time_series import _count_file_rows
from src.config import DATASETS

st.set_page_config(page_title="데이터 현황", layout="wide")
st.title("📊 데이터 현황")
st.caption("4개 원천 데이터셋의 규모·분포·샘플을 확인합니다.")

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
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    dispatch_df = get_dispatch()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**종결구분 분포 (TRMN_SE_NM)**")
        if "TRMN_SE_NM" in dispatch_df.columns:
            vc = dispatch_df["TRMN_SE_NM"].value_counts().reset_index()
            vc.columns = ["종결구분", "건수"]
            fig2 = px.pie(vc, names="종결구분", values="건수", hole=0.3)
            fig2.update_traces(textposition="inside", textinfo="percent+label")
            fig2.update_layout(margin=dict(t=20, b=20))
            st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.markdown("**환자발생유형 분포 (PTN_OCRN_TYPE_NM)**")
        if "PTN_OCRN_TYPE_NM" in dispatch_df.columns:
            vc2 = dispatch_df["PTN_OCRN_TYPE_NM"].value_counts().reset_index()
            vc2.columns = ["발생유형", "건수"]
            fig3 = px.pie(vc2, names="발생유형", values="건수", hole=0.3)
            fig3.update_traces(textposition="inside", textinfo="percent+label")
            fig3.update_layout(margin=dict(t=20, b=20))
            st.plotly_chart(fig3, use_container_width=True)

    with st.expander("샘플 5행 미리보기"):
        st.dataframe(dispatch_df.head(), use_container_width=True)

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
            st.plotly_chart(fig4, use_container_width=True)

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
            st.plotly_chart(fig5, use_container_width=True)

    with st.expander("샘플 5행 미리보기"):
        st.dataframe(station_df.head(), use_container_width=True)

# ── 탭 C: 구급상황관리 ──────────────────────────────────────────────────────
with tab_c:
    st.subheader("구급상황관리현황 (C)")
    mgmt_df = get_mgmt()

    c1, c2 = st.columns(2)
    c1.metric("로드 샘플 수", f"{len(mgmt_df):,}행")
    c2.metric("분석 연도", "2019 – 2023")

    col1, col2 = st.columns(2)
    with col1:
        if "SRIL_CLSF_NM" in mgmt_df.columns:
            st.markdown("**중증도 분포**")
            vc = mgmt_df["SRIL_CLSF_NM"].value_counts().reset_index()
            vc.columns = ["중증도", "건수"]
            fig6 = px.pie(vc, names="중증도", values="건수", hole=0.3)
            fig6.update_traces(textposition="inside", textinfo="percent+label")
            fig6.update_layout(margin=dict(t=20, b=20))
            st.plotly_chart(fig6, use_container_width=True)

    with col2:
        if "MAIN_SYM_NM" in mgmt_df.columns:
            st.markdown("**주증상 분포 (상위 15개)**")
            vc2 = mgmt_df["MAIN_SYM_NM"].value_counts().head(15).reset_index()
            vc2.columns = ["주증상", "건수"]
            fig7 = px.bar(
                vc2.sort_values("건수"), x="건수", y="주증상",
                orientation="h", color="건수",
                color_continuous_scale="Oranges",
                text="건수",
            )
            fig7.update_traces(textposition="outside")
            fig7.update_layout(coloraxis_showscale=False, margin=dict(t=20, b=20))
            st.plotly_chart(fig7, use_container_width=True)

    if "_year" in mgmt_df.columns:
        st.markdown("**연도별 로드 건수**")
        yr_vc = mgmt_df["_year"].value_counts().sort_index().reset_index()
        yr_vc.columns = ["연도", "건수"]
        fig8 = px.bar(
            yr_vc, x="연도", y="건수",
            text=yr_vc["건수"].map("{:,}".format),
            color_discrete_sequence=["#2ecc71"],
        )
        fig8.update_traces(textposition="outside")
        fig8.update_layout(
            xaxis=dict(type="category"),
            yaxis=dict(tickformat=","),
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig8, use_container_width=True)

    with st.expander("샘플 5행 미리보기"):
        st.dataframe(mgmt_df.head(), use_container_width=True)

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
        st.plotly_chart(fig9, use_container_width=True)

    for sheet_name, df in sheets.items():
        with st.expander(f"{sheet_name} 전체 테이블"):
            st.dataframe(df, use_container_width=True)
