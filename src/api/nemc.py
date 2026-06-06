"""NEMC Mediboard '내 손안의 응급실' API 클라이언트.

엔드포인트: https://mediboard.nemc.or.kr/api/v1/search/handy
인증 불필요. 서울(emogloca=11) 전체 응급실 51개를 단일 호출로 반환.
"""
from __future__ import annotations

import requests

_BASE = "https://mediboard.nemc.or.kr/api/v1"

# 행정구역 코드
EMOGLOCA = {
    "서울": 11, "부산": 26, "대구": 27, "인천": 28,
    "광주": 29, "대전": 30, "울산": 31, "경기": 41,
}

# 증상 → 수용 불가 확인 Y코드 목록
# unavailableMessages[].code 에서 이 코드가 나오면 해당 증상 수용 불가
SYMPTOM_YCODES: dict[str, list[str]] = {
    "흉통":      ["Y0010"],
    "심정지":    ["Y0010"],
    "의식저하":  ["Y0031", "Y0032", "Y0020"],
    "뇌졸중 의심": ["Y0031", "Y0032", "Y0020"],
    "외상·골절": ["Y0131", "Y0132"],
    "화상":      ["Y0120"],
    "복통":      ["Y0051", "Y0052", "Y0060", "Y0081"],
    "토혈·혈변": ["Y0081", "Y0082"],
    "호흡곤란":  [],   # Y코드 없음 — 일반 병상 + erMessages로 판단
    "소아":      [],   # childEmergencyAvailable로 판단
    "저혈당":    [],
}

# 증상 → 주요 가용 병상 필드 (NEMC 응답 키)
BED_KEY: dict[str, str] = {
    "소아": "childEmergencyAvailable",
}
BED_KEY_DEFAULT = "generalEmergencyAvailable"


def handy_beds(emogloca: int = 11, timeout: int = 10) -> list[dict]:
    """NEMC Mediboard 실시간 병상 조회.

    Parameters
    ----------
    emogloca : int
        행정구역 코드 (서울=11, 기본값)

    Returns
    -------
    list[dict]
        병원별 dict. 주요 키:
          emogCode, emergencyRoomName, emergencyRoomNickname,
          latitude, longitude, address, emergencyInstitutionType,
          generalEmergencyAvailable, generalEmergencyTotal,
          childEmergencyAvailable, childEmergencyTotal,
          npirAvailable, npirTotal,           ← 음압격리병상
          generalAvailable, generalTotal,      ← 일반 입원실
          deliveryRoomAvailable,               ← 분만실 Y/N
          erMessages, unavailableMessages
    """
    resp = requests.get(
        f"{_BASE}/search/handy",
        params={"searchCondition": "regional", "emogloca": emogloca},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("result", {}).get("data", [])
