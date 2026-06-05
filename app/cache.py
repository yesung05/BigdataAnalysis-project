"""공통 @st.cache_data 래퍼. 모든 페이지에서 import해서 사용."""
import sys
from pathlib import Path

import streamlit as st

_PROJ_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJ_DIR))

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
