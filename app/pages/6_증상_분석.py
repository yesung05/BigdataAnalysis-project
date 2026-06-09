"""6. 증상 분석 — Plotly 인터랙티브 (전체 CSV analytics JSON 기반)."""
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

st.set_page_config(page_title="증상 분석", layout="wide")
st.title("💊 환자 특성 분석")
st.caption(
    "어떤 환자가 구급차를 이용하고, 어떤 결과를 맞는가  "
    "| 구급출동(A) 서울 한정 × 구급상황관리(C) 독립 분석 | 전체 CSV 기반"
)

_occ    = _load_analytics("occurrence_type")
_comp   = _load_analytics("dispatch_completion")
_symsev = _load_analytics("symptom_severity")

# ── 탭 구성 ───────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["환자 발생 유형", "증상별 정상처리율", "주증상 × 중증도"])

# ── 탭 1: 파이차트 ─────────────────────────────────────────────────────────
with tab1:
    st.subheader("환자 발생 유형 분포 (A)")
    if _occ and _occ.get("types"):
        occ_df = pd.DataFrame(_occ["types"]).rename(columns={"type": "유형", "count": "건수"})
        fig = px.pie(
            occ_df, names="유형", values="건수",
            color_discrete_sequence=["#3498db", "#e74c3c", "#95a5a6", "#f39c12"],
            hole=0.35,
        )
        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate="%{label}<br>%{value:,}건 (%{percent})<extra></extra>",
        )
        fig.update_layout(margin=dict(t=30, b=30))
        st.plotly_chart(fig, width='stretch')
        st.caption("전체 구급출동 CSV 기반 (2017–2022)")
    else:
        st.warning("analytics JSON 없음 — `python scripts/generate_analytics.py` 실행 후 새로고침하세요.")

# ── 탭 2: 정상처리율 수평 막대 ───────────────────────────────────────────
with tab2:
    st.subheader("증상별 정상처리(완료이송)율 (A)")
    min_count = st.slider("최소 샘플 수 (증상별)", 10, 200, 30, step=10)

    if _comp and _comp.get("symptoms"):
        comp_all  = pd.DataFrame(_comp["symptoms"])
        comp_filt = comp_all[comp_all["count"] >= min_count].sort_values("completion_rate_pct").reset_index(drop=True)

        if not comp_filt.empty:
            fig2 = px.bar(
                comp_filt, x="completion_rate_pct", y="symptom",
                orientation="h",
                color="completion_rate_pct",
                color_continuous_scale=[[0, "#e74c3c"], [0.9, "#f39c12"], [1, "#27ae60"]],
                labels={"completion_rate_pct": "정상처리율 (%)", "symptom": "증상", "count": "건수"},
                text=comp_filt["completion_rate_pct"].map("{:.1f}%".format),
                hover_data={"count": True},
            )
            fig2.add_vline(x=95, line_dash="dash", line_color="gray",
                           annotation_text="95%")
            fig2.update_traces(textposition="outside")
            fig2.update_layout(
                coloraxis_showscale=False,
                xaxis=dict(range=[0, 108]),
                margin=dict(t=20, b=20),
            )
            st.plotly_chart(fig2, width='stretch')
            st.caption("전체 구급출동 CSV 기반 (2017–2022)")
        else:
            st.info("조건을 만족하는 증상 없음 — 최소 샘플 수를 낮춰보세요")
    else:
        st.warning("analytics JSON 없음 — `python scripts/generate_analytics.py` 실행 후 새로고침하세요.")

# ── 탭 3: 증상 × 중증도 히트맵 ──────────────────────────────────────────
with tab3:
    st.subheader("주증상 × 중증도 분포 히트맵 (C)")
    top_n = st.slider("표시할 주증상 수", 5, 20, 15)

    if _symsev and _symsev.get("symptoms"):
        sym_list = _symsev["symptoms"][:top_n]
        rows = []
        for s in sym_list:
            for cls, pct in s["severity"].items():
                rows.append({"symptom": s["symptom"], "severity": cls, "pct": pct})

        if rows:
            pivot_df = (
                pd.DataFrame(rows)
                .pivot(index="symptom", columns="severity", values="pct")
                .fillna(0)
            )
            fig3 = px.imshow(
                pivot_df,
                color_continuous_scale="YlOrRd",
                labels=dict(x="중증도", y="주증상", color="비율(%)"),
                text_auto=".1f",
                aspect="auto",
            )
            fig3.update_layout(margin=dict(t=20, b=20))
            st.plotly_chart(fig3, width='stretch')
            st.caption("행 정규화 — 각 증상별 중증도 비율(%) | 전체 구급상황관리 CSV 기반 (2019–2023)")
        else:
            st.info("히트맵 데이터 없음")
    else:
        st.warning("analytics JSON 없음 — `python scripts/generate_analytics.py` 실행 후 새로고침하세요.")

st.divider()

with st.expander("💡 이 시각화로 알 수 있는 것"):
    st.markdown("""
    - **[탭1] 질병외(사고·외상) ≈ 질병**: 거의 절반씩입니다. 외상·사고(질병외)가 질병보다 소폭 많아, 서울 구급 수요가 만성질환뿐 아니라 도시형 사고(낙상, 교통사고 등)에도 상당히 노출돼 있음을 보여줍니다.
    - **[탭2] 대부분 증상 완료이송율 97–100%**: 거의 모든 증상에서 병원 이송이 이루어집니다. 95% 기준선 이하 증상은 비이송 비율이 상대적으로 높습니다.
    - **[탭3] 저혈당 응급, 의식기능저하 응급, 흉통 응급**: 이 증상들은 거의 확실하게 응급 판정을 받으며 즉각 이송이 필요합니다.
    - **[탭3] 무호흡·호흡정지 긴급 + 지연(사망)**: 호흡 관련 증상은 현장 도착 시 이미 심각한 상태가 많아 신속 출동과 기도 처치 역량이 직접적으로 생존율에 영향을 줍니다.
    """)

st.info(
    "**데이터 출처**\n\n"
    "- **탭 1, 2** — 구급출동(A) 서울 한정 (PTN_OCRN_TYPE_NM, PTN_SYM_SE_NM, TRMN_SE_NM) — 전체 CSV\n"
    "- **탭 3** — 구급상황관리(C) 전체 CSV (MAIN_SYM_NM, SRIL_CLSF_NM)\n"
    "- 두 데이터셋은 공통 키가 없어 독립 분석"
)
