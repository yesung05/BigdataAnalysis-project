"""공통 @st.cache_data 래퍼. 모든 페이지에서 import해서 사용."""
import sys
from pathlib import Path

import streamlit as st

_PROJ_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJ_DIR))

import pandas as pd

from src.data.loader import (
    load_dispatch_sample,
    load_mgmt_sample,
    load_seoul_dispatch_xlsx,
    load_station_coords,
)


@st.cache_data(show_spinner="구급출동 데이터 로드 중...")
def get_dispatch():
    return load_dispatch_sample(nrows_per_year=20_000)


@st.cache_data(show_spinner="소방서 좌표 로드 중...")
def get_station_coords():
    return load_station_coords()


@st.cache_data(show_spinner="구급상황관리 데이터 로드 중...")
def get_mgmt():
    return load_mgmt_sample(nrows_per_year=10_000)


@st.cache_data(show_spinner="서울 Excel 로드 중...")
def get_seoul_excel():
    return load_seoul_dispatch_xlsx()


@st.cache_data(show_spinner="전체 CSV에서 자치구별 2차 이송률 집계 중… (최초 1회)")
def get_district_transfer_rate():
    import pandas as pd
    from src.config import DATASETS

    cfg = DATASETS["구급출동"]
    frames = []
    for yr in cfg["years"]:
        fpath = cfg["dir"] / f"구급출동_{yr}.csv"
        if not fpath.exists():
            continue
        chunk = pd.read_csv(
            fpath,
            usecols=["GRNDS_CTPV_NM", "GRNDS_SGG_NM", "TRANS2_RSN"],
            encoding=cfg["encoding"],
            low_memory=False,
        )
        chunk = chunk[chunk["GRNDS_CTPV_NM"].str.contains("서울", na=False)]
        frames.append(chunk[["GRNDS_SGG_NM", "TRANS2_RSN"]])

    if not frames:
        return pd.DataFrame(columns=["자치구", "출동건수", "이송2차건수", "발생률"])

    combined = pd.concat(frames, ignore_index=True)
    combined["has_trans2"] = combined["TRANS2_RSN"].notna()
    grp = (
        combined.groupby("GRNDS_SGG_NM")
        .agg(출동건수=("has_trans2", "count"), 이송2차건수=("has_trans2", "sum"))
        .reset_index()
        .rename(columns={"GRNDS_SGG_NM": "자치구"})
    )
    grp["발생률"] = grp["이송2차건수"] / grp["출동건수"] * 100
    return grp


