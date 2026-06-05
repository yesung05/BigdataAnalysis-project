"""4. 증상 분석 — Plotly 인터랙티브."""
import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR = _PAGES_DIR.parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from cache import get_dispatch, get_mgmt

st.set_page_config(page_title="증상 분석", layout="wide")
st.title("🏥 증상 분석")
st.caption(
    "구급출동(A) × 구급상황관리(C) 독립 분석  "
    "| TRMN_SE_NM='정상'이 완료이송 (값 '이송'은 존재하지 않음)"
)

dispatch_df = get_dispatch()
mgmt_df = get_mgmt()

# ── 탭 구성 ───────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["환자 발생 유형", "증상별 정상처리율", "주증상 × 중증도"])

# ── 탭 1: 파이차트 ─────────────────────────────────────────────────────────
with tab1:
    st.subheader("환자 발생 유형 분포 (A)")
    col = "PTN_OCRN_TYPE_NM"
    if col in dispatch_df.columns:
        counts = dispatch_df[col].value_counts().reset_index()
        counts.columns = ["유형", "건수"]
        fig = px.pie(
            counts, names="유형", values="건수",
            color_discrete_sequence=["#3498db", "#e74c3c", "#95a5a6", "#f39c12"],
            hole=0.35,
        )
        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate="%{label}<br>%{value:,}건 (%{percent})<extra></extra>",
        )
        fig.update_layout(margin=dict(t=30, b=30))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"{col} 컬럼 없음")

# ── 탭 2: 정상처리율 수평 막대 ───────────────────────────────────────────
with tab2:
    st.subheader("증상별 정상처리(완료이송)율 (A)")
    col_sym = "PTN_SYM_SE_NM"
    col_trm = "TRMN_SE_NM"
    min_count = st.slider("최소 샘플 수 (증상별)", 10, 200, 30, step=10)

    if col_sym in dispatch_df.columns and col_trm in dispatch_df.columns:
        df2 = dispatch_df.copy()
        df2["is_normal"] = (df2[col_trm] == "정상").astype(int)
        grp = df2.groupby(col_sym).agg(
            건수=("is_normal", "count"),
            완료건수=("is_normal", "sum"),
        )
        grp = grp[grp["건수"] >= min_count].copy()
        grp["완료율"] = grp["완료건수"] / grp["건수"] * 100
        grp = grp.sort_values("완료율").reset_index()

        if not grp.empty:
            fig2 = px.bar(
                grp, x="완료율", y=col_sym,
                orientation="h",
                color="완료율",
                color_continuous_scale=[[0, "#e74c3c"], [0.9, "#f39c12"], [1, "#27ae60"]],
                labels={"완료율": "정상처리율 (%)", col_sym: "증상"},
                text=grp["완료율"].map("{:.1f}%".format),
                hover_data={"건수": True, "완료건수": True},
            )
            fig2.add_vline(x=95, line_dash="dash", line_color="gray",
                           annotation_text="95%")
            fig2.update_traces(textposition="outside")
            fig2.update_layout(
                coloraxis_showscale=False,
                xaxis=dict(range=[0, 108]),
                margin=dict(t=20, b=20),
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("조건을 만족하는 증상 없음 — 최소 샘플 수를 낮춰보세요")
    else:
        st.warning(f"{col_sym} 또는 {col_trm} 컬럼 없음")

# ── 탭 3: 증상 × 중증도 히트맵 ──────────────────────────────────────────
with tab3:
    st.subheader("주증상 × 중증도 분포 히트맵 (C)")
    top_n = st.slider("표시할 주증상 수", 5, 20, 15)

    col_sym2 = "MAIN_SYM_NM"
    col_sev = "SRIL_CLSF_NM"
    if col_sym2 in mgmt_df.columns and col_sev in mgmt_df.columns:
        valid = mgmt_df.dropna(subset=[col_sym2, col_sev])
        top_syms = valid[col_sym2].value_counts().head(top_n).index
        filtered = valid[valid[col_sym2].isin(top_syms)]

        pivot = (
            filtered.groupby([col_sym2, col_sev])
            .size()
            .unstack(fill_value=0)
        )
        pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100

        fig3 = px.imshow(
            pivot_pct,
            color_continuous_scale="YlOrRd",
            labels=dict(x="중증도", y="주증상", color="비율(%)"),
            text_auto=".1f",
            aspect="auto",
        )
        fig3.update_layout(margin=dict(t=20, b=20))
        st.plotly_chart(fig3, use_container_width=True)
        st.caption("행 정규화 — 각 증상별 중증도 비율(%)을 표시")
    else:
        st.warning(f"{col_sym2} 또는 {col_sev} 컬럼 없음")

st.divider()
st.info(
    "**데이터 출처**\n\n"
    "- **탭 1, 2** — 구급출동(A) 샘플 (PTN_SYM_SE_NM, PTN_OCRN_TYPE_NM, TRMN_SE_NM)\n"
    "- **탭 3** — 구급상황관리(C) 샘플 (MAIN_SYM_NM, SRIL_CLSF_NM)\n"
    "- 두 데이터셋은 공통 키가 없어 독립 분석"
)
