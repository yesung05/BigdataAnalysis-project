"""5. 소방서 현황 — Plotly 인터랙티브."""
import sys
from pathlib import Path

import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR = _PAGES_DIR.parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from cache import get_dispatch, get_station_coords
from src.config import FIGURES_DIR

st.set_page_config(page_title="소방서 현황", layout="wide")
st.title("🔥 소방서 현황")
st.caption("구급출동(A) × 소방서 좌표(B) LEFT JOIN — 정규화 센터명 기준 매칭")

dispatch_df = get_dispatch()
station_df = get_station_coords()

# ── 안전센터별 출동 건수 집계 ─────────────────────────────────────────────
_EXCLUDE = {"현장대응단"}
if "CNTR_NM" in dispatch_df.columns:
    filtered = dispatch_df[~dispatch_df["CNTR_NM"].isin(_EXCLUDE)]
    load = filtered.groupby("CNTR_NM").size().reset_index(name="출동건수")
    load = load.sort_values("출동건수", ascending=False)
else:
    load = None

# ── 상위 N 막대 ─────────────────────────────────────────────────────────
st.subheader("안전센터별 출동 건수")

col_ctrl, _ = st.columns([1, 3])
with col_ctrl:
    top_n = st.slider("표시 개수", 10, 50, 30, step=5)

if load is not None:
    top = load.head(top_n).sort_values("출동건수")
    fig = px.bar(
        top, x="출동건수", y="CNTR_NM",
        orientation="h",
        color="출동건수",
        color_continuous_scale=[[0, "#f5b7b1"], [1, "#c0392b"]],
        labels={"CNTR_NM": "안전센터", "출동건수": "출동 건수 (샘플)"},
        text="출동건수",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        coloraxis_showscale=False,
        yaxis=dict(tickfont=dict(size=11)),
        margin=dict(t=20, b=20),
        height=max(400, top_n * 22),
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    excluded_count = len(dispatch_df) - len(filtered) if "CNTR_NM" in dispatch_df.columns else 0
    c1.metric("집계된 안전센터", f"{len(load):,}개")
    c2.metric("현장대응단 제외", f"{excluded_count:,}건")
    c3.metric("샘플 기준", "120,000건")
else:
    st.warning("CNTR_NM 컬럼 없음")

st.divider()

# ── 소방서 유형·지역 분포 ────────────────────────────────────────────────
st.subheader("소방서 데이터 분포 (B)")

col1, col2 = st.columns(2)
with col1:
    if "유형" in station_df.columns:
        vc = station_df["유형"].value_counts().reset_index()
        vc.columns = ["유형", "개수"]
        fig2 = px.pie(
            vc, names="유형", values="개수",
            hole=0.3,
            title="유형별 분포",
        )
        fig2.update_traces(
            textposition="inside",
            textinfo="percent+label",
        )
        st.plotly_chart(fig2, use_container_width=True)

with col2:
    if "관할소방서" in station_df.columns:
        vc2 = station_df["관할소방서"].value_counts().head(15).reset_index()
        vc2.columns = ["관할소방서", "센터 수"]
        fig3 = px.bar(
            vc2.sort_values("센터 수"), x="센터 수", y="관할소방서",
            orientation="h",
            title="관할소방서별 센터 수 (상위 15개)",
            color="센터 수",
            color_continuous_scale="Blues",
        )
        fig3.update_layout(coloraxis_showscale=False, margin=dict(t=40, b=20))
        st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── Folium 지도 ─────────────────────────────────────────────────────────────
st.subheader("전국 안전센터 출동 부하 지도")
map_path = FIGURES_DIR / "station_load_map.html"
if map_path.exists():
    html_content = map_path.read_text(encoding="utf-8")
    components.html(html_content, height=580, scrolling=False)
    st.caption("버블 크기 ∝ √출동건수 | 클릭 시 팝업에서 센터명·출동건수 확인")
else:
    st.warning(
        "station_load_map.html 파일이 없습니다.  \n"
        "`python src/analysis/station_load.py`를 먼저 실행하세요."
    )

st.info(
    "**현장대응단 제외**  \n"
    "샘플 120,000건 중 약 27%가 CNTR_NM='현장대응단'으로 기재됨.  \n"
    "실제 소방센터가 아닌 출동 분류 코드이므로 센터 분석에서 제외."
)
