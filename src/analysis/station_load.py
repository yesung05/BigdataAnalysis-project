"""소방서(안전센터)별 출동 부하 분석 및 지도 시각화.

출력:
  outputs/figures/station_load_bar.png  — 상위 30개 안전센터 출동 건수 막대
  outputs/figures/station_load_map.html — Folium 버블 지도

단독 실행:  python src/analysis/station_load.py
"""
import math
import sys
from pathlib import Path

import folium
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config import FIGURES_DIR
from src.data.loader import load_dispatch_sample, load_station_coords
from src.data.preprocess import normalize_center_name

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# 안전센터가 아닌 출동 분류 코드 제외 목록
_EXCLUDE_CNTR = {"현장대응단"}


def calc_station_load(df):
    """안전센터별 출동 건수 집계. 현장대응단 등 비센터 항목 제외."""
    filtered = df[~df["CNTR_NM"].isin(_EXCLUDE_CNTR)]
    excluded = len(df) - len(filtered)
    if excluded > 0:
        print(f"  제외: {excluded:,}건 ({', '.join(_EXCLUDE_CNTR)} 항목)")
    load = filtered.groupby("CNTR_NM").size().reset_index(name="출동건수")
    load = load.sort_values("출동건수", ascending=False)
    print(f"  집계된 안전센터: {len(load):,}개")
    return load


def join_with_coords(load_df, station_df):
    """출동 부하 DataFrame에 소방서 좌표 LEFT JOIN (정규화 키)."""
    load_df = load_df.copy()
    station_df = station_df.copy()

    load_df["_key"] = load_df["CNTR_NM"].apply(normalize_center_name)
    station_df["_key"] = station_df["기관명"].apply(normalize_center_name)

    coord_lut = (
        station_df.drop_duplicates("_key")
        .set_index("_key")[["위도", "경도", "유형", "기관명"]]
    )

    merged = load_df.join(coord_lut, on="_key", how="left")
    matched = merged["위도"].notna().sum()
    total = len(merged)
    print(f"  [JOIN] {matched:,}/{total:,}개 센터 좌표 매칭 ({matched/total*100:.1f}%)")
    return merged


def plot_bar(load_df, save_path, top_n=30):
    top = load_df.head(top_n)
    fig, ax = plt.subplots(figsize=(10, 8))
    bars = ax.barh(top["CNTR_NM"][::-1], top["출동건수"][::-1], color="#e74c3c", alpha=0.85)
    ax.bar_label(bars, padding=3, fontsize=7)
    ax.set_title(f"상위 {top_n}개 안전센터 출동 건수 (샘플 기준)", fontsize=14, fontweight="bold")
    ax.set_xlabel("출동 건수 (샘플)")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  저장: {save_path.name}")


def make_bubble_map(joined_df, save_path):
    """Folium CircleMarker 버블 지도 생성."""
    valid = joined_df.dropna(subset=["위도", "경도"]).copy()
    if valid.empty:
        print("  [SKIP] 좌표 매칭 데이터 없어 지도 생성 불가")
        return

    center_lat = valid["위도"].mean()
    center_lon = valid["경도"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="CartoDB positron")

    max_count = valid["출동건수"].max()
    for _, row in valid.iterrows():
        radius = math.sqrt(row["출동건수"] / max_count) * 20 + 3
        folium.CircleMarker(
            location=[row["위도"], row["경도"]],
            radius=radius,
            color="#c0392b",
            fill=True,
            fill_color="#e74c3c",
            fill_opacity=0.6,
            popup=folium.Popup(
                f"<b>{row['CNTR_NM']}</b><br>출동: {int(row['출동건수']):,}건",
                max_width=200,
            ),
            tooltip=row["CNTR_NM"],
        ).add_to(m)

    m.save(str(save_path))
    print(f"  저장: {save_path.name} ({len(valid):,}개 마커)")


def run():
    print("\n[소방서 출동 부하] 데이터 로드 중...")
    df = load_dispatch_sample(nrows_per_year=20_000)
    stations = load_station_coords()

    load_df = calc_station_load(df)
    joined = join_with_coords(load_df, stations)

    print("\n  차트 저장 중...")
    plot_bar(load_df, FIGURES_DIR / "station_load_bar.png")
    make_bubble_map(joined, FIGURES_DIR / "station_load_map.html")
    print("[소방서 출동 부하] 완료\n")


if __name__ == "__main__":
    run()
