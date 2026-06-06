"""4. 원인 분석: 응급실 접근성 × 2차 이송 상관."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR = _PAGES_DIR.parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from cache import get_district_transfer_rate
from src.config import DATA_DIR

st.set_page_config(page_title="응급실 접근성 × 뺑뺑이", layout="wide")
st.title("🏥 원인 분석: 응급실 접근성 × 2차 이송")
st.caption(
    "응급실이 많은 자치구는 뺑뺑이가 적은가  "
    "| 서울시 응급실 76개소 × 구급출동(A) 자치구별 발생률 전체 CSV 집계"
)

# ── 응급실 데이터 로드 (76행) ─────────────────────────────────────────────
ER_PATH = DATA_DIR / "서울시 응급실 위치 정보.csv"
er_df = pd.read_csv(ER_PATH, encoding="cp949")
er_df["자치구"] = er_df["주소"].str.split().str[1]

# ── 자치구별 응급실 집계 ──────────────────────────────────────────────────
er_count = (
    er_df.groupby("자치구")
    .agg(
        응급실수=("기관ID", "count"),
        종합병원수=("병원분류", lambda x: (x == "A").sum()),
        일반병원수=("병원분류", lambda x: (x == "B").sum()),
    )
    .reset_index()
)

# ── 2차 이송 발생률 (전체 CSV) ─────────────────────────────────────────────
rate_df = get_district_transfer_rate()

# ── 병합 ─────────────────────────────────────────────────────────────────
merged = pd.merge(rate_df, er_count, on="자치구", how="inner")

# ── 요약 메트릭 ────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("서울 응급실 총수", f"{len(er_df):,}개소")
c2.metric("종합병원(A등급)", f"{(er_df['병원분류'] == 'A').sum():,}개")
c3.metric("분석 자치구 수", f"{len(merged):,}개")
c4.metric("전체 출동 건수", f"{rate_df['출동건수'].sum():,}건", help="전체 CSV 기준")

st.divider()

# ── 탭 ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "🗺 응급실 현황",
    "📊 전체 응급실 수 × 2차 이송률",
    "🏥 종합병원(A) × 2차 이송률",
])


def _scatter_with_regression(df, x_col, y_col, x_label, y_label, color_col="발생률"):
    """산점도 + OLS 회귀선 + 상관계수."""
    x = df[x_col].values
    y = df[y_col].values
    r, p = stats.pearsonr(x, y)
    slope, intercept, *_ = stats.linregress(x, y)
    x_rng = [float(x.min()), float(x.max())]
    y_rng = [slope * xi + intercept for xi in x_rng]

    fig = px.scatter(
        df, x=x_col, y=y_col,
        text="자치구",
        size="출동건수",
        size_max=28,
        color=color_col,
        color_continuous_scale=[[0, "#3498db"], [0.5, "#f39c12"], [1, "#e74c3c"]],
        labels={x_col: x_label, y_col: y_label},
        hover_data={"출동건수": True, "이송2차건수": True, "응급실수": True, "종합병원수": True},
    )
    fig.add_trace(go.Scatter(
        x=x_rng, y=y_rng,
        mode="lines",
        line=dict(color="#7f8c8d", width=1.5, dash="dash"),
        name=f"OLS 회귀선  r={r:+.3f}  p={p:.3f}",
        showlegend=True,
    ))
    fig.update_traces(textposition="top center", textfont_size=9)
    fig.update_layout(
        coloraxis_showscale=False,
        legend=dict(orientation="h", y=1.1),
        margin=dict(t=50, b=20),
    )
    return fig, r, p


# ─── 탭 1: 응급실 현황 ────────────────────────────────────────────────────
with tab1:
    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("자치구별 응급실 수")
        er_bar = er_count.sort_values("응급실수")
        fig1 = px.bar(
            er_bar, x="응급실수", y="자치구",
            orientation="h",
            color="응급실수",
            color_continuous_scale=[[0, "#d6eaf8"], [1, "#1a5276"]],
            text="응급실수",
        )
        fig1.update_traces(textposition="outside")
        fig1.update_layout(
            coloraxis_showscale=False,
            height=max(400, len(er_bar) * 26),
            margin=dict(t=10, b=10),
        )
        st.plotly_chart(fig1, width='stretch')

    with col2:
        st.subheader("병원 분류 분포")
        cls_count = er_df["병원분류명"].value_counts().reset_index()
        cls_count.columns = ["분류", "건수"]
        fig2 = px.pie(
            cls_count, names="분류", values="건수",
            hole=0.35,
            color_discrete_sequence=["#2980b9", "#e67e22", "#27ae60"],
        )
        fig2.update_traces(textinfo="percent+label", textposition="inside")
        fig2.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig2, width='stretch')

        st.subheader("응급실 목록")
        st.dataframe(
            er_df[["기관명", "병원분류명", "자치구"]]
            .sort_values(["자치구", "기관명"])
            .reset_index(drop=True),
            width='stretch',
            hide_index=True,
        )

# ─── 탭 2: 전체 응급실 수 × 2차 이송률 ──────────────────────────────────
with tab2:
    st.subheader("자치구별 응급실 수 vs 2차 이송 발생률")
    st.caption("버블 크기 ∝ 자치구 총 출동 건수 | 색이 붉을수록 2차 이송률 높음")

    if len(merged) >= 5:
        fig3, r3, p3 = _scatter_with_regression(
            merged, "응급실수", "발생률",
            "응급실 수 (개소)", "2차 이송 발생률 (%)",
        )
        st.plotly_chart(fig3, width='stretch')

        m1, m2, m3 = st.columns(3)
        m1.metric("Pearson r", f"{r3:+.3f}")
        m2.metric("p값", f"{p3:.3f}",
                  delta="★ 유의 (p<0.05)" if p3 < 0.05 else "비유의")
        m3.metric("설명력 r²", f"{r3**2:.3f}")
    else:
        st.warning("분석 가능한 자치구 수가 부족합니다.")

# ─── 탭 3: 종합병원(A) 수 × 2차 이송률 ──────────────────────────────────
with tab3:
    st.subheader("자치구별 종합병원(A등급) 수 vs 2차 이송 발생률")
    st.caption("응급실 전체 수 대신 종합병원(A)만 분리 — 수용 역량 대리 지표")

    if len(merged) >= 5:
        fig4, r4, p4 = _scatter_with_regression(
            merged, "종합병원수", "발생률",
            "종합병원 수 (A등급)", "2차 이송 발생률 (%)",
        )
        st.plotly_chart(fig4, width='stretch')

        m1, m2, m3 = st.columns(3)
        m1.metric("Pearson r", f"{r4:+.3f}")
        m2.metric("p값", f"{p4:.3f}",
                  delta="★ 유의 (p<0.05)" if p4 < 0.05 else "비유의")
        m3.metric("설명력 r²", f"{r4**2:.3f}")
    else:
        st.warning("분석 가능한 자치구 수가 부족합니다.")

st.divider()

# ── 원본 데이터 테이블 ────────────────────────────────────────────────────
with st.expander("📋 자치구별 집계 데이터"):
    disp = merged[[
        "자치구", "응급실수", "종합병원수", "일반병원수",
        "출동건수", "이송2차건수", "발생률",
    ]].copy()
    disp["발생률"] = disp["발생률"].map("{:.3f}%".format)
    st.dataframe(
        disp.sort_values("이송2차건수", ascending=False).reset_index(drop=True),
        width='stretch',
        hide_index=True,
    )

with st.expander("💡 이 시각화로 알 수 있는 것"):
    st.markdown("""
    - **음의 상관(r < 0)이 나타난다면**: 응급실이 많은 자치구일수록 2차 이송률이 낮아지는 관계로, 의료 인프라 확충이 뺑뺑이 감소에 직접 기여함을 시사합니다.
    - **종합병원(A) 상관이 더 강하다면**: 단순 응급실 수보다 수용 역량(전문의·중환자실 보유)이 핵심 변수임을 의미합니다. 응급실 신규 지정보다 기존 병원의 응급 역량 강화 정책이 더 효과적일 수 있습니다.
    - **버블 크기(출동 건수)로 이상치 해석**: 출동이 많고 응급실도 많은데 2차 이송률도 높은 자치구는 타 지역 환자 유입(의료 허브 효과)으로 인한 구조적 포화 상태일 가능성이 있습니다.
    - **상관이 약하더라도**: 응급실 위치보다 병상 수·야간 전문의 배치·응급실 운영 시간 등 질적 변수가 2차 이송에 더 큰 영향을 줄 수 있어, 추가 데이터 연계 분석이 필요합니다.
    """)

st.warning(
    "**분석 한계**  \n"
    "- 응급실 데이터는 현재(2026년) 기준이며 2017–2022년 구급출동과 시점 차이가 있습니다.  \n"
    "- 응급실 위치(수)만 분석하며, 병상 수·전문의 수·응급실 등급 등 수용 역량은 미포함입니다.  \n"
    "- 자치구 단위 집계(N=25)로 표본이 작아 통계적 유의성 해석에 주의가 필요합니다."
)
