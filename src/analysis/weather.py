"""날씨 × 구급 출동 상관 분석.

출력:
  outputs/figures/weather_01_temp_scatter.png  — 기온 × 일별 출동건수 산점도
  outputs/figures/weather_02_correlation.png   — 날씨 변수 × 출동건수 상관계수 막대

단독 실행:  python src/analysis/weather.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config import FIGURES_DIR
from src.data.loader import load_dispatch_sample

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

WEATHER_COLS = {
    "HR_UNIT_ARTMP": "기온(°C)",
    "HR_UNIT_RN":    "강수량(mm)",
    "HR_UNIT_WSPD":  "풍속(m/s)",
    "HR_UNIT_HUM":   "습도(%)",
    "HR_UNIT_SNWFL": "적설량(cm)",
    "HR_UNIT_VSDST": "가시거리(m)",
}


def _build_daily(df):
    """일별 출동건수 + 날씨 평균을 집계한 DataFrame 반환."""
    date_col = "DCLR_YMD"
    if date_col not in df.columns:
        print(f"  [ERROR] {date_col} 컬럼 없음")
        return None

    # 날씨 컬럼 존재 확인
    weather_available = [c for c in WEATHER_COLS if c in df.columns]
    if not weather_available:
        print("  [SKIP] 날씨 컬럼 없음")
        return None

    agg = {"RPTP_NO": "count"} if "RPTP_NO" in df.columns else {"_year": "count"}
    agg.update({c: "mean" for c in weather_available})
    first_key = list(agg.keys())[0]

    daily = df.groupby(date_col).agg(agg).reset_index()
    daily = daily.rename(columns={first_key: "출동건수"})
    return daily


def plot_temp_scatter(daily_df, save_path):
    """기온 × 일별 출동건수 산점도 + 회귀선."""
    col = "HR_UNIT_ARTMP"
    if col not in daily_df.columns:
        print("  [SKIP] 기온 컬럼 없음")
        return

    valid = daily_df[[col, "출동건수"]].dropna()
    x, y = valid[col].values, valid["출동건수"].values

    slope, intercept, r, p, _ = stats.linregress(x, y)
    x_line = np.linspace(x.min(), x.max(), 100)
    y_line = slope * x_line + intercept

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(x, y, alpha=0.4, s=20, color="#3498db", label="일별 데이터")
    ax.plot(x_line, y_line, color="#e74c3c", linewidth=2,
            label=f"회귀선  r={r:.3f}, p={p:.3f}")
    ax.set_title("기온 × 일별 구급 출동 건수", fontsize=14, fontweight="bold")
    ax.set_xlabel("기온 (°C)")
    ax.set_ylabel("일별 출동 건수 (샘플)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name}")


def plot_correlation(daily_df, save_path):
    """날씨 변수별 출동건수 피어슨 상관계수 수평 막대."""
    corrs = {}
    for col, label in WEATHER_COLS.items():
        if col not in daily_df.columns:
            continue
        valid = daily_df[[col, "출동건수"]].dropna()
        if len(valid) < 10:
            continue
        r, p = stats.pearsonr(valid[col], valid["출동건수"])
        corrs[label] = r

    if not corrs:
        print("  [SKIP] 상관계수 계산 불가")
        return

    labels = list(corrs.keys())
    values = list(corrs.values())
    colors = ["#e74c3c" if v > 0 else "#3498db" for v in values]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(labels, values, color=colors, alpha=0.85)
    ax.bar_label(bars, fmt="%.3f", padding=3)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("날씨 변수 × 출동건수 피어슨 상관계수", fontsize=13, fontweight="bold")
    ax.set_xlabel("상관계수 (r)")
    ax.set_xlim(-1, 1)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name}")

    print("\n  [날씨-출동 상관계수]")
    for label, r in sorted(corrs.items(), key=lambda x: abs(x[1]), reverse=True):
        print(f"    {label:12s}: r={r:+.3f}")


def run():
    print("\n[날씨 상관] 데이터 로드 중...")
    df = load_dispatch_sample(nrows_per_year=20_000)

    daily = _build_daily(df)
    if daily is None:
        print("[날씨 상관] 건너뜀\n")
        return

    print(f"  일별 집계: {len(daily):,}일")

    print("\n  차트 저장 중...")
    plot_temp_scatter(daily, FIGURES_DIR / "weather_01_temp_scatter.png")
    plot_correlation(daily, FIGURES_DIR / "weather_02_correlation.png")
    print("[날씨 상관] 완료\n")


if __name__ == "__main__":
    run()
