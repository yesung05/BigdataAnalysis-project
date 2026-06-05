"""시계열 트렌드 분석.

출력:
  outputs/figures/ts_01_yearly_dispatch.png — 연도별 출동 추이 (실제 파일 행수 기준)
  outputs/figures/ts_02_monthly_seoul.png   — 서울 월별 출동 추이 2022~2024

단독 실행:  python src/analysis/time_series.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config import FIGURES_DIR, DATA_DIR
from src.data.loader import load_seoul_dispatch_xlsx

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

COLORS = ["#2ecc71", "#3498db", "#e74c3c", "#9b59b6", "#f39c12", "#1abc9c"]


def _count_file_rows(csv_path):
    """CSV 파일의 데이터 행수를 카운트 (헤더 제외)."""
    try:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f) - 1
    except Exception:
        return None


def plot_yearly_dispatch(save_path):
    """연도별 실제 출동 건수 (구급출동현황 파일 행수 기준)."""
    dispatch_dir = DATA_DIR / "구급출동현황"
    years_data = {}

    for yr in range(2017, 2023):
        fpath = dispatch_dir / f"구급출동_{yr}.csv"
        if fpath.exists():
            count = _count_file_rows(fpath)
            if count and count > 0:
                years_data[yr] = count

    if not years_data:
        print("  [SKIP] 구급출동 CSV 파일 없음")
        return

    years = list(years_data.keys())
    counts = list(years_data.values())

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(years, counts, color="#3498db", alpha=0.8, width=0.5)

    # 바 위에 만 단위 주석
    for yr, cnt in zip(years, counts):
        ax.annotate(
            f"{cnt/10000:.0f}만",
            (yr, cnt),
            textcoords="offset points",
            xytext=(0, 6),
            ha="center",
            fontsize=9,
            color="#2c3e50",
        )

    # 추세선
    z = np.polyfit(years, counts, 1)
    p = np.poly1d(z)
    ax.plot(years, p(years), linestyle="--", color="#e74c3c", linewidth=1.5, alpha=0.7, label="추세선")

    ax.set_title("연도별 구급 출동 건수 추이 (전체 건수)", fontsize=14, fontweight="bold")
    ax.set_xlabel("연도")
    ax.set_ylabel("출동 건수")
    ax.set_xticks(years)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x/10000)}만"))
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name}")
    print(f"  연도별 건수: { {y: f'{c:,}' for y, c in years_data.items()} }")


def plot_monthly_seoul(sheets, save_path):
    """서울시 월별 구급 출동 추이 (2022~2024).

    서울시 Excel 구조 (서울소방재난본부 공식 양식):
      - 헤더행: 기관명, 1월, 2월, ..., 12월
      - 첫 번째 데이터 행(index 0): 서울청 합계 (전체 합계)
      - 이후 행: 각 소방서 및 안전센터 상세 데이터
    """
    years_data = {}
    for sheet_name, df in sheets.items():
        if df.empty:
            continue
        # 1~12월 컬럼 찾기
        month_cols = [
            c for c in df.columns
            if str(c).replace("월", "").strip().isdigit()
            and 1 <= int(str(c).replace("월", "").strip()) <= 12
        ]
        if len(month_cols) < 12:
            continue

        # 첫 번째 행이 서울청(전체 합계)임 — 직접 사용
        # 주의: str.contains("계")로 검색하면 구이름에 "계"가 포함된 행도 매칭되어 오류 발생
        total_row = df.iloc[[0]]

        monthly = total_row[month_cols].values.flatten()
        try:
            monthly = [float(v) for v in monthly]
            year = str(sheet_name).replace("년", "").strip()
            years_data[year] = monthly
        except (ValueError, TypeError):
            continue

    if not years_data:
        print("  [SKIP] 서울 Excel에서 월별 데이터 파싱 실패")
        return

    months = list(range(1, 13))
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, (year, data) in enumerate(sorted(years_data.items())):
        months_valid = months[: len(data)]
        ax.plot(
            months_valid,
            data[: len(months_valid)],
            marker="o",
            linewidth=2,
            label=f"{year}년",
            color=COLORS[i % len(COLORS)],
        )
        # 최고점 주석
        peak_idx = int(np.argmax(data))
        ax.annotate(
            f"{int(data[peak_idx]):,}",
            (months_valid[peak_idx], data[peak_idx]),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=8,
            color=COLORS[i % len(COLORS)],
        )

    ax.set_title("서울시 월별 구급 출동 건수 (2022~2024)", fontsize=14, fontweight="bold")
    ax.set_xlabel("월")
    ax.set_ylabel("출동 건수")
    ax.set_xticks(months)
    ax.set_xticklabels([f"{m}월" for m in months])
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name}")


def run():
    print("\n[시계열 분석] 연도별 출동 건수 집계 중...")
    plot_yearly_dispatch(FIGURES_DIR / "ts_01_yearly_dispatch.png")

    print("\n[시계열 분석] 서울시 Excel 로드 중...")
    try:
        sheets = load_seoul_dispatch_xlsx()
        plot_monthly_seoul(sheets, FIGURES_DIR / "ts_02_monthly_seoul.png")
    except Exception as e:
        print(f"  [ERROR] 서울 Excel 로드 실패: {e}")

    print("[시계열 분석] 완료\n")


if __name__ == "__main__":
    run()
