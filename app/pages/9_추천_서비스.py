"""9. 추천 서비스 — 내 위치 기반 소방 안전센터·응급실 TOP-3."""
import sys
from pathlib import Path

import folium
import streamlit as st

try:
    from streamlit_folium import st_folium
    _HAS_ST_FOLIUM = True
except Exception:
    _HAS_ST_FOLIUM = False

try:
    from streamlit_js_eval import get_geolocation
    _HAS_GEO = True
except Exception:
    _HAS_GEO = False

_PAGES_DIR = Path(__file__).resolve().parent
_APP_DIR = _PAGES_DIR.parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from cache import get_er_locations, get_station_coords
from src.recommend.hospital import recommend_hospitals
from src.recommend.station import recommend_stations

st.set_page_config(page_title="추천 서비스", layout="wide")
st.title("🚑 소방 안전센터·응급실 추천")
st.caption("내 위치와 증상을 입력하면 가장 가까운 소방 안전센터(TOP-3)와 응급실(TOP-3)을 안내합니다.")

# ── 서울 25개 자치구 중심 좌표 ────────────────────────────────────────────────
SEOUL_DISTRICTS: dict[str, tuple[float, float]] = {
    "강남구": (37.5172, 127.0473),
    "강동구": (37.5301, 127.1238),
    "강북구": (37.6396, 127.0255),
    "강서구": (37.5509, 126.8495),
    "관악구": (37.4784, 126.9516),
    "광진구": (37.5384, 127.0822),
    "구로구": (37.4954, 126.8874),
    "금천구": (37.4567, 126.8956),
    "노원구": (37.6541, 127.0568),
    "도봉구": (37.6688, 127.0471),
    "동대문구": (37.5744, 127.0401),
    "동작구": (37.5124, 126.9393),
    "마포구": (37.5615, 126.9088),
    "서대문구": (37.5791, 126.9368),
    "서초구": (37.4836, 127.0327),
    "성동구": (37.5633, 127.0369),
    "성북구": (37.5894, 127.0167),
    "송파구": (37.5145, 127.1059),
    "양천구": (37.5270, 126.8561),
    "영등포구": (37.5264, 126.8965),
    "용산구": (37.5311, 126.9809),
    "은평구": (37.6026, 126.9291),
    "종로구": (37.5735, 126.9790),
    "중구": (37.5641, 126.9978),
    "중랑구": (37.6063, 127.0925),
}

SYMPTOMS = ["(선택 안 함)", "흉통", "호흡곤란", "의식저하", "외상·골절", "복통", "저혈당", "뇌졸중 의심", "기타"]

# ── 입력 UI ─────────────────────────────────────────────────────────────────
st.subheader("📍 내 위치 입력")

_GPS_LABEL = "현재 위치 자동 감지 (GPS)"
_MODES = [_GPS_LABEL, "자치구 선택", "위도·경도 직접 입력"] if _HAS_GEO else ["자치구 선택", "위도·경도 직접 입력"]

col_mode, col_sym = st.columns([2, 2])
with col_mode:
    input_mode = st.radio("입력 방식", _MODES, horizontal=True)

with col_sym:
    symptom = st.selectbox("🩺 주요 증상", SYMPTOMS)

user_lat, user_lon = 37.5665, 126.9780  # 기본값: 서울시청

if input_mode == _GPS_LABEL:
    with st.spinner("위치 정보를 가져오는 중… (브라우저 권한 허용 필요)"):
        loc = get_geolocation()
    if loc and "coords" in loc:
        user_lat = loc["coords"]["latitude"]
        user_lon = loc["coords"]["longitude"]
        acc = loc["coords"].get("accuracy", None)
        st.success(f"위치 감지 완료: 위도 {user_lat:.5f}, 경도 {user_lon:.5f}" +
                   (f" (정확도 ±{acc:.0f}m)" if acc else ""))
    else:
        st.warning(
            "GPS 위치를 가져오지 못했습니다.  \n"
            "브라우저 주소창 왼쪽의 🔒 아이콘 → 위치 권한을 **허용**으로 변경하세요.  \n"
            "기본값(서울시청)으로 대신 표시합니다."
        )

elif input_mode == "자치구 선택":
    gu = st.selectbox("자치구", list(SEOUL_DISTRICTS.keys()))
    user_lat, user_lon = SEOUL_DISTRICTS[gu]
    st.caption(f"선택한 자치구 중심 좌표: 위도 {user_lat}, 경도 {user_lon}")

else:
    c1, c2 = st.columns(2)
    with c1:
        user_lat = st.number_input("위도 (latitude)", value=37.5665, format="%.4f", step=0.001)
    with c2:
        user_lon = st.number_input("경도 (longitude)", value=126.9780, format="%.4f", step=0.001)

st.divider()

# ── 데이터 로드 ──────────────────────────────────────────────────────────────
station_df = get_station_coords()
er_df = get_er_locations()

# 서울 안전센터만 필터링 (좌표 범위 기준)
seoul_stations = station_df[
    station_df["위도"].between(37.40, 37.72) &
    station_df["경도"].between(126.73, 127.25)
].copy()

