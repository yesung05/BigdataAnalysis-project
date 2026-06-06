"""E-Gen 응급의료정보조회 API 클라이언트.

오퍼레이션:
  1. getEmrrmRltmUsefulSckbdInfoInqire  — 응급실 실시간 가용병상
  2. getSrsillDissAceptncPosblInfoInqire — 중증질환자 수용가능정보
  3. getEgytListInfoInqire              — 응급의료기관 목록 (정적)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

_PROJ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJ))

from src.config import EMER_API_KEY

_BASE = "http://apis.data.go.kr/B552657/ErmctInfoInqireService"

# ── 응답 필드 한글 라벨 맵 ────────────────────────────────────────────────────
BEDS_LABEL = {
    "hvec": "응급실 일반 병상",
    "hvicc": "중환자실 일반",
    "hvcc": "중환자실 신경과",
    "hvccc": "중환자실 흉부외과",
    "hv2": "중환자실 내과",
    "hv3": "중환자실 외과",
    "hv6": "중환자실 신경외과",
    "hv9": "중환자실 외상",
    "hv31": "[응급전용] 중환자실",
    "hv36": "[응급전용] 입원실",
}

EQUIP_LABEL = {
    "hvctayn": "CT",
    "hvmriayn": "MRI",
    "hvangioayn": "혈관촬영기",
    "hvventiayn": "인공호흡기",
    "hvecmoayn": "ECMO",
    "hvcrrtayn": "CRRT",
    "hvoxyayn": "고압산소치료기",
    "hvhypoayn": "중심체온조절유도기",
    "hvamyn": "구급차 가용",
}

SEVERE_LABEL = {
    "MKioskTy1": "뇌출혈 수술",
    "MKioskTy2": "뇌경색 재관류",
    "MKioskTy3": "심근경색 재관류(수술)",
    "MKioskTy4": "심근경색 재관류(시술)",
    "MKioskTy5": "복부손상 수술",
    "MKioskTy6": "사지접합 수술",
    "MKioskTy7": "응급내시경",
    "MKioskTy8": "응급투석",
    "MKioskTy9": "조산산모",
    "MKioskTy10": "정신질환",
    "MKioskTy11": "중증화상(1차)",
    "MKioskTy12": "중증화상(2차)",
    "MKioskTy15": "소아응급",
    "MKioskTy19": "중증외상",
    "MKioskTy22": "투석(HD)",
    "MKioskTy23": "CRRT",
    "MKioskTy25": "HIV 감염 응급",
    "MKioskTy28": "응급게이트키퍼(정신과)",
}

# 증상 문자열 → 우선 확인 중증질환 코드 맵
SYMPTOM_TO_SEVERE = {
    "흉통":      ["MKioskTy3", "MKioskTy4"],
    "심정지":    ["MKioskTy3", "MKioskTy4"],
    "의식저하":  ["MKioskTy1", "MKioskTy2"],
    "두통":      ["MKioskTy1", "MKioskTy2"],
    "편측마비":  ["MKioskTy1", "MKioskTy2"],
    "뇌졸중 의심": ["MKioskTy1", "MKioskTy2"],
    "중증외상":  ["MKioskTy19"],
    "교통사고":  ["MKioskTy19"],
    "추락":      ["MKioskTy19"],
    "외상·골절": ["MKioskTy19"],
    "화상":      ["MKioskTy11", "MKioskTy12"],
    "호흡곤란":  [],   # 장비(hvventiayn) 위주로 확인
    "소아":      ["MKioskTy15"],
}


def _call(operation: str, params: dict) -> list[dict]:
    """E-Gen API 호출 → item dict 리스트 반환. 실패 시 RuntimeError."""
    if not EMER_API_KEY:
        raise RuntimeError("EMER_API_KEY 미설정 — .env에 키를 추가하세요.")
    full_params = {**params, "serviceKey": EMER_API_KEY}
    resp = requests.get(f"{_BASE}/{operation}", params=full_params, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    code = getattr(root.find(".//resultCode"), "text", "")
    if code and code != "00":
        msg = getattr(root.find(".//resultMsg"), "text", "알 수 없는 오류")
        raise RuntimeError(f"API 오류 {code}: {msg}")
    return [{child.tag: child.text for child in item} for item in root.findall(".//item")]


def realtime_beds(sigungu: str, sido: str = "서울특별시", rows: int = 20) -> list[dict]:
    """오퍼레이션 1 — 응급실 실시간 가용병상 조회.

    반환 항목 (병원별):
      name, phone, updated, beds(dict: 한글라벨→수), equip(dict: 한글라벨→Y/N)
    """
    items = _call("getEmrrmRltmUsefulSckbdInfoInqire", {
        "STAGE1": sido, "STAGE2": sigungu, "numOfRows": rows,
    })
    result = []
    for it in items:
        # 0 병상도 포함 (0 = 만실 의미)
        beds = {}
        for k, label in BEDS_LABEL.items():
            v = it.get(k)
            if v is not None:
                try:
                    beds[label] = int(v)
                except (ValueError, TypeError):
                    pass
        equip = {EQUIP_LABEL[k]: v for k, v in it.items()
                 if k in EQUIP_LABEL and v in ("Y", "N")}
        result.append({
            "name":    it.get("dutyName", ""),
            "phone":   it.get("dutyTel3", ""),
            "updated": it.get("hvidate", ""),
            "hpid":    it.get("hpid", ""),
            "beds":    beds,
            "equip":   equip,
            "_raw":    dict(it),  # 전체 필드 (MKioskTy* 등 커스텀 조회용)
        })
    return result


def severe_acceptance(sigungu: str, sido: str = "서울특별시",
                      symptom: str = "", rows: int = 30) -> list[dict]:
    """오퍼레이션 2 — 중증질환자 수용가능정보 조회.

    반환: 병원별 {name, phone, available: [한글질환명...], unavailable: [...]}
    증상이 지정되면 해당 중증질환 코드를 우선 확인해 결과를 필터.
    """
    items = _call("getSrsillDissAceptncPosblInfoInqire", {
        "STAGE1": sido, "STAGE2": sigungu, "numOfRows": rows,
    })
    target_codes = SYMPTOM_TO_SEVERE.get(symptom, [])

    result = []
    for it in items:
        available, unavailable = [], []
        for code, label in SEVERE_LABEL.items():
            val = it.get(code, "")
            if val == "Y":
                available.append(label)
            elif val == "N":
                unavailable.append(label)
        # 증상 지정 시 해당 수용 여부 확인
        symptom_ok = None
        if target_codes:
            symptom_ok = any(it.get(c, "") == "Y" for c in target_codes)
        result.append({
            "name":       it.get("dutyName", ""),
            "phone":      it.get("dutyTel3", ""),
            "available":  available,
            "unavailable": unavailable,
            "symptom_ok": symptom_ok,
        })
    # 증상 지정 시 수용 가능 병원 먼저 정렬
    if target_codes:
        result.sort(key=lambda x: (0 if x["symptom_ok"] else 1))
    return result
