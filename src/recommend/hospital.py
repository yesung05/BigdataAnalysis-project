"""응급실 추천 모듈.

recommend_hospitals()         — 정적(거리+분류 가중치) 기반
recommend_hospitals_realtime() — E-Gen 실시간 병상 + 증상 수용 여부 기반
"""
from __future__ import annotations

import re
from math import atan2, cos, radians, sin, sqrt

# ── 분류별 거리 가중치 ────────────────────────────────────────────────────────
_CLASS_WEIGHT = {
    "권역응급의료센터": 0.65,
    "지역응급의료센터": 0.80,
    "지역응급의료기관": 1.00,
}

# ── 증상별 프로파일 (E-Gen API 필드 매핑) ─────────────────────────────────────
# bed_raw_key : realtime_beds._raw 에서 조회할 병상 컬럼 (오퍼레이션 1)
# severe_codes: getSrsillDissAceptncPosblInfoInqire MKioskTy* 코드 (오퍼레이션 2)
# critical    : True이면 중증질환 수용 여부까지 확인
_SYMPTOM_PROFILE: dict[str, dict] = {
    "흉통":      {"bed_raw_key": "hv2",   "equip": ["hvecmoayn","hvcrrtayn"], "severe_codes": ["MKioskTy3","MKioskTy4"], "critical": True,  "label": "심근경색 재관류"},
    "심정지":    {"bed_raw_key": "hvicc", "equip": ["hvecmoayn"],              "severe_codes": ["MKioskTy3","MKioskTy4"], "critical": True,  "label": "심근경색 재관류"},
    "의식저하":  {"bed_raw_key": "hvcc",  "equip": ["hvctayn","hvmriayn"],     "severe_codes": ["MKioskTy1","MKioskTy2"], "critical": True,  "label": "뇌출혈·뇌경색 처치"},
    "뇌졸중 의심":{"bed_raw_key": "hvcc", "equip": ["hvctayn","hvmriayn"],     "severe_codes": ["MKioskTy1","MKioskTy2"], "critical": True,  "label": "뇌졸중 처치"},
    "호흡곤란":  {"bed_raw_key": "hvicc", "equip": ["hvventiayn"],             "severe_codes": [],                         "critical": False, "label": "인공호흡기 필요"},
    "외상·골절": {"bed_raw_key": "hv9",   "equip": [],                         "severe_codes": ["MKioskTy19"],              "critical": True,  "label": "중증외상 수술"},
    "복통":      {"bed_raw_key": "hvec",  "equip": [],                         "severe_codes": ["MKioskTy5","MKioskTy7"],  "critical": False, "label": "응급내시경·복부수술"},
    "화상":      {"bed_raw_key": "hvec",  "equip": [],                         "severe_codes": ["MKioskTy11","MKioskTy12"],"critical": True,  "label": "중증화상"},
    "저혈당":    {"bed_raw_key": "hvec",  "equip": [],                         "severe_codes": [],                         "critical": False, "label": "일반"},
    "소아":      {"bed_raw_key": "hvncc", "equip": [],                         "severe_codes": ["MKioskTy15"],              "critical": False, "label": "소아응급"},
    "토혈·혈변": {"bed_raw_key": "hvec",  "equip": [],                         "severe_codes": ["MKioskTy7"],               "critical": False, "label": "응급내시경"},
}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s)).lower()


def _extract_district(address: str) -> str | None:
    for part in str(address).split():
        if part.endswith("구"):
            return part
    return None


def _bed_factor(count: int | None) -> float:
    if count is None:  return 1.00  # 정보 없음
    if count > 10:     return 0.60
    if count >= 5:     return 0.75
    if count >= 1:     return 0.90
    return 2.00  # 0 = 만실


def _accept_factor(ok: bool | None) -> float:
    if ok is True:  return 0.50  # 수용 가능 → 강력 우선
    if ok is False: return 2.50  # 수용 불가 → 강력 패널티
    return 1.00  # 정보 없음


# ── 정적 추천 (기존 방식 유지) ────────────────────────────────────────────────
def recommend_hospitals(lat: float, lon: float, symptom: str, hospital_df, topk: int = 3):
    """위도·경도·증상 기준 응급실 topk 반환 (정적, DataFrame 반환)."""
    df = hospital_df.dropna(subset=["병원위도", "병원경도"]).copy()
    df["거리km"] = df.apply(
        lambda r: _haversine(lat, lon, float(r["병원위도"]), float(r["병원경도"])), axis=1
    )
    cls_col = next((c for c in df.columns if "분류명" in c), None)
    if cls_col:
        df["score"] = df.apply(
            lambda r: r["거리km"] * _CLASS_WEIGHT.get(str(r[cls_col]).strip(), 1.0), axis=1
        )
        sort_col = "score"
    else:
        sort_col = "거리km"
    keep = [c for c in ["기관명", "병원분류명", "주소", "응급실전화",
                         "병원위도", "병원경도", "거리km"] if c in df.columns]
    return df.nsmallest(topk, sort_col)[keep].reset_index(drop=True)


