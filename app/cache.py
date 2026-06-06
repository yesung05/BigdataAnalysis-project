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
