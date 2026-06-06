"""5. 소방서 현황 — Plotly 인터랙티브."""
import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR = _PAGES_DIR.parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from cache import get_center_counts, get_station_coords
from src.config import FIGURES_DIR

st.set_page_config(page_title="소방서 현황", layout="wide")
st.title("🔥 소방 안전센터 출동 부하")
st.caption("구급출동(A) 전체 CSV 집계 — 어떤 센터에 수요가 집중되는가 | 현장대응단 제외")

station_df = get_station_coords()

# ── 전체 CSV에서 서울 안전센터 출동 건수 집계 ─────────────────────────────
load = get_center_counts()

# ── 상위 N 막대 ─────────────────────────────────────────────────────────
st.subheader("안전센터별 출동 건수")

col_ctrl, col_chk, _ = st.columns([2, 1, 1])
with col_ctrl:
    slider_max = max(50, len(load))
    top_n = st.slider("상위 N개 표시", 10, min(slider_max, 300), 50, step=10)
with col_chk:
    show_all = st.checkbox("전체 표시", value=False)

if not load.empty:
    display = load if show_all else load.head(top_n)
    display = display.sort_values("출동건수")
    fig = px.bar(
        display, x="출동건수", y="CNTR_NM",
        orientation="h",
        color="출동건수",
        color_continuous_scale=[[0, "#f5b7b1"], [1, "#c0392b"]],
        labels={"CNTR_NM": "안전센터", "출동건수": "출동 건수 (전체)"},
        text="출동건수",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        coloraxis_showscale=False,
        yaxis=dict(tickfont=dict(size=11)),
        margin=dict(t=20, b=20),
        height=max(500, len(display) * 22),
    )
    st.plotly_chart(fig, width='stretch')

    c1, c2, c3 = st.columns(3)
    c1.metric("집계된 안전센터", f"{len(load):,}개")
    c2.metric("표시 중", f"{len(display):,}개")
    c3.metric("집계 기준", "전체 CSV (2017–2022)")
else:
    st.warning("CNTR_NM 집계 결과 없음")

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
        st.plotly_chart(fig2, width='stretch')

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
        st.plotly_chart(fig3, width='stretch')

st.divider()

# ── Folium 지도 ─────────────────────────────────────────────────────────────
st.subheader("전국 안전센터 출동 부하 지도")
map_path = FIGURES_DIR / "station_load_map.html"
if map_path.exists():
    html_content = map_path.read_text(encoding="utf-8")
    st.iframe(html_content, height=580, scrolling=False)
    st.caption("버블 크기 ∝ √출동건수 | 클릭 시 팝업에서 센터명·출동건수 확인")
else:
    st.warning(
        "station_load_map.html 파일이 없습니다.  \n"
        "`python src/analysis/station_load.py`를 먼저 실행하세요."
    )

with st.expander("💡 이 시각화로 알 수 있는 것"):
    st.markdown("""
    - **역삼119안전센터 1위(2,055건)**: 강남구 역삼동은 고층 오피스·주거 밀집 지역으로 서울 전체에서 가장 많은 구급 출동을 처리합니다. 2위 영동(1,871건), 3위 상계(1,845건)가 뒤를 잇습니다.
    - **상위-하위 2배 격차**: 1위 역삼(2,055건) vs 30위 난곡(970건)으로 약 2.1배 차이입니다. 상위 센터에 인력·예비 차량을 집중 배치하거나 인근 센터와 출동 분담 체계를 재검토할 근거가 됩니다.
    - **강남·노원·송파 집중**: 상위 30개 중 상당수가 강남(역삼·서초·가락·잠실)과 노원(상계·중계)에 분포합니다. 대규모 주거단지와 상업지역의 구급 수요가 동시에 집중되는 패턴입니다.
    - **전국 지도(버블)**: 버블 크기가 클수록 해당 센터의 출동 부하가 크며, 지리적으로 밀집된 지역의 부하 집중 여부를 시각적으로 파악할 수 있습니다.
    """)

st.info(
    "**현장대응단 제외**  \n"
    "`CNTR_NM='현장대응단'`은 실제 소방 안전센터가 아닌 출동 분류 코드이므로 센터 분석에서 제외됩니다.  \n"
    "집계는 전체 CSV(2017–2022) 기준이며 서울(`GRNDS_CTPV_NM` 포함) 필터링 적용."
)
