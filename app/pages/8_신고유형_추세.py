"""8. 119 신고유형 추세 — 2011–2023 연도별 유형별 변화."""
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

from cache import get_call_types

st.set_page_config(page_title="119 신고유형 추세", layout="wide")
st.title("📞 119 신고유형 추세 (2011–2023)")
st.caption("소방청 119신고 전화 유형 통계 — 화재·구조·구급·기타 신고 유형이 어떻게 변해왔는가")

# ── 데이터 로드 및 전처리 ───────────────────────────────────────────────────
raw = get_call_types()

# 유선·무선을 연도별로 합산
MAIN_CATS = ["화재", "구조", "구급", "대민출동 및 기타", "장난전화", "무응답", "오접속"]
avail = [c for c in MAIN_CATS if c in raw.columns]

yr_col = "연도별"
agg = raw.groupby(yr_col)[avail].sum().reset_index()
agg = agg.sort_values(yr_col)

# 집계: 핵심 신고(화재·구조·구급) vs 비업무 신호
agg["핵심신고"] = agg[["화재", "구조", "구급"]].sum(axis=1)
NON_EMERGENCY = [c for c in ["장난전화", "무응답", "오접속"] if c in agg.columns]
if NON_EMERGENCY:
    agg["비업무신호"] = agg[NON_EMERGENCY].sum(axis=1)

tab1, tab2, tab3 = st.tabs(["유형별 추이", "비율 변화", "원본 데이터"])

# ── 탭 1: 스택 영역 차트 ────────────────────────────────────────────────────
with tab1:
    st.subheader("연도별 119 신고 건수 (유형별 누적)")

    stack_cols = [c for c in ["화재", "구조", "구급", "대민출동 및 기타"] if c in agg.columns]
    if stack_cols:
        long = agg[[yr_col] + stack_cols].melt(
            id_vars=yr_col, var_name="유형", value_name="건수"
        )
        fig1 = px.area(
            long,
            x=yr_col,
            y="건수",
            color="유형",
            color_discrete_map={
                "화재": "#e74c3c",
                "구조": "#f39c12",
                "구급": "#3498db",
                "대민출동 및 기타": "#95a5a6",
            },
            labels={yr_col: "연도", "건수": "신고 건수"},
        )
        fig1.update_layout(
            hovermode="x unified",
            yaxis=dict(tickformat=","),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig1, width='stretch')

        c1, c2, c3 = st.columns(3)
        if "구급" in agg.columns:
            c1.metric("2023년 구급 신고", f"{int(agg.loc[agg[yr_col]==agg[yr_col].max(), '구급'].values[0]):,}건")
        if "화재" in agg.columns:
            c2.metric("2023년 화재 신고", f"{int(agg.loc[agg[yr_col]==agg[yr_col].max(), '화재'].values[0]):,}건")
        if "구조" in agg.columns:
            c3.metric("2023년 구조 신고", f"{int(agg.loc[agg[yr_col]==agg[yr_col].max(), '구조'].values[0]):,}건")

    with st.expander("💡 이 시각화로 알 수 있는 것"):
        st.markdown("""
        - **구급 신고가 압도적으로 多**: 2011년 대비 2023년까지 구급 신고 건수가 지속적으로 증가하고 있어, 고령화·도시화에 따른 의료 응급 수요 증가를 반영합니다.
        - **화재 신고는 상대적으로 안정**: 소방 예방 활동 강화와 건물 방화 기준 강화로 화재 발생 신고는 큰 변화 없이 유지됩니다.
        - **대민출동 및 기타 신고**: 구급·구조 이외의 민원 출동(동물구조, 잠금해제 등)이 꾸준히 발생하고 있어 소방 인력 소모 요인이 됩니다.
        """)

# ── 탭 2: 비율 변화 막대 ────────────────────────────────────────────────────
with tab2:
    st.subheader("연도별 신고 유형 비율 변화")

    ratio_cols = [c for c in ["화재", "구조", "구급", "대민출동 및 기타"] if c in agg.columns]
    if ratio_cols:
        ratio_df = agg[[yr_col] + ratio_cols].copy()
        total = ratio_df[ratio_cols].sum(axis=1)
        for c in ratio_cols:
            ratio_df[c] = ratio_df[c] / total * 100

        long2 = ratio_df.melt(id_vars=yr_col, var_name="유형", value_name="비율(%)")
        fig2 = px.bar(
            long2,
            x=yr_col,
            y="비율(%)",
            color="유형",
            barmode="stack",
            color_discrete_map={
                "화재": "#e74c3c",
                "구조": "#f39c12",
                "구급": "#3498db",
                "대민출동 및 기타": "#95a5a6",
            },
            labels={yr_col: "연도", "비율(%)": "비율 (%)"},
            text_auto=".1f",
        )
        fig2.update_traces(textposition="inside", textfont_size=10)
        fig2.update_layout(
            yaxis=dict(range=[0, 100]),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig2, width='stretch')

    if "비업무신호" in agg.columns and "핵심신고" in agg.columns:
        st.subheader("핵심신고 vs 비업무신호 추이")
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=agg[yr_col], y=agg["핵심신고"],
            mode="lines+markers", name="핵심신고(화재+구조+구급)",
            line=dict(color="#2ecc71", width=2),
            fill="tozeroy", fillcolor="rgba(46,204,113,0.1)",
        ))
        fig3.add_trace(go.Scatter(
            x=agg[yr_col], y=agg["비업무신호"],
            mode="lines+markers", name="비업무신호(장난+오접속+무응답)",
            line=dict(color="#e74c3c", width=2, dash="dash"),
        ))
        fig3.update_layout(
            yaxis=dict(tickformat=","),
            hovermode="x unified",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig3, width='stretch')
        st.caption("비업무신호가 높을수록 실제 출동 가능한 인력이 분산됨")

    with st.expander("💡 이 시각화로 알 수 있는 것"):
        st.markdown("""
        - **구급 비중 지속 증가**: 전체 신고 중 구급이 차지하는 비율이 해마다 늘어나고 있어 소방의 '의료 응급 기관화' 추세가 뚜렷합니다.
        - **비업무신호(장난전화·오접속·무응답)**: 연간 수백만 건의 비업무 신호가 소방 무선·유선 통신을 점유합니다. 특히 오접속이 장난전화보다 압도적으로 많아 통신 인프라 관리 중요성을 보여줍니다.
        - **정책 시사점**: 구급 비중이 높아질수록 119는 단순 소방·구조를 넘어 응급의료 전문 인력 확충이 필요함을 데이터가 뒷받침합니다.
        """)

# ── 탭 3: 원본 데이터 ────────────────────────────────────────────────────────
with tab3:
    st.subheader("연도별 집계 원본")
    st.dataframe(agg.set_index(yr_col), width='stretch')
    st.caption("유선 + 무선 합산값. 출처: 소방청 119신고 전화 유형 통계 (2011–2023)")