@st.cache_data(show_spinner="AI 분석 요약 생성 중… (최초 실행 시 수 분 소요)")
def get_analysis_summary() -> str:
    """모든 캐시 데이터를 집계해 AI 시스템 프롬프트용 분석 요약 문자열 반환."""
    from scipy.stats import pearsonr

    sections: list[str] = []

    # ── 공통 데이터 로드 ──────────────────────────────────────────────────────
    df_raw = get_dispatch()
    seoul = df_raw[df_raw["GRNDS_CTPV_NM"].str.contains("서울", na=False)].copy()
    seoul["has_trans2"] = seoul["TRANS2_RSN"].notna()
    if "TRANS3_RSN" in seoul.columns:
        seoul["has_trans3"] = seoul["TRANS3_RSN"].notna()

    # ── ① 연도별 출동 건수 ────────────────────────────────────────────────────
    yr_counts = seoul.groupby("_year").size().sort_index()
    sections.append(
        "## 연도별 서울 구급 출동 건수 (샘플 기준)\n"
        + ", ".join(f"{yr}년 {cnt:,}건" for yr, cnt in yr_counts.items())
    )

    # ── ② 연도별 2차·3차 이송률 ──────────────────────────────────────────────
    yr_rate = (
        seoul.groupby("_year")
        .agg(출동=("has_trans2", "count"), 이송2차=("has_trans2", "sum"))
        .assign(발생률=lambda x: x["이송2차"] / x["출동"] * 100)
    )
    lines = "\n".join(
        f"- {yr}년: {row['발생률']:.3f}%  ({int(row['이송2차'])}건 / {int(row['출동']):,}건)"
        for yr, row in yr_rate.iterrows()
    )
    sections.append("## 연도별 2차 이송(뺑뺑이) 발생률\n" + lines)

    # ── ③ 자치구별 2차 이송 발생률 (전체 CSV) ─────────────────────────────────
    dist = get_district_transfer_rate().sort_values("발생률", ascending=False)
    if not dist.empty:
        lines = "\n".join(
            f"- {row['자치구']}: {row['발생률']:.3f}%  (출동 {int(row['출동건수']):,}건, 2차이송 {int(row['이송2차건수'])}건)"
            for _, row in dist.iterrows()
        )
        sections.append("## 서울 자치구별 2차 이송 발생률 (전체 CSV 기반, 높은 순)\n" + lines)

    # ── ④ 2차 이송 거부 이유 ──────────────────────────────────────────────────
    _REASON_MAP = [
        (["응급실"], "응급실 포화"),
        (["병상", "만실", "병실", "입원실", "중환자실", "포화", "입원"], "병상 부족"),
        (["전문의", "진료", "전문", "처치", "치료", "의료", "부재"], "진료 불가"),
        (["거리", "원거리", "접근", "이동"], "거리·접근성"),
        (["기타", "무", "없음", "미상"], "기타"),
    ]

    def _cat(text):
        if not isinstance(text, str) or not text.strip():
            return None
        for kws, label in _REASON_MAP:
            if any(kw in text for kw in kws):
                return label
        return "기타"

    trans2_df = seoul[seoul["has_trans2"]].copy()
    trans2_df["reason_cat"] = trans2_df["TRANS2_RSN"].apply(_cat)
    reason_counts = trans2_df["reason_cat"].dropna().value_counts()
    lines = "\n".join(f"- {r}: {c}건" for r, c in reason_counts.items())
    sections.append("## 2차 이송 거부 이유별 건수\n" + lines)

    # ── ⑤ 2차 이송 추가 이동 거리 통계 ──────────────────────────────────────
    extra = (
        trans2_df["GRNDS2_DSTNC"].fillna(0) - trans2_df["GRNDS_DSTNC"].fillna(0)
    ).clip(lower=0)
    extra = extra[extra > 0]
    if not extra.empty:
        q = extra.quantile([0.25, 0.5, 0.75, 0.90])
        sections.append(
            "## 2차 이송 추가 이동 거리 통계\n"
            f"- 중앙값: {q[0.5]:.2f}km\n"
            f"- 평균: {extra.mean():.2f}km\n"
            f"- 25%ile: {q[0.25]:.2f}km / 75%ile: {q[0.75]:.2f}km / 90%ile: {q[0.90]:.2f}km\n"
            f"- 최대: {extra.max():.1f}km\n"
            f"- 2차 이송 전체 건수: {len(trans2_df):,}건 (샘플 기준)"
        )

    # ── ⑥ 안전센터별 출동 건수 TOP 50 (전체 CSV) ─────────────────────────────
    centers = get_center_counts().head(50).reset_index(drop=True)
    lines = "\n".join(
        f"- {i+1}위 {row['CNTR_NM']}: {int(row['출동건수']):,}건"
        for i, row in centers.iterrows()
    )
    sections.append("## 소방 안전센터별 출동 건수 TOP 50 (전체 CSV 기반)\n" + lines)

    # ── ⑦ 응급실 현황 (병원명 포함) ──────────────────────────────────────────
    er = get_er_locations().copy()
    er["자치구"] = er["주소"].str.split().str[1]
    cls_counts = er["병원분류명"].value_counts()
    lines_cls = "\n".join(f"- {k}: {v}개" for k, v in cls_counts.items())
    gu_order = er["자치구"].value_counts().index
    lines_gu = []
    for gu in gu_order:
        subset = er[er["자치구"] == gu]
        names = subset["기관명"].tolist()
        lines_gu.append(f"- {gu} ({len(names)}개): {', '.join(names)}")
    sections.append(
        f"## 서울 응급실 현황 (총 {len(er)}개소)\n"
        "### 분류별\n" + lines_cls
        + "\n### 자치구별 응급실 목록 (병원명 포함)\n" + "\n".join(lines_gu)
    )

    # ── ⑦-b 응급실 수 × 2차 이송률 상관 ─────────────────────────────────────
    if not dist.empty:
        er_gu = er["자치구"].value_counts().reset_index()
        er_gu.columns = ["자치구", "응급실수"]
        merged = dist.merge(er_gu, on="자치구", how="inner")
        if len(merged) >= 3:
            r_er, p_er = pearsonr(merged["응급실수"], merged["발생률"])
            sig_er = "유의(p<0.05)" if p_er < 0.05 else "비유의"
            direction = "음의 상관 (응급실 많을수록 2차 이송률 낮은 경향)" if r_er < 0 else "양의 상관"
            detail = "\n".join(
                f"  - {row['자치구']}: 응급실 {int(row['응급실수'])}개 / 2차이송률 {row['발생률']:.3f}%"
                for _, row in merged.sort_values("응급실수", ascending=False).iterrows()
            )
            sections.append(
                "## 자치구별 응급실 수 × 2차 이송 발생률 상관분석\n"
                f"- Pearson r={r_er:.3f}, p={p_er:.4f} ({sig_er})\n"
                f"- r²={r_er**2:.3f} → 응급실 수가 2차 이송률 변동의 {r_er**2*100:.1f}% 설명\n"
                f"- 방향: {direction}\n"
                "### 자치구별 상세 (응급실 많은 순)\n" + detail
            )

    # ── ⑧ 환자 발생유형 분포 ─────────────────────────────────────────────────
    if "PTN_OCRN_TYPE_NM" in seoul.columns:
        vc = seoul["PTN_OCRN_TYPE_NM"].value_counts()
        total = vc.sum()
        lines = "\n".join(f"- {k}: {v:,}건 ({v/total*100:.1f}%)" for k, v in vc.items())
        sections.append("## 환자 발생유형 분포\n" + lines)

    # ── ⑧-b 계절·월별 출동 건수 ──────────────────────────────────────────────
    if "SEASN_NM" in seoul.columns:
        season_vc = seoul["SEASN_NM"].value_counts()
        total_s = season_vc.sum()
        season_order = ["봄", "여름", "가을", "겨울"]
        season_lines = []
        for s in season_order:
            if s in season_vc:
                v = season_vc[s]
                season_lines.append(f"- {s}: {v:,}건 ({v/total_s*100:.1f}%)")
        if season_lines:
            sections.append("## 계절별 구급 출동 건수 (샘플 데이터 기준)\n" + "\n".join(season_lines))

    if "DCLR_MM" in seoul.columns:
        monthly_vc = seoul.groupby("DCLR_MM").size().sort_index()
        total_m = monthly_vc.sum()
        month_lines = [
            f"- {int(m)}월: {v:,}건 ({v/total_m*100:.1f}%)"
            for m, v in monthly_vc.items()
        ]
        sections.append("## 월별 구급 출동 건수 (샘플 데이터 기준)\n" + "\n".join(month_lines))

    # ── ⑨ 증상별 정상처리(완료이송)율 ────────────────────────────────────────
    if "PTN_SYM_SE_NM" in seoul.columns and "TRMN_SE_NM" in seoul.columns:
        grp = (
            seoul.groupby("PTN_SYM_SE_NM")
            .apply(lambda g: pd.Series({
                "건수": len(g),
                "완료율": (g["TRMN_SE_NM"] == "정상").mean() * 100,
            }))
        )
        grp = grp[grp["건수"] >= 30].sort_values("완료율", ascending=False)
        lines = "### 완료이송율 상위 10개 증상\n"
        lines += "\n".join(
            f"- {sym}: {row['완료율']:.1f}% ({int(row['건수']):,}건)"
            for sym, row in grp.head(10).iterrows()
        )
        lines += "\n### 완료이송율 하위 10개 증상\n"
        lines += "\n".join(
            f"- {sym}: {row['완료율']:.1f}% ({int(row['건수']):,}건)"
            for sym, row in grp.tail(10).iterrows()
        )
        sections.append("## 증상별 정상처리(완료이송)율\n" + lines)

    # ── ⑩ 주증상 × 중증도 TOP 15 (구급상황관리) ──────────────────────────────
    mgmt = get_mgmt()
    if "MAIN_SYM_NM" in mgmt.columns and "SRIL_CLSF_NM" in mgmt.columns:
        valid = mgmt.dropna(subset=["MAIN_SYM_NM", "SRIL_CLSF_NM"])
        top_syms = valid["MAIN_SYM_NM"].value_counts().head(15).index
        pivot = (
            valid[valid["MAIN_SYM_NM"].isin(top_syms)]
            .groupby(["MAIN_SYM_NM", "SRIL_CLSF_NM"])
            .size()
            .unstack(fill_value=0)
        )
        pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
        lines = []
        for sym in pivot_pct.index:
            parts = ", ".join(
                f"{col}: {pivot_pct.loc[sym, col]:.1f}%"
                for col in pivot_pct.columns
                if pivot_pct.loc[sym, col] >= 5
            )
            lines.append(f"- {sym}: {parts}")
        sections.append(
            "## 주증상별 중증도 분포 TOP 15 (구급상황관리 데이터)\n" + "\n".join(lines)
        )

    # ── ⑪ 기상 변수 × 출동 건수 Pearson 상관 ────────────────────────────────
    weather_map = {
        "HR_UNIT_ARTMP": "기온(°C)",
        "HR_UNIT_RN": "강수량(mm)",
        "HR_UNIT_WSPD": "풍속(m/s)",
        "HR_UNIT_HUM": "습도(%)",
        "HR_UNIT_SNWFL": "적설량(cm)",
    }
    avail_w = [c for c in weather_map if c in seoul.columns]
    if avail_w and "DCLR_YMD" in seoul.columns:
        agg_dict: dict = {"RPTP_NO": "count"}
        agg_dict.update({c: "mean" for c in avail_w})
        daily = seoul.groupby("DCLR_YMD").agg(agg_dict).dropna()
        lines = []
        for col in avail_w:
            if daily[col].std() > 0:
                r, p = pearsonr(daily["RPTP_NO"], daily[col])
                sig = "유의(p<0.05)" if p < 0.05 else "비유의"
                lines.append(f"- {weather_map[col]}: r={r:.3f}, p={p:.4f} ({sig}), r²={r**2:.3f}")
        if lines:
            sections.append("## 기상 변수 × 구급 출동 건수 Pearson 상관 (일별 집계)\n" + "\n".join(lines))

    # ── ⑫ 119 신고유형 추이 ──────────────────────────────────────────────────
    ct = get_call_types()
    type_cols = [c for c in ["화재", "구조", "구급", "대민출동 및 기타"] if c in ct.columns]
    if type_cols and "연도별" in ct.columns:
        recent = ct.groupby("연도별")[type_cols].sum().sort_index().tail(7)
        lines = []
        for yr, row in recent.iterrows():
            total = row.sum()
            parts = ", ".join(
                f"{c}: {int(row[c]):,}건({row[c]/total*100:.1f}%)" for c in type_cols
            )
            lines.append(f"- {yr}년: {parts}")
        sections.append("## 119 신고 유형별 건수 (최근 7개년, 유선+무선 합산)\n" + "\n".join(lines))

    return "\n\n---\n\n".join(sections)


