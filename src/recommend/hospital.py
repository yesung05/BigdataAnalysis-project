"""응급실 추천: 사용자 위치·증상 기준 topk 반환."""
from math import atan2, cos, radians, sin, sqrt

# 응급의료기관 분류별 거리 가중치 (낮을수록 우선)
_PRIORITY = {
    "권역응급의료센터": 0.70,
    "지역응급의료센터": 0.85,
    "지역응급의료기관": 1.00,
}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def recommend_hospitals(lat: float, lon: float, symptom: str, hospital_df, topk: int = 3):
    """위도·경도·증상 기준 응급실 topk 반환.

    Parameters
    ----------
    lat, lon : 사용자 위치 (WGS84 십진도)
    symptom : 선택된 증상 문자열 (현재는 가중치 로직에 미반영, 확장용)
    hospital_df : 서울시 응급실 위치 정보 DataFrame
                  필수 컬럼: 병원위도, 병원경도, 기관명, 병원분류명
    topk : 반환할 최대 개수

    Returns
    -------
    DataFrame — score(거리 × 분류 가중치) 오름차순 정렬, topk행
    """
    df = hospital_df.dropna(subset=["병원위도", "병원경도"]).copy()
    df["거리km"] = df.apply(
        lambda r: _haversine(lat, lon, float(r["병원위도"]), float(r["병원경도"])), axis=1
    )

    cls_col = next((c for c in df.columns if "분류명" in c), None)
    if cls_col:
        df["score"] = df.apply(
            lambda r: r["거리km"] * _PRIORITY.get(str(r[cls_col]).strip(), 1.0), axis=1
        )
        sort_col = "score"
    else:
        sort_col = "거리km"

    keep = [c for c in ["기관명", "병원분류명", "주소", "응급실전화", "병원위도", "병원경도", "거리km"] if c in df.columns]
    return df.nsmallest(topk, sort_col)[keep].reset_index(drop=True)
