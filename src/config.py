"""프로젝트 전역 설정: 경로, 데이터셋 메타정보, 인코딩.

모든 모듈은 경로를 하드코딩하지 말고 이 파일을 통해 참조한다.
"""
from __future__ import annotations

from pathlib import Path

# ---- 디렉토리 ----
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR                       # 원본 CSV/XLSX (현재 data/ 루트 및 하위폴더)
INTERIM_DIR = DATA_DIR / "interim"       # 중간 가공물
PROCESSED_DIR = DATA_DIR / "processed"   # 분석용 정제 데이터 (parquet 권장)
OUTPUTS_DIR = PROJECT_ROOT / "outputs"   # 그림/리포트 산출물
FIGURES_DIR = OUTPUTS_DIR / "figures"

for _d in (INTERIM_DIR, PROCESSED_DIR, OUTPUTS_DIR, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---- 데이터셋 정의 ----
# 인코딩 주의: 소방청 대용량 CSV는 UTF-8, 일부 참조 CSV는 cp949(euc-kr).
DATASETS = {
    "구급출동": {
        "dir": RAW_DIR / "구급출동현황",
        "pattern": "구급출동_*.csv",
        "encoding": "utf-8",
        "years": [2017, 2018, 2019, 2020, 2021, 2022],
        "desc": "전국 구급출동 상세 내역 (출동 1건 = 1행, ~200MB/년)",
    },
    "구급상황관리": {
        "dir": RAW_DIR / "구급상황관리현황",
        "pattern": "구급상황관리 현황_*_전국.csv",
        "encoding": "utf-8",
        "years": [2019, 2020, 2021, 2022, 2023],
        "desc": "전국 구급상황관리센터 의료지도 내역 (~250MB/년)",
    },
    "119신고유형": {
        "path": RAW_DIR / "소방청_119신고 전화 유형_20231231.csv",
        "encoding": "cp949",
        "desc": "연도별 119 신고 전화 유형 집계",
    },
    "서울주소별구급출동": {
        "path": RAW_DIR / "소방청_서울특별시 주소별 구급출동현황_20191231.csv",
        "encoding": "cp949",
        "desc": "2019 서울 시도/시군구 주소별 구급출동 건수",
    },
    "서울구급출동_xlsx": {
        "path": RAW_DIR / "서울시 소방 구급 출동 현황(2022_2024).xlsx",
        "desc": "서울시 구급 출동 현황 2022~2024 (엑셀)",
    },
}

# ---- 주요 컬럼 한글 매핑 (구급출동 데이터) ----
# 전체 컬럼 사전은 docs/Api문서.pdf 참조. 분석에 자주 쓰는 것만 정의.
COLUMN_LABELS = {
    "RPTP_NO": "신고번호",
    "DCLR_YMD": "신고일자",
    "DCLR_YR": "신고연도",
    "DCLR_MM": "신고월",
    "DCLR_HR": "신고시각",
    "DCLR_DOW": "신고요일",
    "SEASN_NM": "계절",
    "PTN_OCRN_TYPE_NM": "환자발생유형",
    "PTN_GNDR_NM": "환자성별",
    "PTN_CTPV_NM": "환자시도",
    "GRNDS_CTPV_NM": "현장시도",
    "GRNDS_SGG_NM": "현장시군구",
    "GRNDS_DSTNC": "현장거리",
    "TRMN_SE_NM": "종결구분",
    "DAMG_RGN_LAT": "위도",
    "DAMG_RGN_LOT": "경도",
}

# .env 로드 (프로젝트 루트의 .env 파일에서 환경변수 주입)
import os

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env", override=False)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMER_API_KEY = os.getenv("EMER_API_KEY", "")  # E-Gen 응급의료정보 API

# 대용량 CSV 읽기 기본 청크 크기 (행)
DEFAULT_CHUNKSIZE = 200_000