@st.cache_data(show_spinner="119신고 유형 데이터 로드 중…")
def get_call_types():
    from src.config import DATASETS
    ds = DATASETS["119신고유형"]
    df = pd.read_csv(ds["path"], encoding=ds["encoding"])
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"화 재": "화재", "구 조": "구조", "구 급": "구급", "기 타": "기타"})
    return df


@st.cache_data(show_spinner="응급실 위치 데이터 로드 중…")
def get_er_locations():
    from src.config import DATA_DIR
    path = DATA_DIR / "서울시 응급실 위치 정보.csv"
    return pd.read_csv(path, encoding="cp949")


@st.cache_data(show_spinner="전체 CSV에서 안전센터 집계 중… (최초 1회)")
def get_center_counts():
    import pandas as pd
    from src.config import DATASETS

    cfg = DATASETS["구급출동"]
    frames = []
    for yr in cfg["years"]:
        fpath = cfg["dir"] / f"구급출동_{yr}.csv"
        if not fpath.exists():
            continue
        chunk = pd.read_csv(
            fpath,
            usecols=["CNTR_NM", "GRNDS_CTPV_NM"],
            encoding=cfg["encoding"],
            low_memory=False,
        )
        chunk = chunk[chunk["GRNDS_CTPV_NM"].str.contains("서울", na=False)]
        frames.append(chunk[["CNTR_NM"]])

    if not frames:
        return pd.DataFrame(columns=["CNTR_NM", "출동건수"])

    combined = pd.concat(frames, ignore_index=True)
    combined = combined[~combined["CNTR_NM"].isin({"현장대응단"})]
    result = combined["CNTR_NM"].value_counts().reset_index()
    result.columns = ["CNTR_NM", "출동건수"]
    return result
