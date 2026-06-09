"""3. 뺑뺑이 분석 — Plotly 인터랙티브 (전체 CSV analytics JSON 기반)."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR = _PAGES_DIR.parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from cache import _load_analytics

st.set_page_config(page_title="뺑뺑이 분석", layout="wide")
st.title("🚨 핵심 문제: 2차 이송(뺑뺑이)")
st.caption("구급출동(A) 서울 한정 — 어디서·왜 발생하는가 | TRANS2_RSN 기재 여부로 2차 이송 정의 | 전체 330만 건 기반")

# ── analytics JSON 로드 ────────────────────────────────────────────────────
_yearly   = _load_analytics("yearly_trend")
_district = _load_analytics("district_transfer")
_transfer = _load_analytics("transfer_analysis")

if not _yearly or not _district or not _transfer:
    st.warning("analytics JSON 없음 — `python scripts/generate_analytics.py` 실행 후 새로고침하세요.")
    st.stop()

# ── 요약 메트릭 ────────────────────────────────────────────────────────────
yearly_rows = _yearly.get("yearly", [])
total = sum(y["dispatches"] for y in yearly_rows)
n2    = sum(y["transfers"]  for y in yearly_rows)
n3    = sum(y.get("transfers3", 0) for y in yearly_rows)
dist_km = _transfer.get("distance_km", {})

c1, c2, c3 = st.columns(3)
c1.metric("2차 이송률 (뺑뺑이)", f"{n2/total*100:.2f}%" if total else "N/A", help=f"{n2:,}건 / {total:,}건")
c2.metric("3차 이송률",          f"{n3/total*100:.2f}%" if total else "N/A")
c3.metric("평균 추가 거리",      f"{dist_km.get('mean', 0):.1f} km" if dist_km else "데이터 없음")

st.divider()

# ── 연도별 발생률 ──────────────────────────────────────────────────────────
st.subheader("연도별 2차 이송 발생률")

yr_df = pd.DataFrame(yearly_rows)
fig1 = go.Figure()
fig1.add_trace(go.Scatter(
    x=yr_df["year"], y=yr_df["transfer_rate_pct"],
    mode="lines+markers",
    line=dict(color="#e74c3c", width=2),
    marker=dict(size=8),
    fill="tozeroy",
    fillcolor="rgba(231,76,60,0.12)",
    hovertemplate="연도: %{x}<br>발생률: %{y:.2f}%<extra></extra>",
))
fig1.update_layout(
    xaxis=dict(tickvals=yr_df["year"].tolist(), ticktext=[str(y) for y in yr_df["year"]]),
    yaxis=dict(title="발생률 (%)"),
    hovermode="x unified",
    margin=dict(t=20, b=20),
)
st.plotly_chart(fig1, width='stretch')
st.caption("전체 구급출동 CSV 기반 (2017–2022)")

st.divider()

# ── 서울 자치구별 발생률 ─────────────────────────────────────────────────
st.subheader("서울 자치구별 2차 이송 발생률")

dist_df = pd.DataFrame(_district.get("districts", []))
if not dist_df.empty:
    dist_df = dist_df[dist_df["dispatches"] >= 1000]  # 전체 데이터이므로 임계값 상향
    dist_df = dist_df.sort_values("rate_pct")
    median_rate = dist_df["rate_pct"].median()

    fig2 = px.bar(
        dist_df, x="rate_pct", y="district",
        orientation="h",
        color="rate_pct",
        color_continuous_scale=[[0, "#3498db"], [0.5, "#f39c12"], [1, "#e74c3c"]],
        labels={"rate_pct": "발생률 (%)", "district": "자치구"},
        hover_data={"dispatches": True, "transfers": True},
    )
    fig2.add_vline(x=median_rate, line_dash="dash", line_color="gray",
                   annotation_text=f"중앙값 {median_rate:.2f}%")
    fig2.update_layout(coloraxis_showscale=False, margin=dict(t=20, b=20))
    st.plotly_chart(fig2, width='stretch')
    st.caption("출동 1,000건 이상 자치구만 표시 | 전체 CSV 기반 | 색이 짙을수록 발생률 높음")
else:
    st.warning("자치구별 데이터 없음")

st.divider()

# ── 거부 이유 & 추가 거리 히스토그램 ──────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("2차 이송 거부 이유")
    reason_df = pd.DataFrame(_transfer.get("reasons", []))
    if not reason_df.empty:
        fig3 = px.bar(
            reason_df, x="reason", y="count",
            color="reason",
            text="count",
            color_discrete_sequence=px.colors.qualitative.Set2,
            labels={"reason": "이유", "count": "건수"},
        )
        fig3.update_traces(textposition="outside")
        fig3.update_layout(showlegend=False, margin=dict(t=20, b=20))
        st.plotly_chart(fig3, width='stretch')
    else:
        st.info("거부 이유 데이터 없음")

with col2:
    st.subheader("추가 이동 거리 분포")
    hist_data = _transfer.get("distance_hist", [])
    if hist_data and dist_km:
        hist_df = pd.DataFrame(hist_data)
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(
            x=[(r["x0"] + r["x1"]) / 2 for r in hist_data],
            y=[r["count"] for r in hist_data],
            width=[(r["x1"] - r["x0"]) * 0.9 for r in hist_data],
            marker_color="#e74c3c",
            opacity=0.8,
            hovertemplate="거리: %{x:.1f}km<br>건수: %{y}<extra></extra>",
        ))
        median_v = dist_km.get("median", 0)
        mean_v   = dist_km.get("mean", 0)
        fig4.add_vline(x=median_v, line_dash="dash", line_color="#2c3e50",
                       annotation_text=f"중앙값 {median_v:.1f}km")
        fig4.add_vline(x=mean_v, line_dash="dot", line_color="#7f8c8d",
                       annotation_text=f"평균 {mean_v:.1f}km")
        fig4.update_layout(
            xaxis_title="추가 거리 (km)",
            yaxis_title="건수",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig4, width='stretch')
    elif dist_km:
        st.info(f"히스토그램 데이터 없음 | 중앙값: {dist_km.get('median', 0):.1f}km, 평균: {dist_km.get('mean', 0):.1f}km")
    else:
        st.info("추가 거리 데이터 없음")

st.divider()

with st.expander("💡 이 시각화로 알 수 있는 것"):
    st.markdown("""
    - **연도별 발생률 V자 패턴**: 2019년 최저 → 2021년 급반등. COVID 이전 개선 흐름이 팬데믹 이후 응급실 혼잡 심화로 역전됐을 가능성이 있습니다.
    - **자치구별 격차**: 상위권(중구, 관악구, 은평구)은 인근 응급실 수용 역량이 상대적으로 부족한 지역이며, 중앙값 기준으로 절반 이상의 자치구가 낮은 편입니다.
    - **거부 이유 — '진료 불가'가 '응급실 포화'보다 많음**: 단순 병상 부족보다 전문의 부재·처치 불가 문제가 더 빈번하다는 의미로, 야간·주말 전문의 확보 정책이 필요합니다.
    - **추가 이동 거리 분포**: 절반 이상의 뺑뺑이 환자는 2km 이내에서 수용 병원을 찾습니다. 그러나 우측 꼬리가 길어 일부 환자는 상당히 먼 거리를 이동하며, 이는 골든타임 침해 위험이 큽니다.
    """)

st.info(
    "**분석 방법론**\n\n"
    "- 2차 이송 정의: `TRANS2_RSN` 컬럼에 값이 기재된 경우\n"
    "- `GRNDS2_DSTNC` 단독 판별 불가 — 정상 이송에도 값이 있음\n"
    "- 서울(`GRNDS_CTPV_NM` 포함) 필터링 적용\n"
    "- **전체 구급출동 CSV 기반 (2017–2022)**"
)