# ── 실시간 추천 (NEMC Mediboard API) ─────────────────────────────────────────
def _to_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def recommend_hospitals_realtime(
    lat: float, lon: float, symptom: str, hospital_df=None,
    topk: int = 5, emogloca: int = 11,
) -> list[dict]:
    """NEMC Mediboard 실시간 병상으로 최적 응급실 추천.

    단일 API 호출(서울 전체 51개)로 GPS 거리 + 분류가중치 + 병상팩터 + 증상수용팩터 스코어링.
    스코어 낮을수록 우선 추천.

    Returns list[dict] (score 오름차순, topk 개):
      name, nickname, class, address, phone, lat, lon, district,
      distance_km, est_min,
      avail_general, total_general,    ← 응급실 일반 병상
      avail_child, total_child,        ← 소아 응급
      avail_npir,                      ← 음압격리병상
      delivery_ok,                     ← 분만실 Y/N
      symptom_ok, symptom_label,
      key_bed_count, total_bed_count,
      er_messages, unavail_messages,
      score, data_source
    """
    from src.api.nemc import handy_beds, SYMPTOM_YCODES, BED_KEY, BED_KEY_DEFAULT

    profile   = _SYMPTOM_PROFILE.get(symptom, {})
    sym_label = profile.get("label", symptom or "일반")
    y_codes   = set(SYMPTOM_YCODES.get(symptom, []))
    bed_key   = BED_KEY.get(symptom, BED_KEY_DEFAULT)
    bed_total_key = bed_key.replace("Available", "Total")

    # NEMC 단일 호출
    try:
        hospitals = handy_beds(emogloca=emogloca)
    except Exception:
        hospitals = []

    # API 실패 시 정적 fallback
    if not hospitals:
        if hospital_df is not None:
            return _static_fallback(lat, lon, symptom, hospital_df, topk)
        return []

    results: list[dict] = []
    for h in hospitals:
        h_lat = h.get("latitude")
        h_lon = h.get("longitude")
        if not (h_lat and h_lon):
            continue

        dist_km  = _haversine(lat, lon, float(h_lat), float(h_lon))
        cls_nm   = h.get("emergencyInstitutionType", "")
        district = _extract_district(h.get("address", ""))

        # 수용 불가 코드 집합
        unavail_codes = {m.get("code") for m in h.get("unavailableMessages", [])}
        if y_codes:
            symptom_ok: bool | None = (
                False if y_codes & unavail_codes else None
            )
        else:
            symptom_ok = None

        # 주요 병상 수
        key_beds   = _to_int(h.get(bed_key))
        total_beds = _to_int(h.get(bed_total_key))

        # 스코어
        cw    = _CLASS_WEIGHT.get(cls_nm, 1.00)
        bf    = _bed_factor(key_beds)
        af    = _accept_factor(symptom_ok)
        score = dist_km * cw * bf * af

        results.append({
            "name":          h.get("emergencyRoomName", ""),
            "nickname":      h.get("emergencyRoomNickname", ""),
            "class":         cls_nm,
            "address":       h.get("address", ""),
            "phone":         h.get("hotlineTel") or "",
            "lat":           float(h_lat),
            "lon":           float(h_lon),
            "district":      district,
            "distance_km":   dist_km,
            "est_min":       max(1, round(dist_km / 40 * 60)),
            "avail_general":    _to_int(h.get("generalEmergencyAvailable")),
            "total_general":    _to_int(h.get("generalEmergencyTotal")),
            "avail_child":      _to_int(h.get("childEmergencyAvailable")),
            "total_child":      _to_int(h.get("childEmergencyTotal")),
            "avail_npir":       _to_int(h.get("npirAvailable")),
            "total_npir":       _to_int(h.get("npirTotal")),
            "avail_inpatient":  _to_int(h.get("generalAvailable")),
            "total_inpatient":  _to_int(h.get("generalTotal")),
            "delivery_ok":      h.get("deliveryRoomAvailable"),
            "symptom_ok":    symptom_ok,
            "symptom_label": sym_label,
            "key_bed_count": key_beds,
            "total_bed_count": total_beds,
            "er_messages":   [m.get("message", "") for m in h.get("erMessages", [])],
            "unavail_messages": [
                {"code": m.get("code"), "category": m.get("category"),
                 "message": m.get("message")}
                for m in h.get("unavailableMessages", [])
            ],
            "score":       score,
            "data_source": "nemc_realtime",
            "emog_code":   h.get("emogCode"),
        })

    results.sort(key=lambda x: x["score"])
    return results[:topk]


def _static_fallback(lat, lon, symptom, hospital_df, topk):
    """NEMC API 실패 시 정적 거리 기반 fallback."""
    df = hospital_df.dropna(subset=["병원위도", "병원경도"]).copy()
    df["거리km"] = df.apply(
        lambda r: _haversine(lat, lon, float(r["병원위도"]), float(r["병원경도"])), axis=1
    )
    profile = _SYMPTOM_PROFILE.get(symptom, {})
    sym_label = profile.get("label", symptom or "일반")
    results = []
    for _, row in df.nsmallest(topk, "거리km").iterrows():
        dist_km = float(row["거리km"])
        cls_nm  = str(row.get("병원분류명", ""))
        cw      = _CLASS_WEIGHT.get(cls_nm, 1.00)
        results.append({
            "name": str(row.get("기관명", "")), "nickname": "",
            "class": cls_nm, "address": str(row.get("주소", "")),
            "phone": str(row.get("응급실전화", "")),
            "lat": float(row["병원위도"]), "lon": float(row["병원경도"]),
            "district": _extract_district(str(row.get("주소", ""))),
            "distance_km": dist_km, "est_min": max(1, round(dist_km / 40 * 60)),
            "avail_general": None, "total_general": None,
            "avail_child": None, "total_child": None,
            "avail_npir": None, "delivery_ok": None,
            "symptom_ok": None, "symptom_label": sym_label,
            "key_bed_count": None, "total_bed_count": None,
            "er_messages": [], "unavail_messages": [],
            "score": dist_km * cw, "data_source": "static",
            "emog_code": None,
        })
    return results
