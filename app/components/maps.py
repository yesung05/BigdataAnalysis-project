import folium

# 지도 관련 유틸 (folium/pydeck 통합 포인트)

def make_map(center=(37.5665,126.9780), zoom_start=12):
    m = folium.Map(location=center, zoom_start=zoom_start)
    return m