# ── 추천 실행 ────────────────────────────────────────────────────────────────
top_stations = recommend_stations(user_lat, user_lon, seoul_stations, topk=3)
top_hospitals = recommend_hospitals(user_lat, user_lon, symptom, er_df, topk=3)

# ── 결과 카드 ────────────────────────────────────────────────────────────────
col_s, col_h = st.columns(2)

with col_s:
    st.subheader("🚒 가까운 소방 안전센터 TOP-3")
    if top_stations.empty:
        st.warning("서울 소방 안전센터 데이터를 불러올 수 없습니다.")
    else:
        for rank, (_, row) in enumerate(top_stations.iterrows(), 1):
            name = row.get("기관명", "알 수 없음")
            dist = row.get("거리km", float("nan"))
            parent = row.get("상위 본부명", "")
            kind = row.get("유형", "")
            with st.container(border=True):
                st.markdown(f"**{rank}위 — {name}**")
                c1, c2 = st.columns(2)
                c1.metric("거리", f"{dist:.2f} km")
                c2.metric("유형", kind)
                if parent:
                    st.caption(f"관할: {parent}")

with col_h:
    st.subheader("🏥 가까운 응급실 TOP-3")
    if top_hospitals.empty:
        st.warning("응급실 데이터를 불러올 수 없습니다.")
    else:
        for rank, (_, row) in enumerate(top_hospitals.iterrows(), 1):
            name = row.get("기관명", "알 수 없음")
            dist = row.get("거리km", float("nan"))
            cls_name = row.get("병원분류명", "")
            address = row.get("주소", "")
            phone = row.get("응급실전화", "")
            with st.container(border=True):
                st.markdown(f"**{rank}위 — {name}**")
                c1, c2 = st.columns(2)
                c1.metric("거리", f"{dist:.2f} km")
                c2.metric("분류", cls_name if cls_name else "-")
                if address:
                    st.caption(f"주소: {address}")
                if phone:
                    st.caption(f"응급실 전화: {phone}")

st.divider()

# ── Folium 지도 ──────────────────────────────────────────────────────────────
st.subheader("🗺️ 지도로 보기")

m = folium.Map(location=[user_lat, user_lon], zoom_start=14)

# 내 위치
folium.Marker(
    location=[user_lat, user_lon],
    tooltip="📍 내 위치",
    icon=folium.Icon(color="blue", icon="user", prefix="fa"),
).add_to(m)

# 소방 안전센터 (빨강)
for _, row in top_stations.iterrows():
    if "위도" in row and "경도" in row:
        name = row.get("기관명", "")
        dist = row.get("거리km", 0)
        folium.Marker(
            location=[float(row["위도"]), float(row["경도"])],
            tooltip=f"🚒 {name} ({dist:.2f}km)",
            popup=folium.Popup(f"<b>{name}</b><br>거리: {dist:.2f}km", max_width=200),
            icon=folium.Icon(color="red", icon="fire", prefix="fa"),
        ).add_to(m)

# 응급실 (초록)
lat_c = "병원위도"
lon_c = "병원경도"
for _, row in top_hospitals.iterrows():
    if lat_c in row and lon_c in row:
        name = row.get("기관명", "")
        dist = row.get("거리km", 0)
        cls_nm = row.get("병원분류명", "")
        folium.Marker(
            location=[float(row[lat_c]), float(row[lon_c])],
            tooltip=f"🏥 {name} ({dist:.2f}km)",
            popup=folium.Popup(f"<b>{name}</b><br>{cls_nm}<br>거리: {dist:.2f}km", max_width=200),
            icon=folium.Icon(color="green", icon="hospital", prefix="fa"),
        ).add_to(m)

if _HAS_ST_FOLIUM:
    st_folium(m, width=None, height=500, returned_objects=[])
else:
    html_str = m._repr_html_()
    st.iframe(html_str, height=500, scrolling=False)

st.caption("🔴 소방 안전센터  🟢 응급실  🔵 내 위치 | 마커 클릭으로 상세 정보 확인")

st.divider()

with st.expander("💡 추천 알고리즘 안내"):
    st.markdown("""
    **소방 안전센터 추천**
    - Haversine 공식으로 내 위치 ↔ 전국 소방 안전센터(서울 한정, ~200개) 간 직선 거리 계산
    - 거리 오름차순 TOP-3 반환

    **응급실 추천**
    - Haversine 거리 계산 후 응급의료기관 분류에 따른 가중치 적용
    - 권역응급의료센터(×0.70) → 지역응급의료센터(×0.85) → 지역응급의료기관(×1.00)
    - 가중 점수 오름차순 TOP-3 반환 (같은 거리라면 상위 분류 병원이 우선 추천)

    **주의:** 직선 거리 기반이므로 실제 도로 이동 시간과 차이가 있을 수 있습니다.
    응급 상황에서는 **119 신고(119)**를 최우선으로 하세요.
    """)

st.info(
    "**⚠️ 실제 응급 상황에서는 119에 먼저 신고하세요.**  \n"
    "이 서비스는 데이터 분석 목적의 참고용입니다."
)
