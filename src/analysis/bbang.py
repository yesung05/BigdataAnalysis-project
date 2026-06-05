"""뺑뺑이(2차·3차 이송) 심층 분석.

출력:
  outputs/figures/bbang_01_yearly_rate.png   — 연도별 2차 이송 발생률 추이
  outputs/figures/bbang_02_district_rate.png — 서울 자치구별 2차 이송 발생률
  outputs/figures/bbang_03_reason.png        — 거부 이유 분류
  outputs/figures/bbang_04_extra_distance.png — 추가 이동 거리 분포

단독 실행:  python src/analysis/bbang.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config import FIGURES_DIR
from src.data.loader import load_dispatch_sample

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


# ── 거부 이유 카테고리화 ──────────────────────────────────────────────
# TRANS2_RSN 실제 값(2022 50k샘플): 응급실(55), 전문의부재(9), 기타(8), 입원실(3), 중환자실(3)
_REASON_MAP = [
    (["응급실"], "응급실 포화"),
    (["병상", "만실", "병실", "입원실", "중환자실", "포화", "입원"], "병상 부족"),
    (["전문의", "진료", "전문", "처치", "치료", "의료", "부재"], "진료 불가"),
    (["거리", "원거리", "접근", "이동"], "거리·접근성"),
    (["기타", "무", "없음", "미상"], "기타"),
]


def _categorize_reason(text):
    if not isinstance(text, str) or text.strip() == "":
        return None
    for keywords, label in _REASON_MAP:
        if any(kw in text for kw in keywords):
            return label
    return "기타"


# ── 분석 함수 ────────────────────────────────────────────────────────

def analyze(df):
    """뺑뺑이 관련 파생 컬럼 추가.

    TRANS2_RSN(거부이유)이 기록된 건만 뺑뺑이로 정의.
    GRNDS2_DSTNC는 정상 이송에서도 값이 있어 단독 판별 기준으로 부적합.
    """
    df = df.copy()
    df["has_trans2"] = df["TRANS2_RSN"].notna()
    df["has_trans3"] = df["TRANS3_RSN"].notna()
    df["extra_dist"] = (df["GRNDS2_DSTNC"].fillna(0) - df["GRNDS_DSTNC"].fillna(0)).clip(lower=0)
    df.loc[~df["has_trans2"], "extra_dist"] = float("nan")
    df["trans2_reason_cat"] = df["TRANS2_RSN"].apply(_categorize_reason)
    return df


def plot_yearly_rate(df, save_path):
    yr = df.groupby("_year")["has_trans2"].agg(["sum", "count"])
    yr["rate"] = yr["sum"] / yr["count"] * 100

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(yr.index, yr["rate"], marker="o", linewidth=2, color="#e74c3c")
    ax.fill_between(yr.index, yr["rate"], alpha=0.15, color="#e74c3c")
    for x, y in zip(yr.index, yr["rate"]):
        ax.annotate(f"{y:.2f}%", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax.set_title("연도별 2차 이송(뺑뺑이) 발생률", fontsize=14, fontweight="bold")
    ax.set_xlabel("연도")
    ax.set_ylabel("발생률 (%)")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f%%"))
    ax.set_xticks(yr.index)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name}")


def plot_district_rate(df, save_path, min_count=200):
    """서울 자치구별(GRNDS_SGG_NM) 2차 이송 발생률.

    데이터가 서울 중심이므로 시군구 레벨로 세분화해 지역별 차이를 분석한다.
    """
    col = "GRNDS_SGG_NM"
    if col not in df.columns:
        print(f"  [SKIP] {col} 컬럼 없음")
        return

    reg = (
        df.groupby(col)["has_trans2"]
        .agg(["sum", "count"])
        .assign(rate=lambda x: x["sum"] / x["count"] * 100)
        .sort_values("rate", ascending=True)
    )
    reg = reg[reg["count"] >= min_count]

    if reg.empty:
        print(f"  [SKIP] min_count={min_count} 조건 만족 지역 없음")
        return

    fig, ax = plt.subplots(figsize=(9, max(6, len(reg) * 0.35)))
    median_rate = reg["rate"].median()
    colors = ["#e74c3c" if r > median_rate else "#3498db" for r in reg["rate"]]
    bars = ax.barh(reg.index, reg["rate"], color=colors)
    ax.bar_label(bars, fmt="%.2f%%", padding=3, fontsize=8)
    ax.axvline(median_rate, linestyle="--", color="gray", alpha=0.6,
               label=f"중앙값 {median_rate:.2f}%")
    ax.set_title("서울 자치구별 2차 이송 발생률\n(데이터: 서울 전체 기준)", fontsize=13, fontweight="bold")
    ax.set_xlabel("발생률 (%)")
    ax.legend(fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name} ({len(reg)}개 자치구)")


def plot_reason(df, save_path):
    reason_s = df.loc[df["has_trans2"], "trans2_reason_cat"].dropna()
    if reason_s.empty:
        print("  [SKIP] 거부 이유 데이터 없음")
        return
    counts = reason_s.value_counts()

    palette = ["#e74c3c", "#e67e22", "#3498db", "#2ecc71", "#95a5a6"]
    colors = palette[: len(counts)]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(counts.index, counts.values, color=colors)
    ax.bar_label(bars, padding=3)
    ax.set_title("2차 이송 거부 이유 분류", fontsize=14, fontweight="bold")
    ax.set_ylabel("건수")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name}")


def plot_extra_distance(df, save_path):
    trans2 = df[df["has_trans2"] & (df["extra_dist"] > 0)]["extra_dist"].clip(upper=50)
    if trans2.empty:
        print("  [SKIP] 추가 거리 데이터 없음")
        return

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(trans2, bins=20, color="#e74c3c", edgecolor="white", alpha=0.8)
    ax.axvline(trans2.median(), linestyle="--", color="#2c3e50", label=f"중앙값 {trans2.median():.1f}km")
    ax.axvline(trans2.mean(), linestyle="-.", color="#7f8c8d", label=f"평균 {trans2.mean():.1f}km")
    ax.set_title("2차 이송 시 추가 이동 거리 분포", fontsize=14, fontweight="bold")
    ax.set_xlabel("추가 거리 (km)")
    ax.set_ylabel("건수")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name}")


def print_summary(df):
    print("\n[뺑뺑이 분석 요약]")
    print(f"  전체 샘플: {len(df):,}건")
    trans2 = df["has_trans2"].sum()
    trans3 = df["has_trans3"].sum()
    print(f"  2차 이송:  {trans2:,}건 ({trans2/len(df)*100:.2f}%)")
    print(f"  3차 이송:  {trans3:,}건 ({trans3/len(df)*100:.2f}%)")

    yr = df.groupby("_year")["has_trans2"].agg(["sum", "count"])
    yr["rate"] = yr["sum"] / yr["count"] * 100
    print("\n  연도별 발생률:")
    for y, row in yr.iterrows():
        print(f"    {y}: {int(row['sum']):>4}건 / {int(row['count']):>6}건 = {row['rate']:.2f}%")

    extra = df.loc[df["has_trans2"] & (df["extra_dist"] > 0), "extra_dist"]
    if not extra.empty:
        print(f"\n  추가 거리 (2차 이송): 평균 {extra.mean():.1f}km, 중앙값 {extra.median():.1f}km")

    reasons = df.loc[df["has_trans2"], "trans2_reason_cat"].value_counts()
    if not reasons.empty:
        print("\n  거부 이유 분류:")
        for k, v in reasons.items():
            print(f"    {k}: {v}건")


def run():
    print("\n[뺑뺑이 분석] 데이터 로드 중...")
    df_raw = load_dispatch_sample(nrows_per_year=20_000)
    df = analyze(df_raw)

    print_summary(df)

    print("\n  차트 저장 중...")
    plot_yearly_rate(df, FIGURES_DIR / "bbang_01_yearly_rate.png")
    plot_district_rate(df, FIGURES_DIR / "bbang_02_district_rate.png")
    plot_reason(df, FIGURES_DIR / "bbang_03_reason.png")
    plot_extra_distance(df, FIGURES_DIR / "bbang_04_extra_distance.png")
    print("[뺑뺑이 분석] 완료\n")


if __name__ == "__main__":
    run()
