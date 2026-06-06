"""소방 안전센터 추천: 사용자 위치 기준 가장 가까운 topk 반환."""
from math import atan2, cos, radians, sin, sqrt


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 GPS 좌표 간 직선 거리(km) — Haversine 공식."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def recommend_stations(lat: float, lon: float, stations_df, topk: int = 3):
    """위도·경도 기준 가까운 소방 안전센터 topk 반환.

    Parameters
    ----------
    lat, lon : 사용자 위치 (WGS84 십진도)
    stations_df : load_station_coords() 반환값 (컬럼: 기관명, 위도, 경도, 유형)
    topk : 반환할 최대 개수

    Returns
    -------
    DataFrame — 거리km 오름차순 정렬, topk행
    """
    df = stations_df.dropna(subset=["위도", "경도"]).copy()
    df["거리km"] = df.apply(
        lambda r: _haversine(lat, lon, float(r["위도"]), float(r["경도"])), axis=1
    )
    keep = [c for c in ["기관명", "상위 본부명", "유형", "주소", "위도", "경도", "거리km"] if c in df.columns]
    return df.nsmallest(topk, "거리km")[keep].reset_index(drop=True)
