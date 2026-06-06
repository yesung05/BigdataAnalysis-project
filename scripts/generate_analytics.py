#!/usr/bin/env python
"""사전 분석 결과 JSON 파일 생성 스크립트.

전체 구급출동 CSV(2017-2022)와 구급상황관리 CSV(2019-2023)를 읽어
data/analytics/*.json 파일로 저장합니다.

실행 (프로젝트 루트에서):
    python scripts/generate_analytics.py

생성 파일 (12개):
    district_transfer.json   자치구별 2차 이송률      (전체 CSV)
    station_load.json        안전센터 출동 순위        (전체 CSV)
    seasonal_demand.json     계절·월·시간대별 출동 패턴 (전체 CSV)
    yearly_trend.json        연도별 출동 건수·이송률   (전체 CSV)
    transfer_analysis.json   2차 이송 거부 이유 + 거리  (전체 CSV)
    er_locations.json        서울 응급실 목록           (정적 CSV)
    er_transfer_corr.json    응급실수 × 2차이송률 상관  (계산값)
    symptom_severity.json    주증상별 중증도 분포       (전체 mgmt CSV)
    dispatch_completion.json 증상별 완료이송율          (전체 CSV)
    weather_correlation.json 기상변수 × 출동건수 상관   (ASOS 서울 시간별 관측, 구급CSV와 겹치는 연도)
    call_types.json          119신고유형 연도별 추이    (정적 CSV)
    occurrence_type.json     환자 발생유형 분포         (전체 CSV)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr

_PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJ))

from src.config import DATA_DIR, DATASETS

OUT_DIR = DATA_DIR / "analytics"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ASOS_DIR = DATA_DIR / "Weather"

# ── 상수 ──────────────────────────────────────────────────────────────────────
SEASON_FROM_MONTH = {
    3: "봄", 4: "봄",  5: "봄",
    6: "여름", 7: "여름", 8: "여름",
    9: "가을", 10: "가을", 11: "가을",
    12: "겨울", 1: "겨울", 2: "겨울",
}
MONTH_NAME = {
    1:"1월",2:"2월",3:"3월",4:"4월",5:"5월",6:"6월",
    7:"7월",8:"8월",9:"9월",10:"10월",11:"11월",12:"12월"
}
REASON_RULES = [
    (["응급실"],                              "응급실 포화"),
    (["병상","만실","병실","입원실","중환자실","포화","입원"], "병상 부족"),
    (["전문의","진료","전문","처치","치료","의료","부재"],    "진료 불가"),
    (["거리","원거리","접근","이동"],          "거리·접근성"),
]
WEATHER_LABEL = {
    "HR_UNIT_ARTMP": "기온(°C)",
    "HR_UNIT_RN":    "강수량(mm)",
    "HR_UNIT_WSPD":  "풍속(m/s)",
    "HR_UNIT_HUM":   "습도(%)",
}

DISPATCH_WANT = [
    "GRNDS_CTPV_NM", "GRNDS_SGG_NM", "CNTR_NM",
    "TRANS2_RSN", "GRNDS_DSTNC", "GRNDS2_DSTNC",
    "SEASN_NM", "DCLR_MM", "DCLR_HR", "DCLR_YMD",
    "PTN_OCRN_TYPE_NM", "PTN_SYM_SE_NM", "TRMN_SE_NM",
    "HR_UNIT_ARTMP", "HR_UNIT_RN", "HR_UNIT_WSPD", "HR_UNIT_HUM",
]

# ── 누산기 ────────────────────────────────────────────────────────────────────
dist_cnt: dict = defaultdict(lambda: {"d": 0, "t": 0})
stn_cnt: dict  = defaultdict(int)
season_cnt: dict = defaultdict(int)
month_cnt: dict  = defaultdict(int)
hour_cnt: dict   = defaultdict(int)
year_cnt: dict   = defaultdict(lambda: {"d": 0, "t": 0})
reason_cnt: dict = defaultdict(int)
extra_dists: list[float] = []
occ_cnt: dict    = defaultdict(int)
sym_complete: dict = defaultdict(lambda: {"done": 0, "total": 0})
weather_records: list[dict] = []

years_processed: list[int] = []

# ════════════════════════════════════════════════════════════════════════════
# PART 1. 전체 구급출동 CSV 처리 (연도별 1 pass)
# ════════════════════════════════════════════════════════════════════════════
cfg = DATASETS["구급출동"]

for year in cfg["years"]:
    fpath = cfg["dir"] / f"구급출동_{year}.csv"
    if not fpath.exists():
        print(f"  SKIP {year}: 파일 없음")
        continue

    # 사용 가능한 컬럼만 읽기
    header_cols = pd.read_csv(fpath, nrows=0, encoding=cfg["encoding"]).columns.tolist()
    usecols = [c for c in DISPATCH_WANT if c in header_cols]

    print(f"  [{year}] 읽는 중...", end=" ", flush=True)
    df = pd.read_csv(fpath, usecols=usecols, encoding=cfg["encoding"], low_memory=False)
    print(f"{len(df):,}행")

    # 서울 필터
    if "GRNDS_CTPV_NM" in df.columns:
        df = df[df["GRNDS_CTPV_NM"].str.contains("서울", na=False)].copy()
    if len(df) == 0:
        continue
    years_processed.append(year)

    # SEASN_NM 없으면 DCLR_MM으로 추론
    if "SEASN_NM" not in df.columns and "DCLR_MM" in df.columns:
        df["SEASN_NM"] = df["DCLR_MM"].apply(
            lambda m: SEASON_FROM_MONTH.get(int(m) if pd.notna(m) and str(m).isdigit() else 0)
        )

    has_t2 = df["TRANS2_RSN"].notna() if "TRANS2_RSN" in df.columns else pd.Series([False] * len(df), index=df.index)

    # ── 자치구별 집계 ─────────────────────────────────────────────────────
    if "GRNDS_SGG_NM" in df.columns:
        for gu, grp in df.groupby("GRNDS_SGG_NM", dropna=True):
            dist_cnt[gu]["d"] += len(grp)
            if "TRANS2_RSN" in df.columns:
                dist_cnt[gu]["t"] += int(grp["TRANS2_RSN"].notna().sum())

    # ── 안전센터 집계 ─────────────────────────────────────────────────────
    if "CNTR_NM" in df.columns:
        for nm, cnt in df["CNTR_NM"].dropna().value_counts().items():
            if nm != "현장대응단":
                stn_cnt[nm] += int(cnt)

    # ── 계절·월·시간대 집계 ──────────────────────────────────────────────
    if "SEASN_NM" in df.columns:
        for s, c in df["SEASN_NM"].dropna().value_counts().items():
            season_cnt[s] += int(c)

    if "DCLR_MM" in df.columns:
        for m, c in df["DCLR_MM"].dropna().apply(lambda x: int(x) if str(x).isdigit() else None).dropna().astype(int).value_counts().items():
            if 1 <= int(m) <= 12:
                month_cnt[int(m)] += int(c)

    if "DCLR_HR" in df.columns:
        def _parse_hr(x):
            try:
                v = int(x)
                return v // 100 if v > 24 else v  # HHMM → HH
            except Exception:
                return None
        for h, c in df["DCLR_HR"].dropna().apply(_parse_hr).dropna().astype(int).value_counts().items():
            if 0 <= int(h) <= 23:
                hour_cnt[int(h)] += int(c)

    # ── 연도별 추이 ───────────────────────────────────────────────────────
    year_cnt[year]["d"] += len(df)
    if "TRANS2_RSN" in df.columns:
        year_cnt[year]["t"] += int(has_t2.sum())

    # ── 2차 이송 거부 이유 + 거리 ─────────────────────────────────────────
    if "TRANS2_RSN" in df.columns:
        trans2 = df[has_t2]
        for txt in trans2["TRANS2_RSN"].dropna():
            cat = "기타"
            for kws, label in REASON_RULES:
                if any(kw in str(txt) for kw in kws):
                    cat = label
                    break
            reason_cnt[cat] += 1

        if "GRNDS_DSTNC" in df.columns and "GRNDS2_DSTNC" in df.columns:
            extra = (
                trans2["GRNDS2_DSTNC"].fillna(0).astype(float)
                - trans2["GRNDS_DSTNC"].fillna(0).astype(float)
            ).clip(lower=0)
            extra = extra[extra > 0].tolist()
            if len(extra_dists) < 200_000:
                extra_dists.extend(extra)

    # ── 환자 발생유형 ─────────────────────────────────────────────────────
    if "PTN_OCRN_TYPE_NM" in df.columns:
        for ot, c in df["PTN_OCRN_TYPE_NM"].dropna().value_counts().items():
            occ_cnt[ot] += int(c)

    # ── 증상별 완료이송율 ─────────────────────────────────────────────────
    if "PTN_SYM_SE_NM" in df.columns and "TRMN_SE_NM" in df.columns:
        tmp = df.dropna(subset=["PTN_SYM_SE_NM"])
        for sym, grp in tmp.groupby("PTN_SYM_SE_NM"):
            sym_complete[sym]["total"] += len(grp)
            sym_complete[sym]["done"]  += int((grp["TRMN_SE_NM"] == "정상").sum())

    # ── 기상 (일별 집계) ──────────────────────────────────────────────────
    wc_avail = [c for c in WEATHER_LABEL if c in df.columns]
    if "DCLR_YMD" in df.columns and wc_avail:
        agg_dict = {c: "mean" for c in wc_avail}
        agg_dict["GRNDS_SGG_NM"] = "count"  # dispatch count
        day_df = df.groupby("DCLR_YMD").agg(agg_dict).rename(
            columns={"GRNDS_SGG_NM": "count"}
        )
        for date, row in day_df.iterrows():
            rec: dict = {"date": str(date), "count": int(row["count"])}
            for wc in wc_avail:
                v = row.get(wc)
                if pd.notna(v):
                    rec[wc] = float(v)
            weather_records.append(rec)

    del df  # 메모리 해제

print(f"\n구급출동 처리 완료: {years_processed}\n")

# ════════════════════════════════════════════════════════════════════════════
# PART 2. 구급상황관리 CSV 처리 (증상×중증도)
# ════════════════════════════════════════════════════════════════════════════
mgmt_cfg = DATASETS["구급상황관리"]
MGMT_WANT = ["MAIN_SYM_NM", "SRIL_CLSF_NM"]

symptom_sev: dict = defaultdict(lambda: defaultdict(int))  # sym -> {class -> count}
mgmt_years: list[int] = []

for year in mgmt_cfg["years"]:
    fpath = mgmt_cfg["dir"] / f"구급상황관리 현황_{year}_전국.csv"
    if not fpath.exists():
        continue
    header_cols = pd.read_csv(fpath, nrows=0, encoding=mgmt_cfg["encoding"]).columns.tolist()
    usecols = [c for c in MGMT_WANT if c in header_cols]
    if len(usecols) < 2:
        continue

    print(f"  [mgmt {year}] 읽는 중...", end=" ", flush=True)
    mdf = pd.read_csv(fpath, usecols=usecols, encoding=mgmt_cfg["encoding"], low_memory=False)
    print(f"{len(mdf):,}행")
    mgmt_years.append(year)

    for sym, grp in mdf.dropna(subset=MGMT_WANT).groupby("MAIN_SYM_NM"):
        for cls, cnt in grp["SRIL_CLSF_NM"].value_counts().items():
            symptom_sev[sym][cls] += int(cnt)

    del mdf

print(f"\n구급상황관리 처리 완료: {mgmt_years}\n")

# ════════════════════════════════════════════════════════════════════════════
# PART 3. 정적 CSV 처리 (응급실, 119신고유형)
# ════════════════════════════════════════════════════════════════════════════

# ── 응급실 위치 정보 ──────────────────────────────────────────────────────
print("  [응급실] 읽는 중...")
er_path = DATA_DIR / "서울시 응급실 위치 정보.csv"
er_df = pd.read_csv(er_path, encoding="cp949")
er_df["자치구"] = er_df["주소"].str.split().str[1]

er_by_district: dict = {}
for gu, grp in er_df.groupby("자치구", dropna=True):
    hospitals = []
    for _, row in grp.iterrows():
        hospitals.append({
            "name":    str(row.get("기관명", "")),
            "class":   str(row.get("병원분류명", "")),
            "phone":   str(row.get("응급실전화", "")),
            "address": str(row.get("주소", "")),
            "lat":     float(row["병원위도"]) if pd.notna(row.get("병원위도")) else None,
            "lon":     float(row["병원경도"]) if pd.notna(row.get("병원경도")) else None,
        })
    er_by_district[gu] = hospitals

class_counts: dict = er_df["병원분류명"].value_counts().to_dict()

# ── 119신고유형 ───────────────────────────────────────────────────────────
print("  [119신고] 읽는 중...")
ct_ds = DATASETS["119신고유형"]
ct_df = pd.read_csv(ct_ds["path"], encoding=ct_ds["encoding"])
ct_df.columns = ct_df.columns.str.strip()
ct_df = ct_df.rename(columns={"화 재": "화재", "구 조": "구조", "구 급": "구급", "기 타": "기타"})

type_cols = [c for c in ["화재", "구조", "구급", "대민출동 및 기타", "장난전화", "무응답", "오접속"] if c in ct_df.columns]
call_types_list = []
if "연도별" in ct_df.columns:
    for yr, grp in ct_df.groupby("연도별"):
        rec: dict = {"year": int(yr)}
        for c in type_cols:
            rec[c] = int(grp[c].sum()) if c in grp.columns else 0
        call_types_list.append(rec)
    call_types_list.sort(key=lambda x: x["year"])

# ════════════════════════════════════════════════════════════════════════════
# PART 4. 파생 통계 계산
# ════════════════════════════════════════════════════════════════════════════

# ── 기상 상관계수 (ASOS 외부 데이터 기준) ────────────────────────────────
print("\n  [기상] ASOS 서울(108) 시간별 관측 로드 및 Pearson 상관 계산 중...")
weather_corr: list[dict] = []
_asos_days = 0
_ASOS_WEATHER_KEYS = ["기온(°C)", "강수량(mm)", "풍속(m/s)", "습도(%)"]

if weather_records:
    # 일별 서울 구급출동 건수
    _dispatch_daily = (
        pd.DataFrame([{"date": r["date"], "count": r["count"]} for r in weather_records])
        .groupby("date")["count"].sum()
        .reset_index()
    )
    _dispatch_daily["date"] = pd.to_datetime(_dispatch_daily["date"])

    # ASOS 파일 로드 — 구급CSV와 겹치는 연도만
    _asos_frames = []
    for _f in sorted(ASOS_DIR.glob("*.csv")):
        try:
            _df = pd.read_csv(_f, encoding="cp949", usecols=[2, 3, 5, 7, 11], header=0)
            _df.columns = ["datetime", "기온(°C)", "강수량(mm)", "풍속(m/s)", "습도(%)"]
            _df["datetime"] = pd.to_datetime(_df["datetime"], errors="coerce")
            _df = _df.dropna(subset=["datetime"])
            _yr = int(_df["datetime"].dt.year.mode()[0])
            if _yr in years_processed:
                _asos_frames.append(_df)
                print(f"    {_yr}년 로드: {len(_df):,}행 ({_f.name})")
        except Exception as exc:
            print(f"    ⚠ {_f.name} 로드 실패: {exc}")

    if _asos_frames:
        _asos = pd.concat(_asos_frames, ignore_index=True)
        _asos["date"] = _asos["datetime"].dt.normalize()
        # 일별 집계: 기온/풍속/습도 평균, 강수량 합계
        _asos_daily = _asos.groupby("date").agg({
            "기온(°C)":  "mean",
            "강수량(mm)": "sum",
            "풍속(m/s)": "mean",
            "습도(%)":   "mean",
        }).reset_index()

        _joined = _dispatch_daily.merge(_asos_daily, on="date", how="inner")
        _asos_days = len(_joined)
        print(f"    → 겹침 일수: {_asos_days}일")

        for label in _ASOS_WEATHER_KEYS:
            valid = _joined[["count", label]].dropna()
            if len(valid) >= 10 and valid[label].std() > 0:
                r, p = pearsonr(valid["count"], valid[label])
                weather_corr.append({
                    "variable": label, "col": label,
                    "r":    round(float(r), 4),
                    "p":    round(float(p), 4),
                    "r2":   round(float(r ** 2), 4),
                    "significant": bool(p < 0.05),
                })
    else:
        print("    → 겹치는 ASOS 파일 없음, 기상 상관 건너뜀")

# ── 응급실 × 2차이송 상관 ────────────────────────────────────────────────
print("  [상관] 응급실수 × 2차이송률 계산 중...")
er_transfer_corr: dict = {}
if dist_cnt and er_by_district:
    rows = []
    for gu, stats in dist_cnt.items():
        if stats["d"] > 0 and gu in er_by_district:
            rows.append({
                "district":    gu,
                "er_count":    len(er_by_district[gu]),
                "transfer_rate_pct": round(stats["t"] / stats["d"] * 100, 4),
            })
    if len(rows) >= 5:
        rdf = pd.DataFrame(rows)
        r, p = pearsonr(rdf["er_count"], rdf["transfer_rate_pct"])
        er_transfer_corr = {
            "pearson_r":   round(float(r), 4),
            "p_value":     round(float(p), 4),
            "r_squared":   round(float(r**2), 4),
            "significant": bool(p < 0.05),
            "direction":   "음의 상관 (응급실 많을수록 2차 이송률 낮은 경향)" if r < 0 else "양의 상관",
            "districts":   sorted(rows, key=lambda x: -x["er_count"]),
        }

# ════════════════════════════════════════════════════════════════════════════
# PART 5. JSON 파일 저장
# ════════════════════════════════════════════════════════════════════════════

def save(name: str, data: dict) -> None:
    path = OUT_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → {path.name} 저장 완료")


total_dispatch = sum(v["d"] for v in year_cnt.values())

# 1. district_transfer.json
districts_list = []
for gu, stats in sorted(dist_cnt.items(), key=lambda x: -x[1]["t"] / x[1]["d"] if x[1]["d"] > 0 else 0):
    if stats["d"] > 0:
        districts_list.append({
            "district":         gu,
            "rate_pct":         round(stats["t"] / stats["d"] * 100, 4),
            "dispatches":       stats["d"],
            "transfers":        stats["t"],
        })
for i, d in enumerate(districts_list):
    d["rank"] = i + 1

save("district_transfer", {
    "meta": {
        "years": years_processed,
        "total_dispatches": total_dispatch,
        "note": "서울 전체 구급출동 CSV 기반 (전체 데이터)"
    },
    "districts":   districts_list,
    "highest":     districts_list[0] if districts_list else {},
    "lowest":      districts_list[-1] if districts_list else {},
    "seoul_avg_pct": round(sum(v["t"] for v in dist_cnt.values()) / total_dispatch * 100, 4) if total_dispatch > 0 else 0,
})

# 2. station_load.json
station_list = sorted(stn_cnt.items(), key=lambda x: -x[1])
save("station_load", {
    "meta": {"years": years_processed},
    "rankings": [
        {"rank": i+1, "name": nm, "dispatches": cnt}
        for i, (nm, cnt) in enumerate(station_list)
    ],
})

# 3. seasonal_demand.json
season_total = sum(season_cnt.values())
month_total  = sum(month_cnt.values())
hour_total   = sum(hour_cnt.values())

season_order = ["봄", "여름", "가을", "겨울"]
by_season = sorted(
    [{"season": s, "dispatches": season_cnt.get(s, 0),
      "pct": round(season_cnt.get(s, 0) / season_total * 100, 2) if season_total else 0}
     for s in season_order],
    key=lambda x: -x["dispatches"]
)
by_month = sorted(
    [{"month": m, "month_name": MONTH_NAME[m], "dispatches": month_cnt.get(m, 0),
      "pct": round(month_cnt.get(m, 0) / month_total * 100, 2) if month_total else 0}
     for m in range(1, 13)],
    key=lambda x: -x["dispatches"]
)
by_hour = sorted(
    [{"hour": h, "time_range": f"{h}~{(h+1)%24}시",
      "dispatches": hour_cnt.get(h, 0),
      "pct": round(hour_cnt.get(h, 0) / hour_total * 100, 2) if hour_total else 0}
     for h in range(24)],
    key=lambda x: -x["dispatches"]
)
peak_season = by_season[0]["season"] if by_season else ""
peak_month  = by_month[0]["month_name"] if by_month else ""
peak_hour   = by_hour[0]["time_range"] if by_hour else ""

save("seasonal_demand", {
    "meta": {"years": years_processed, "total": month_total},
    "by_season":  by_season,
    "by_month":   by_month,
    "by_hour":    by_hour,
    "insight": f"피크: {peak_season}(계절), {peak_month}(월), {peak_hour}(시간대)",
})

# 4. yearly_trend.json
yearly = sorted(
    [{"year": yr, "dispatches": v["d"], "transfers": v["t"],
      "transfer_rate_pct": round(v["t"] / v["d"] * 100, 4) if v["d"] > 0 else 0}
     for yr, v in year_cnt.items()],
    key=lambda x: x["year"]
)
save("yearly_trend", {
    "meta": {"note": "서울 구급출동 전체 CSV 기반"},
    "yearly": yearly,
})

# 5. transfer_analysis.json
reason_total = sum(reason_cnt.values())
reasons_list = sorted(
    [{"reason": r, "count": c,
      "pct": round(c / reason_total * 100, 2) if reason_total else 0}
     for r, c in reason_cnt.items()],
    key=lambda x: -x["count"]
)
dist_stats: dict = {}
if extra_dists:
    arr = np.array(extra_dists)
    dist_stats = {
        "count":   len(arr),
        "median":  round(float(np.median(arr)), 2),
        "mean":    round(float(arr.mean()), 2),
        "p25":     round(float(np.percentile(arr, 25)), 2),
        "p75":     round(float(np.percentile(arr, 75)), 2),
        "p90":     round(float(np.percentile(arr, 90)), 2),
        "max":     round(float(arr.max()), 1),
    }
save("transfer_analysis", {
    "meta": {"years": years_processed},
    "reasons": reasons_list,
    "distance_km": dist_stats,
})

# 6. er_locations.json
save("er_locations", {
    "meta": {"total": len(er_df), "note": "서울시 응급실 위치 정보 CSV 기반"},
    "by_classification": [
        {"class": k, "count": v}
        for k, v in sorted(class_counts.items(), key=lambda x: -x[1])
    ],
    "by_district": er_by_district,
})

# 7. er_transfer_corr.json
save("er_transfer_corr", er_transfer_corr if er_transfer_corr else {
    "note": "데이터 부족으로 계산 불가"
})

# 8. symptom_severity.json
sym_list = []
for sym, cls_cnt in symptom_sev.items():
    total = sum(cls_cnt.values())
    if total < 30:
        continue
    severity = {cls: round(cnt / total * 100, 2) for cls, cnt in cls_cnt.items()}
    sym_list.append({"symptom": sym, "total": total, "severity": severity})
sym_list.sort(key=lambda x: -x["total"])
save("symptom_severity", {
    "meta": {"years": mgmt_years, "note": "전국 구급상황관리 CSV 기반"},
    "symptoms": sym_list,
})

# 9. dispatch_completion.json
comp_list = []
for sym, stats in sym_complete.items():
    if stats["total"] >= 50:
        rate = round(stats["done"] / stats["total"] * 100, 2)
        comp_list.append({"symptom": sym, "completion_rate_pct": rate, "count": stats["total"]})
comp_list.sort(key=lambda x: -x["completion_rate_pct"])
save("dispatch_completion", {
    "meta": {"years": years_processed},
    "top_completion":    comp_list[:15],
    "bottom_completion": list(reversed(comp_list[-15:])),
})

# 10. weather_correlation.json
save("weather_correlation", {
    "meta": {
        "years": years_processed,
        "days_analyzed": _asos_days,
        "source": "ASOS 서울(108) 시간별 관측 × 구급출동 겹침 연도",
    },
    "correlations": sorted(weather_corr, key=lambda x: -abs(x["r"])),
})

# 11. call_types.json
save("call_types", {
    "meta": {"note": "소방청 119신고 전화 유형 CSV 기반"},
    "type_columns": type_cols,
    "yearly": call_types_list,
})

# 12. occurrence_type.json
occ_total = sum(occ_cnt.values())
occ_list = sorted(
    [{"type": t, "count": c, "pct": round(c / occ_total * 100, 2) if occ_total else 0}
     for t, c in occ_cnt.items()],
    key=lambda x: -x["count"]
)
save("occurrence_type", {
    "meta": {"years": years_processed, "total": occ_total},
    "types": occ_list,
})

print("\n✅ 모든 analytics JSON 생성 완료.")
print(f"   출력 디렉토리: {OUT_DIR}")
