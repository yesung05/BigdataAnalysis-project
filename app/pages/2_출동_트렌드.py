"""2. 출동 트렌드 — Plotly 인터랙티브."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR = _PAGES_DIR.parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from cache import get_seoul_excel
from src.analysis.time_series import _count_file_rows
from src.config import DATASETS

st.set_page_config(page_title="출동 트렌드", layout="wide")
st.title("📈 서울 구급 수요 현황")
st.caption("구급출동현황(A) 전국 연도별 실 건수 + 서울시 Excel(D) 월별 추이 | 6년간 15% 증가")

# ── 연도별 출동 건수 ────────────────────────────────────────────────────────
st.subheader("연도별 구급 출동 건수")

dispatch_dir = DATASETS["구급출동"]["dir"]
year_counts = {}
for yr in range(2017, 2023):
    fpath = dispatch_dir / f"구급출동_{yr}.csv"
    if fpath.exists():
        cnt = _count_file_rows(fpath)
        if cnt:
            year_counts[yr] = cnt

if year_counts:
    years = list(year_counts.keys())
    counts = list(year_counts.values())

    z = np.polyfit(years, counts, 1)
    trend_y = [int(np.poly1d(z)(yr)) for yr in years]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=counts,
        name="출동 건수",
        marker_color="#3498db",
        text=[f"{c:,}" for c in counts],
        textposition="outside",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=trend_y,
        name="추세선",
        mode="lines",
        line=dict(color="#e74c3c", width=2, dash="dash"),
    ))
    fig.update_layout(
        xaxis=dict(tickvals=years, ticktext=[str(y) for y in years]),
        yaxis=dict(tickformat=","),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig, width='stretch')

    col1, col2 = st.columns(2)
    with col1:
        df_yr = pd.DataFrame({"연도": years, "출동 건수": counts}).set_index("연도")
        st.dataframe(df_yr.style.format({"출동 건수": "{:,}"}), width='stretch')
    with col2:
        st.info(
            "**주요 인사이트**\n\n"
            "- 2020년: 477,927건 — COVID-19 영향으로 15% 감소\n"
            "- 2022년: 617,414건 — 6개년 최고치\n"
            "- 전체 추세: 우상향 (연평균 +2.5%)"
        )

    with st.expander("💡 이 시각화로 알 수 있는 것"):
        st.markdown("""
        - **2020년 급락 (약 48만 건)**: 직전 연도(2019년 약 54만 건) 대비 약 11% 감소. COVID-19 사회적 거리두기로 외출·집합 행사가 줄어 사고성 출동이 감소했습니다.
        - **2022년 역대 최고 (약 62만 건)**: 엔데믹 전환과 고령 인구 증가가 겹쳐 2017년 대비 약 15% 증가. 6년 최고치로 소방 자원 수요가 구조적으로 확대되고 있음을 보여줍니다.
        - **우상향 추세선**: 2020년 예외를 제외하면 연평균 약 2–3%씩 증가. 고령화가 지속되는 한 이 추세는 이어질 가능성이 높아 중장기 소방 인력·장비 확충의 근거로 활용됩니다.
        """)
else:
    st.warning("구급출동 CSV 파일을 찾을 수 없습니다.")

st.divider()

# ── 서울 월별 ──────────────────────────────────────────────────────────────
st.subheader("서울시 월별 구급 출동 건수 (2022 – 2024)")

sheets = get_seoul_excel()
monthly_data = {}
for sheet_name, df in sheets.items():
    month_cols = [
        c for c in df.columns
        if str(c).replace("월", "").strip().isdigit()
        and 1 <= int(str(c).replace("월", "").strip()) <= 12
    ]
    if len(month_cols) < 1:
        continue
    row = df.iloc[0]
    vals = []
    for mc in sorted(month_cols, key=lambda x: int(str(x).replace("월", "").strip())):
        try:
            vals.append(int(float(row[mc])))
        except (ValueError, TypeError):
            vals.append(None)
    if vals:
        monthly_data[str(sheet_name).replace("년", "").strip()] = vals

if monthly_data:
    months = list(range(1, 13))
    colors = ["#2ecc71", "#3498db", "#e74c3c"]

    fig2 = go.Figure()
    for i, (year, data) in enumerate(sorted(monthly_data.items())):
        month_x = months[: len(data)]
        fig2.add_trace(go.Scatter(
            x=month_x, y=data[: len(month_x)],
            name=f"{year}년",
            mode="lines+markers",
            line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=6),
            hovertemplate="%{y:,}건<extra>%{fullData.name}</extra>",
        ))
    fig2.update_layout(
        xaxis=dict(
            tickvals=months,
            ticktext=[f"{m}월" for m in months],
        ),
        yaxis=dict(tickformat=","),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig2, width='stretch')
    st.info(
        "**주요 인사이트**\n\n"
        "- 7–8월 여름철 피크 (3,500~3,800건), 2–3월 최저\n"
        "- 3개년 모두 유사한 계절 패턴"
    )

    with st.expander("💡 이 시각화로 알 수 있는 것"):
        st.markdown("""
        - **7–8월 피크 (약 3,688–3,781건)**: 폭염 온열질환과 야외 활동 사고가 집중돼 2월 최저치(약 2,660–2,700건) 대비 약 40% 많습니다. 매년 여름 구급대 증편 배치의 실증 근거입니다.
        - **2022년 3월 이상 급등 (~3,460건)**: 같은 달 타 연도 대비 눈에 띄게 높아 특이치입니다. 해당 월의 특수 상황(한파 해제 후 갑작스러운 외출 증가, 집단감염 등)을 교차 확인할 필요가 있습니다.
        - **2024년 전반적 하향**: 2022·2023년보다 절대 수치가 낮게 형성되고 있습니다. 데이터 수집 시점 차이(연말 미집계) 또는 실제 수요 변화인지 추가 검토가 필요합니다.
        - **계절 패턴 재현성**: 3개 연도 모두 여름 피크→겨울 저점의 U자 곡선을 반복해, 계절별 구급 자원 배치를 예측 가능한 방식으로 기획할 수 있습니다.
        """)
else:
    st.warning("서울 Excel 월별 데이터 파싱 실패")
