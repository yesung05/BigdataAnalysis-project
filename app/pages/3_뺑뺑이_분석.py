"""3. 뺑뺑이 분석 — Plotly 인터랙티브."""
import sys
from pathlib import Path

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR = _PAGES_DIR.parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from cache import get_dispatch

st.set_page_config(page_title="뺑뺑이 분석", layout="wide")
st.title("🚨 뺑뺑이 분석")
st.caption("구급출동(A) 샘플 120,000건 — TRANS2_RSN 기재 여부로 2차 이송 정의")

# ── 데이터 준비 ────────────────────────────────────────────────────────────
df_raw = get_dispatch()
df = df_raw.copy()
df["has_trans2"] = df["TRANS2_RSN"].notna()
df["has_trans3"] = df["TRANS3_RSN"].notna() if "TRANS3_RSN" in df.columns else False
df["extra_dist"] = (
    df["GRNDS2_DSTNC"].fillna(0) - df["GRNDS_DSTNC"].fillna(0)
).clip(lower=0)
df.loc[~df["has_trans2"], "extra_dist"] = float("nan")

_REASON_MAP = [
    (["응급실"], "응급실 포화"),
    (["병상", "만실", "병실", "입원실", "중환자실", "포화", "입원"], "병상 부족"),
    (["전문의", "진료", "전문", "처치", "치료", "의료", "부재"], "진료 불가"),
    (["거리", "원거리", "접근", "이동"], "거리·접근성"),
    (["기타", "무", "없음", "미상"], "기타"),
]

def _cat(text):
    if not isinstance(text, str) or not text.strip():
        return None
    for kws, label in _REASON_MAP:
        if any(kw in text for kw in kws):
            return label
    return "기타"

df["trans2_reason_cat"] = df["TRANS2_RSN"].apply(_cat)

# ── 요약 메트릭 ────────────────────────────────────────────────────────────
total = len(df)
n2 = df["has_trans2"].sum()
n3 = df["has_trans3"].sum()
extra = df.loc[df["has_trans2"] & df["extra_dist"].notna(), "extra_dist"]

c1, c2, c3 = st.columns(3)
c1.metric("2차 이송률 (뺑뺑이)", f"{n2/total*100:.2f}%", help=f"{n2:,}건 / {total:,}건")
c2.metric("3차 이송률", f"{n3/total*100:.2f}%")
c3.metric("평균 추가 거리", f"{extra.mean():.1f} km" if not extra.empty else "데이터 없음")

st.divider()

# ── 연도별 발생률 ──────────────────────────────────────────────────────────
st.subheader("연도별 2차 이송 발생률")

yr = df.groupby("_year")["has_trans2"].agg(["sum", "count"])
yr["rate"] = yr["sum"] / yr["count"] * 100
yr = yr.reset_index()

fig1 = go.Figure()
fig1.add_trace(go.Scatter(
    x=yr["_year"], y=yr["rate"],
    mode="lines+markers",
    line=dict(color="#e74c3c", width=2),
    marker=dict(size=8),
    fill="tozeroy",
    fillcolor="rgba(231,76,60,0.12)",
    hovertemplate="연도: %{x}<br>발생률: %{y:.2f}%<extra></extra>",
))
fig1.update_layout(
    xaxis=dict(tickvals=yr["_year"].tolist(), ticktext=[str(y) for y in yr["_year"]]),
    yaxis=dict(title="발생률 (%)"),
    hovermode="x unified",
    margin=dict(t=20, b=20),
)
st.plotly_chart(fig1, use_container_width=True)

st.divider()

# ── 서울 자치구별 발생률 ─────────────────────────────────────────────────
st.subheader("서울 자치구별 2차 이송 발생률")

col_sgg = "GRNDS_SGG_NM"
if col_sgg in df.columns:
    reg = (df.groupby(col_sgg)["has_trans2"]
           .agg(["sum", "count"])
           .assign(rate=lambda x: x["sum"] / x["count"] * 100))
    reg = reg[reg["count"] >= 200].sort_values("rate")
    median_rate = reg["rate"].median()

    fig2 = px.bar(
        reg.reset_index(), x="rate", y=col_sgg,
        orientation="h",
        color="rate",
        color_continuous_scale=[[0, "#3498db"], [0.5, "#f39c12"], [1, "#e74c3c"]],
        labels={"rate": "발생률 (%)", col_sgg: "자치구"},
        hover_data={"count": True, "sum": True},
    )
    fig2.add_vline(x=median_rate, line_dash="dash", line_color="gray",
                   annotation_text=f"중앙값 {median_rate:.2f}%")
    fig2.update_layout(coloraxis_showscale=False, margin=dict(t=20, b=20))
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("샘플 200건 이상인 자치구만 표시 | 색이 짙을수록 발생률 높음")
else:
    st.warning("GRNDS_SGG_NM 컬럼 없음")

st.divider()

# ── 거부 이유 ─────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("2차 이송 거부 이유")
    reason_s = df.loc[df["has_trans2"], "trans2_reason_cat"].dropna()
    if not reason_s.empty:
        counts = reason_s.value_counts().reset_index()
        counts.columns = ["이유", "건수"]
        fig3 = px.bar(
            counts, x="이유", y="건수",
            color="이유",
            text="건수",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig3.update_traces(textposition="outside")
        fig3.update_layout(showlegend=False, margin=dict(t=20, b=20))
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("거부 이유 데이터 없음")

with col2:
    st.subheader("추가 이동 거리 분포")
    trans2_dist = df.loc[df["has_trans2"] & (df["extra_dist"] > 0), "extra_dist"].clip(upper=50)
    if not trans2_dist.empty:
        fig4 = go.Figure()
        fig4.add_trace(go.Histogram(
            x=trans2_dist,
            nbinsx=20,
            marker_color="#e74c3c",
            opacity=0.8,
            hovertemplate="거리: %{x:.1f}km<br>건수: %{y}<extra></extra>",
        ))
        fig4.add_vline(x=trans2_dist.median(), line_dash="dash", line_color="#2c3e50",
                       annotation_text=f"중앙값 {trans2_dist.median():.1f}km")
        fig4.add_vline(x=trans2_dist.mean(), line_dash="dot", line_color="#7f8c8d",
                       annotation_text=f"평균 {trans2_dist.mean():.1f}km")
        fig4.update_layout(
            xaxis_title="추가 거리 (km)",
            yaxis_title="건수",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("추가 거리 데이터 없음")

st.divider()
st.info(
    "**분석 방법론**\n\n"
    "- 2차 이송 정의: `TRANS2_RSN` 컬럼에 값이 기재된 경우\n"
    "- `GRNDS2_DSTNC` 단독 판별 불가 — 정상 이송에도 값이 있음\n"
    "- 샘플: 20,000행/년 × 6년 = 120,000행 (CSV 상위 행, 서울 편향)"
)
