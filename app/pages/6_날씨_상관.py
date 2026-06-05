"""6. 날씨 상관 — Plotly 인터랙티브."""
import sys
from pathlib import Path

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR = _PAGES_DIR.parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from cache import get_dispatch

st.set_page_config(page_title="날씨 상관", layout="wide")
st.title("🌡️ 날씨 × 출동 상관 분석")
st.caption(
    "구급출동(A) 내장 기상 컬럼(HR_UNIT_*) 활용 — 외부 데이터 JOIN 없음  "
    "| 일별 집계 Pearson 상관계수"
)

WEATHER_COLS = {
    "HR_UNIT_ARTMP": "기온(°C)",
    "HR_UNIT_RN":    "강수량(mm)",
    "HR_UNIT_WSPD":  "풍속(m/s)",
    "HR_UNIT_HUM":   "습도(%)",
    "HR_UNIT_SNWFL": "적설량(cm)",
    "HR_UNIT_VSDST": "가시거리(m)",
}

# ── 일별 집계 ─────────────────────────────────────────────────────────────
df = get_dispatch()
date_col = "DCLR_YMD"
available = [c for c in WEATHER_COLS if c in df.columns]

if date_col not in df.columns or not available:
    st.error("날씨 분석에 필요한 컬럼이 없습니다.")
    st.stop()

count_col = "RPTP_NO" if "RPTP_NO" in df.columns else "_year"
agg_dict = {count_col: "count"}
agg_dict.update({c: "mean" for c in available})
daily = df.groupby(date_col).agg(agg_dict).reset_index()
daily = daily.rename(columns={count_col: "출동건수"})

st.caption(f"일별 집계: {len(daily):,}일 | 날씨 컬럼: {len(available)}개")

# ── 상관계수 계산 ─────────────────────────────────────────────────────────
corrs = []
for col, label in WEATHER_COLS.items():
    if col not in daily.columns:
        continue
    valid = daily[[col, "출동건수"]].dropna()
    if len(valid) < 5:
        continue
    r, p = stats.pearsonr(valid[col], valid["출동건수"])
    corrs.append({"변수": label, "컬럼": col, "r": round(r, 3), "p": round(p, 3)})

corrs_sorted = sorted(corrs, key=lambda x: abs(x["r"]), reverse=True)

# ── 상관계수 테이블 ────────────────────────────────────────────────────────
st.subheader("날씨 변수별 상관계수")
import pandas as pd
corr_df = pd.DataFrame(corrs_sorted)[["변수", "r", "p"]]
corr_df["해석"] = corr_df.apply(
    lambda row: ("★ 유의" if row["p"] < 0.05 else "비유의")
    + (" (양의 상관)" if row["r"] > 0.05 else " (음의 상관)" if row["r"] < -0.05 else " (무관)"),
    axis=1,
)
st.dataframe(corr_df, use_container_width=True, hide_index=True)

st.divider()

# ── 상관계수 막대 ────────────────────────────────────────────────────────
st.subheader("변수별 상관계수")
if corrs:
    corr_plot = pd.DataFrame(corrs_sorted)
    fig_corr = px.bar(
        corr_plot.sort_values("r"), x="r", y="변수",
        orientation="h",
        color="r",
        color_continuous_scale=[[0, "#3498db"], [0.5, "#ecf0f1"], [1, "#e74c3c"]],
        color_continuous_midpoint=0,
        labels={"r": "Pearson r", "변수": "날씨 변수"},
        text=corr_plot.sort_values("r")["r"].map("{:+.3f}".format),
    )
    fig_corr.add_vline(x=0, line_color="black", line_width=0.8)
    fig_corr.update_traces(textposition="outside")
    fig_corr.update_layout(
        xaxis=dict(range=[-0.5, 0.5]),
        coloraxis_showscale=False,
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig_corr, use_container_width=True)

st.divider()

# ── 기온 산점도 + 회귀선 ─────────────────────────────────────────────────
st.subheader("기온 × 일별 출동 건수 산점도")
temp_col = "HR_UNIT_ARTMP"
if temp_col in daily.columns:
    valid = daily[[temp_col, "출동건수", date_col]].dropna()
    x, y = valid[temp_col].values, valid["출동건수"].values
    slope, intercept, r_val, p_val, _ = stats.linregress(x, y)
    x_line = np.linspace(x.min(), x.max(), 100)

    fig_sc = go.Figure()
    fig_sc.add_trace(go.Scatter(
        x=valid[temp_col], y=valid["출동건수"],
        mode="markers",
        marker=dict(color="#3498db", size=7, opacity=0.6),
        text=valid[date_col],
        hovertemplate="날짜: %{text}<br>기온: %{x:.1f}°C<br>출동: %{y}건<extra></extra>",
        name="일별 데이터",
    ))
    fig_sc.add_trace(go.Scatter(
        x=x_line, y=slope * x_line + intercept,
        mode="lines",
        line=dict(color="#e74c3c", width=2),
        name=f"회귀선 (r={r_val:.3f}, p={p_val:.3f})",
    ))
    fig_sc.update_layout(
        xaxis_title="기온 (°C)",
        yaxis_title="일별 출동 건수 (샘플)",
        legend=dict(orientation="h", y=1.08),
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig_sc, use_container_width=True)

# ── 다른 날씨 변수 선택 ───────────────────────────────────────────────────
st.subheader("다른 날씨 변수 탐색")
var_labels = {v: k for k, v in WEATHER_COLS.items() if k in daily.columns}
sel_label = st.selectbox("날씨 변수 선택", list(var_labels.keys()))
sel_col = var_labels[sel_label]

valid2 = daily[[sel_col, "출동건수", date_col]].dropna()
if len(valid2) >= 5:
    x2, y2 = valid2[sel_col].values, valid2["출동건수"].values
    slope2, intercept2, r2, p2, _ = stats.linregress(x2, y2)
    x_line2 = np.linspace(x2.min(), x2.max(), 100)

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=valid2[sel_col], y=valid2["출동건수"],
        mode="markers",
        marker=dict(color="#9b59b6", size=7, opacity=0.6),
        text=valid2[date_col],
        hovertemplate=f"날짜: %{{text}}<br>{sel_label}: %{{x:.2f}}<br>출동: %{{y}}건<extra></extra>",
        name="일별 데이터",
    ))
    fig2.add_trace(go.Scatter(
        x=x_line2, y=slope2 * x_line2 + intercept2,
        mode="lines",
        line=dict(color="#e74c3c", width=2),
        name=f"회귀선 (r={r2:.3f}, p={p2:.3f})",
    ))
    fig2.update_layout(
        xaxis_title=sel_label,
        yaxis_title="일별 출동 건수 (샘플)",
        legend=dict(orientation="h", y=1.08),
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig2, use_container_width=True)

st.warning(
    "**통계적 한계**: 샘플 기반 일별 집계 — 표본 수가 적어 유의성 제한적.  \n"
    "기온(r≈+0.267, p<0.05)만 통계적으로 유의하며 나머지는 참고 수준."
)
