"""7. 날씨 상관 — ASOS 서울(108) 관측소 기반."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR   = _PAGES_DIR.parent
_PROJ_DIR  = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from cache import _load_analytics

_ASOS_DIR    = _PROJ_DIR / "data" / "Weather"
_JSON_PATH   = _PROJ_DIR / "data" / "analytics" / "weather_correlation.json"
_ASOS_LABELS = ["기온(°C)", "강수량(mm)", "풍속(m/s)", "습도(%)"]

st.set_page_config(page_title="날씨 상관", layout="wide")
st.title("🌡️ 추가 요인: 날씨와 구급 출동")
st.caption(
    "기온·강수·풍속·습도와 서울 구급 출동 건수의 관계  "
    "| ASOS 서울(108) 시간별 관측 → 일별 집계 × 구급출동 Pearson 상관"
)

# ── 사전 계산 JSON 로드 ────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _load_json() -> dict | None:
    if _JSON_PATH.exists():
        with open(_JSON_PATH, encoding="utf-8") as f:
            return json.load(f)
    return None

# ── weather_daily JSON에서 산점도 데이터 로드 ─────────────────────────────
@st.cache_data(show_spinner=False)
def _build_scatter_data() -> tuple[pd.DataFrame | None, list[str]]:
    data = _load_analytics("weather_daily")
    if not data or not data.get("daily"):
        return None, []
    df = pd.DataFrame(data["daily"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.rename(columns={"count": "출동건수"})
    avail = [c for c in _ASOS_LABELS if c in df.columns]
    return df if not df.empty else None, avail


wdata = _load_json()
daily, available = _build_scatter_data()

# ── 상관계수 테이블 ────────────────────────────────────────────────────────
st.subheader("날씨 변수별 Pearson 상관계수")

if wdata:
    meta  = wdata.get("meta", {})
    corrs = wdata.get("correlations", [])
    years_used = meta.get("years", [])
    days_n     = meta.get("days_analyzed", 0)
    st.caption(
        f"분석 기간: {min(years_used)}~{max(years_used)}년 중 구급출동과 겹치는 **{days_n:,}일**  "
        f"| 출처: {meta.get('source','ASOS 서울(108)')}"
    )

    corr_df = pd.DataFrame([{
        "변수":   c["variable"],
        "r":      c["r"],
        "r²":     c["r2"],
        "p":      c["p"],
        "해석":   ("★ 유의" if c["significant"] else "비유의")
                 + (" (양의 상관)" if c["r"] > 0.05 else
                    " (음의 상관)" if c["r"] < -0.05 else " (무관)"),
    } for c in corrs])
    st.dataframe(corr_df, width='stretch', hide_index=True)

    # 상관계수 막대 차트
    fig_bar = px.bar(
        corr_df.sort_values("r"), x="r", y="변수",
        orientation="h",
        color="r",
        color_continuous_scale=[[0, "#3498db"], [0.5, "#ecf0f1"], [1, "#e74c3c"]],
        color_continuous_midpoint=0,
        text=corr_df.sort_values("r")["r"].map("{:+.3f}".format),
        labels={"r": "Pearson r", "변수": "날씨 변수"},
    )
    fig_bar.add_vline(x=0, line_color="black", line_width=0.8)
    fig_bar.update_traces(textposition="outside")
    fig_bar.update_layout(
        xaxis=dict(range=[-0.5, 0.5]),
        coloraxis_showscale=False,
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig_bar, width='stretch')
else:
    st.warning("weather_correlation.json 없음 — `python scripts/generate_analytics.py` 실행 후 새로고침하세요.")

st.divider()

# ── 산점도 ────────────────────────────────────────────────────────────────
if daily is None or daily.empty:
    st.error("ASOS 날씨 데이터를 불러올 수 없습니다.")
    st.stop()

data_note = f"(ASOS×구급출동 일별 조인 {len(daily):,}일 — 전체 CSV 기반)"

# 기온 산점도 (항상 표시)
st.subheader("기온 × 일별 출동 건수 산점도")
if "기온(°C)" in daily.columns:
    v = daily[["기온(°C)", "출동건수", "date"]].dropna()
    x, y = v["기온(°C)"].values, v["출동건수"].values
    sl, ic, rv, pv, _ = stats.linregress(x, y)
    xl = np.linspace(x.min(), x.max(), 100)

    fig_sc = go.Figure()
    fig_sc.add_trace(go.Scatter(
        x=v["기온(°C)"], y=v["출동건수"],
        mode="markers",
        marker=dict(color="#3498db", size=6, opacity=0.55),
        text=v["date"].dt.strftime("%Y-%m-%d"),
        hovertemplate="날짜: %{text}<br>기온: %{x:.1f}°C<br>출동: %{y}건<extra></extra>",
        name="일별 데이터",
    ))
    fig_sc.add_trace(go.Scatter(
        x=xl, y=sl * xl + ic,
        mode="lines",
        line=dict(color="#e74c3c", width=2),
        name=f"회귀선 (r={rv:.3f}, p={pv:.3f})",
    ))
    fig_sc.update_layout(
        xaxis_title="기온 (°C)",
        yaxis_title=f"일별 출동 건수 {data_note}",
        legend=dict(orientation="h", y=1.08),
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig_sc, width='stretch')

st.divider()

# 변수 선택 산점도
st.subheader("날씨 변수 탐색")
if available:
    sel = st.selectbox("날씨 변수 선택", available)
    v2  = daily[[sel, "출동건수", "date"]].dropna()
    if len(v2) >= 5:
        x2, y2 = v2[sel].values, v2["출동건수"].values
        sl2, ic2, rv2, pv2, _ = stats.linregress(x2, y2)
        xl2 = np.linspace(x2.min(), x2.max(), 100)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=v2[sel], y=v2["출동건수"],
            mode="markers",
            marker=dict(color="#9b59b6", size=6, opacity=0.55),
            text=v2["date"].dt.strftime("%Y-%m-%d"),
            hovertemplate=f"날짜: %{{text}}<br>{sel}: %{{x:.2f}}<br>출동: %{{y}}건<extra></extra>",
            name="일별 데이터",
        ))
        fig2.add_trace(go.Scatter(
            x=xl2, y=sl2 * xl2 + ic2,
            mode="lines",
            line=dict(color="#e74c3c", width=2),
            name=f"회귀선 (r={rv2:.3f}, p={pv2:.3f})",
        ))
        fig2.update_layout(
            xaxis_title=sel,
            yaxis_title=f"일별 출동 건수 {data_note}",
            legend=dict(orientation="h", y=1.08),
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig2, width='stretch')

st.divider()

with st.expander("💡 이 시각화로 알 수 있는 것"):
    if wdata and wdata.get("correlations"):
        c_map = {c["variable"]: c for c in wdata["correlations"]}
        r_tmp  = c_map.get("기온(°C)",   {}).get("r", 0)
        r_hum  = c_map.get("습도(%)",    {}).get("r", 0)
        r_rain = c_map.get("강수량(mm)", {}).get("r", 0)
        r_wind = c_map.get("풍속(m/s)",  {}).get("r", 0)
        st.markdown(f"""
