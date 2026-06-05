"""증상 분석: 발생 유형, 이송률, 증상×중증도 히트맵.

출력:
  outputs/figures/symptom_01_transport_rate.png   — 증상별 정상처리(완료이송)율
  outputs/figures/symptom_02_type_pie.png         — 환자 발생 유형 파이차트
  outputs/figures/symptom_03_severity_heatmap.png — 증상×중증도 히트맵 (구급상황관리)

단독 실행:  python src/analysis/symptom.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config import FIGURES_DIR
from src.data.loader import load_dispatch_sample, load_mgmt_sample

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# TRMN_SE_NM 실제 값(구급출동현황): 정상(96%), 취소, 오인, 기타, 거짓
# '정상' = 정상 이송 완료 (출동 성공)
_TRANSPORT_VALUE = "정상"


def plot_transport_rate(df, save_path, min_count=30):
    """PTN_SYM_SE_NM(증상구분) × 정상처리 여부 → 완료이송율 막대."""
    col = "PTN_SYM_SE_NM"
    if col not in df.columns:
        print(f"  [SKIP] {col} 컬럼 없음")
        return
    if "TRMN_SE_NM" not in df.columns:
        print("  [SKIP] TRMN_SE_NM 컬럼 없음")
        return

    df = df.copy()
    df["is_normal"] = (df["TRMN_SE_NM"] == _TRANSPORT_VALUE).astype(int)
    grp = df.groupby(col).agg(
        건수=("is_normal", "count"),
        완료건수=("is_normal", "sum"),
    )
    grp = grp[grp["건수"] >= min_count].copy()
    grp["완료율"] = grp["완료건수"] / grp["건수"] * 100
    grp = grp.sort_values("완료율")

    if grp.empty:
        print(f"  [SKIP] {col} min_count={min_count} 조건 만족 행 없음")
        return

    fig, ax = plt.subplots(figsize=(9, 6))
    colors = ["#27ae60" if r >= 95 else "#e67e22" if r >= 85 else "#e74c3c" for r in grp["완료율"]]
    bars = ax.barh(grp.index, grp["완료율"], color=colors, alpha=0.85)
    ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=8)
    ax.axvline(95, linestyle="--", color="gray", alpha=0.5, label="95%")
    ax.set_title("증상 구분별 정상처리(완료이송)율", fontsize=14, fontweight="bold")
    ax.set_xlabel("정상처리율 (%) — TRMN_SE_NM='정상'")
    ax.set_xlim(0, 105)
    ax.legend(fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name}")


def plot_type_pie(df, save_path):
    """PTN_OCRN_TYPE_NM(환자발생유형) 파이차트 (3개 카테고리)."""
    col = "PTN_OCRN_TYPE_NM"
    if col not in df.columns:
        print(f"  [SKIP] {col} 컬럼 없음")
        return

    counts = df[col].value_counts()
    if counts.empty:
        print(f"  [SKIP] {col} 데이터 없음")
        return

    palette = ["#3498db", "#e74c3c", "#95a5a6", "#f39c12", "#2ecc71"]
    colors = palette[: len(counts)]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        counts.values,
        labels=counts.index,
        autopct="%1.1f%%",
        colors=colors,
        startangle=140,
        pctdistance=0.75,
        textprops={"fontsize": 12},
    )
    for at in autotexts:
        at.set_fontsize(11)
        at.set_fontweight("bold")
    ax.set_title("환자 발생 유형 분포", fontsize=14, fontweight="bold")
    # 범례에 건수도 표시
    legend_labels = [f"{lbl} ({cnt:,}건)" for lbl, cnt in zip(counts.index, counts.values)]
    ax.legend(wedges, legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.08), fontsize=10)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name}")


def plot_severity_heatmap(mgmt_df, save_path, top_n=15):
    """MAIN_SYM_NM × SRIL_CLSF_NM 히트맵 (구급상황관리)."""
    valid = mgmt_df.dropna(subset=["MAIN_SYM_NM", "SRIL_CLSF_NM"]).copy()
    if valid.empty:
        print("  [SKIP] 증상×중증도 유효 데이터 없음")
        return

    top_syms = valid["MAIN_SYM_NM"].value_counts().head(top_n).index
    filtered = valid[valid["MAIN_SYM_NM"].isin(top_syms)]

    pivot = (
        filtered.groupby(["MAIN_SYM_NM", "SRIL_CLSF_NM"])
        .size()
        .unstack(fill_value=0)
    )
    # 행 정규화 → 비율로 히트맵
    pivot_norm = pivot.div(pivot.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(10, 7))
    sns.heatmap(
        pivot_norm,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        linewidths=0.5,
        cbar_kws={"label": "비율 (%)"},
        ax=ax,
    )
    ax.set_title(f"주증상 × 중증도 분포 (상위 {top_n}개 증상, %)", fontsize=13, fontweight="bold")
    ax.set_xlabel("중증도")
    ax.set_ylabel("주증상")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name}")


def run():
    print("\n[증상 분석] 구급출동 데이터 로드 중...")
    dispatch_df = load_dispatch_sample(nrows_per_year=20_000)

    print("\n[증상 분석] 구급상황관리 데이터 로드 중...")
    mgmt_df = load_mgmt_sample(nrows_per_year=10_000)

    print("\n  차트 저장 중...")
    plot_transport_rate(dispatch_df, FIGURES_DIR / "symptom_01_transport_rate.png")
    plot_type_pie(dispatch_df, FIGURES_DIR / "symptom_02_type_pie.png")
    plot_severity_heatmap(mgmt_df, FIGURES_DIR / "symptom_03_severity_heatmap.png")
    print("[증상 분석] 완료\n")


# 호환성 유지용 함수 (원본 스텁 대체)
def top_symptoms(df, n=20):
    return df["MAIN_SYM_NM"].value_counts().head(n)


if __name__ == "__main__":
    run()
