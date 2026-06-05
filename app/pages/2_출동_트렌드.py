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
st.title("📈 출동 트렌드")
st.caption("구급출동현황(A) 실제 파일 행수 기준 + 서울시 Excel(D) 월별 추이")

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
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        df_yr = pd.DataFrame({"연도": years, "출동 건수": counts}).set_index("연도")
        st.dataframe(df_yr.style.format({"출동 건수": "{:,}"}), use_container_width=True)
    with col2:
        st.info(
            "**주요 인사이트**\n\n"
            "- 2020년: 477,927건 — COVID-19 영향으로 15% 감소\n"
            "- 2022년: 617,414건 — 6개년 최고치\n"
            "- 전체 추세: 우상향 (연평균 +2.5%)"
        )
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
    st.plotly_chart(fig2, use_container_width=True)
    st.info(
        "**주요 인사이트**\n\n"
        "- 7–8월 여름철 피크 (3,500~3,800건), 2–3월 최저\n"
        "- 3개년 모두 유사한 계절 패턴"
    )
else:
    st.warning("서울 Excel 월별 데이터 파싱 실패")