- **기온 r={r_tmp:+.3f} (유의)**: 기온이 높을수록 서울 구급 출동이 증가합니다. 폭염 시즌 구급 자원 사전 증편의 통계적 근거입니다.
- **습도 r={r_hum:+.3f} (유의)**: 습도가 높을수록 출동이 증가하는 경향이 있습니다. 여름철 고온다습 환경과 연관됩니다.
- **강수량 r={r_rain:+.3f} (유의)**: 비 오는 날 출동이 소폭 늘어납니다. 낙상·교통사고 증가 효과가 외출 감소 효과를 약간 상회합니다.
- **풍속 r={r_wind:+.3f} (유의)**: 바람이 강할수록 출동이 소폭 감소합니다. 강풍 시 외출 자체가 줄어드는 효과로 해석됩니다.
- **설명력(r²)**: 기온 기준 r²≈{r_tmp**2:.3f}로 날씨 외 요인(요일·시간대·행사·인구)이 출동 건수를 더 크게 결정합니다.
        """)
    else:
        st.markdown("analytics JSON 로드 후 해석이 표시됩니다.")

st.info(
    f"**데이터 출처**: ASOS 서울(108) 시간별 관측 데이터  "
    f"| 구급출동 CSV와 겹치는 연도({', '.join(str(y) for y in (wdata or {}).get('meta', {}).get('years', []))}) 기준"
)
