"""9. 추천 서비스 — 내 위치·증상 기반 실시간 응급실 추천."""
import sys
from pathlib import Path

import folium
import plotly.graph_objects as go
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
_APP_DIR   = _PAGES_DIR.parent
_PROJ_DIR  = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

from ai_tools import SEOUL_DISTRICTS
from cache import get_er_locations, get_station_coords
from src.recommend.hospital import recommend_hospitals, recommend_hospitals_realtime
from src.recommend.station import recommend_stations

# ── 병상 도넛 차트 헬퍼 ──────────────────────────────────────────────────────
def _bed_donut(avail, total, label: str):
    """가용/총 병상 도넛 차트. 가용률 기준 혼잡·보통·원활 색상."""
    if total is None or total <= 0:
        return None
    avail_safe = max(0, avail if avail is not None else 0)
    used  = max(0, total - avail_safe)
    ratio = avail_safe / total

    if ratio <= 0.33:
        status, color = "혼잡", "#EF4444"
    elif ratio <= 0.66:
        status, color = "보통", "#F59E0B"
    else:
        status, color = "원활", "#22C55E"

    display = avail if avail is not None else 0  # 음수(초과예약)도 그대로 표시

    fig = go.Figure(go.Pie(
        values=[avail_safe, used],
        labels=["가용", "사용중"],
        hole=0.58,
        marker=dict(colors=[color, "#E5E7EB"]),
        textinfo="none",
        hovertemplate="%{label}: %{value}개<extra></extra>",
        direction="clockwise",
        sort=False,
    ))
    fig.add_annotation(
        text=f"<b>{display}</b><br><sub>/{total}</sub>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color=color),
        xanchor="center", yanchor="middle",
    )
    fig.update_layout(
        title=dict(
            text=f"{label}<br><b style='color:{color}'>{status}</b>",
            x=0.5, xanchor="center",
            font=dict(size=11),
        ),
        showlegend=False,
        margin=dict(t=52, b=4, l=4, r=4),
        height=165,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


st.set_page_config(page_title="추천 서비스", layout="wide")
st.title("🚑 응급실 실시간 추천")
st.caption(
    "내 위치와 증상을 입력하면 **E-Gen 실시간 병상 정보**를 바탕으로 "
    "지금 받아줄 수 있는 응급실을 추천합니다."
)

# ── 증상 목록 (E-Gen MKioskTy 연동) ────────────────────────────────────────
SYMPTOMS = [
    "(선택 안 함)",
    "흉통", "심정지", "의식저하", "뇌졸중 의심",
    "호흡곤란", "외상·골절", "복통", "화상",
    "저혈당", "소아", "토혈·혈변",
]

# ── 세션 초기화 ──────────────────────────────────────────────────────────────
for _k, _v in [("rt_results", None), ("rt_error", None), ("rt_searched", False)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── 입력 UI ─────────────────────────────────────────────────────────────────
st.subheader("📍 위치 및 증상 입력")

_GPS_LABEL = "현재 위치 자동 감지 (GPS)"
_MODES = ([_GPS_LABEL, "자치구 선택", "위도·경도 직접 입력"]
          if _HAS_GEO else ["자치구 선택", "위도·경도 직접 입력"])

col_mode, col_sym = st.columns([2, 2])
with col_mode:
    input_mode = st.radio("입력 방식", _MODES, horizontal=True)
with col_sym:
    symptom = st.selectbox("🩺 주요 증상", SYMPTOMS)

user_lat, user_lon = 37.5665, 126.9780  # 기본값: 서울시청

if input_mode == _GPS_LABEL:
    with st.spinner("위치 정보를 가져오는 중…"):
        loc = get_geolocation()
    if loc and "coords" in loc:
        user_lat = loc["coords"]["latitude"]
        user_lon = loc["coords"]["longitude"]
        acc = loc["coords"].get("accuracy")
        st.success(
            f"위치 감지 완료: 위도 {user_lat:.5f}, 경도 {user_lon:.5f}"
            + (f" (±{acc:.0f}m)" if acc else "")
        )
    else:
        st.warning(
            "GPS 위치를 가져오지 못했습니다. 브라우저에서 위치 권한을 허용하세요.  \n"
            "기본값(서울시청)으로 표시합니다."
        )

elif input_mode == "자치구 선택":
    gu = st.selectbox("자치구", list(SEOUL_DISTRICTS.keys()))
    user_lat, user_lon = SEOUL_DISTRICTS[gu]
    st.caption(f"선택한 자치구 중심 좌표: {user_lat}, {user_lon}")

else:
    c1, c2 = st.columns(2)
    with c1:
        user_lat = st.number_input("위도", value=37.5665, format="%.4f", step=0.001)
    with c2:
        user_lon = st.number_input("경도", value=126.9780, format="%.4f", step=0.001)

st.divider()

# ── 찾기 버튼 ────────────────────────────────────────────────────────────────
col_btn, col_hint = st.columns([1, 3])
with col_btn:
    search_clicked = st.button("🔍 실시간 병원 찾기", type="primary", use_container_width=True)
with col_hint:
    st.caption(
        "E-Gen 응급의료정보 API로 현재 가용 병상과 중증질환 수용 여부를 조회합니다.  \n"
        "중증 증상(흉통·의식저하·외상 등)은 수용 가능 여부까지 추가 확인합니다."
    )

# ── 데이터 로드 ──────────────────────────────────────────────────────────────
station_df = get_station_coords()
er_df      = get_er_locations()

seoul_stations = station_df[
    station_df["위도"].between(37.40, 37.72) &
    station_df["경도"].between(126.73, 127.25)
].copy()

top_stations = recommend_stations(user_lat, user_lon, seoul_stations, topk=3)

# ── 실시간 병원 검색 실행 ────────────────────────────────────────────────────
if search_clicked:
    sym = symptom if symptom != "(선택 안 함)" else ""
    with st.spinner("E-Gen API에서 실시간 병상 정보를 조회 중입니다…"):
        try:
            results = recommend_hospitals_realtime(
                user_lat, user_lon, sym, er_df, topk=5
            )
            st.session_state["rt_results"] = results
            st.session_state["rt_error"]   = None
            st.session_state["rt_searched"] = True
        except Exception as e:
            st.session_state["rt_results"] = None
            st.session_state["rt_error"]   = str(e)
            st.session_state["rt_searched"] = True

# ── 결과 카드 ────────────────────────────────────────────────────────────────

# ① 추천 응급실 (상단 전체 너비, 2×n 그리드)
st.subheader("🏥 추천 응급실 TOP-5")

if st.session_state["rt_searched"] and st.session_state["rt_error"]:
    st.error(f"실시간 조회 오류: {st.session_state['rt_error']}")
    st.info("정적 거리 기반 결과로 대신 표시합니다.")

rt_list = st.session_state.get("rt_results")


def _render_rt_card(rank: int, h: dict):
    """실시간 병원 카드 (도넛 차트 포함)."""
    sym_ok   = h.get("symptom_ok")
    key_beds = h.get("key_bed_count")

    if sym_ok is False:
        badge = "🔴 수용 불가"
    elif key_beds is not None and key_beds <= 0:
        badge = "🔴 만실"
    elif key_beds is not None and key_beds > 0:
        badge = "🟢 병상 있음"
    else:
        badge = "⚪ 정보 없음"

    with st.container(border=True):
        nick = h.get("nickname", "")
        st.markdown(
            f"**{rank}위 — {h['name']}**"
            + (f" *({nick})*" if nick else "")
            + f"  {badge}"
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("거리", f"{h['distance_km']:.2f} km")
        c2.metric("이송 예상", f"약 {h['est_min']}분")
        c3.metric("분류", h.get("class", "-") or "-")

        # 도넛 차트
        _bed_specs = [
            (h.get("avail_general"),  h.get("total_general"),   "응급실 일반"),
            (h.get("avail_child"),    h.get("total_child"),     "소아 응급"),
            (h.get("avail_npir"),     h.get("total_npir"),      "음압격리"),
            (h.get("avail_inpatient"),h.get("total_inpatient"), "일반 입원"),
        ]
        charts = [
            (lbl, _bed_donut(av, tot, lbl))
            for av, tot, lbl in _bed_specs
            if tot is not None and tot > 0
        ]
        if charts:
            pie_cols = st.columns(len(charts))
            for pc, (lbl, fig) in zip(pie_cols, charts):
                pc.plotly_chart(
                    fig, use_container_width=True,
                    config={"displayModeBar": False},
                    key=f"pie_{rank}_{lbl}_{h.get('emog_code', rank)}",
                )
        else:
            st.caption("병상 데이터 없음")

        dlv = h.get("delivery_ok")
        if dlv == "Y":
            st.caption("🤱 분만실 가용")
        elif dlv == "N":
            st.caption("🚫 분만실 불가")

        unavail = h.get("unavail_messages", [])
        if unavail:
            cats = ", ".join(m.get("category", "") for m in unavail[:3])
            more = f" 외 {len(unavail)-3}건" if len(unavail) > 3 else ""
            st.caption(f"⚠️ 수용 불가: {cats}{more}")

        er_msgs = h.get("er_messages", [])
        if er_msgs:
            with st.expander(f"💬 병원 안내 {len(er_msgs)}건"):
                for msg in er_msgs:
                    st.caption(f"• {msg}")

        if h.get("phone"):
            st.caption(f"📞 {h['phone']}")
        if h.get("address"):
            st.caption(f"📍 {h['address']}")
        st.caption("📡 NEMC Mediboard 실시간")


if rt_list:
    # 2×n 그리드
    for row_i in range(0, len(rt_list), 2):
        grid_cols = st.columns(2)
        for col_j, h in enumerate(rt_list[row_i: row_i + 2]):
            with grid_cols[col_j]:
                _render_rt_card(row_i + col_j + 1, h)

elif st.session_state["rt_searched"]:
    # 검색했으나 결과 없음 → 정적 2열 fallback
    sym = symptom if symptom != "(선택 안 함)" else ""
    static_hospitals = recommend_hospitals(user_lat, user_lon, sym, er_df, topk=5)
    if static_hospitals.empty:
        st.warning("응급실 데이터를 불러올 수 없습니다.")
    else:
        st.caption("(실시간 데이터 없음 — 거리 기반 결과)")
        rows_df = list(static_hospitals.iterrows())
        for row_i in range(0, len(rows_df), 2):
            grid_cols = st.columns(2)
            for col_j, (_, row) in enumerate(rows_df[row_i: row_i + 2]):
                with grid_cols[col_j]:
                    with st.container(border=True):
                        st.markdown(f"**{row_i+col_j+1}위 — {row.get('기관명','?')}**")
                        ca, cb = st.columns(2)
                        ca.metric("거리", f"{row.get('거리km',0):.2f} km")
                        cb.metric("분류", row.get("병원분류명", "-") or "-")
                        if row.get("주소"):    st.caption(f"📍 {row['주소']}")
                        if row.get("응급실전화"): st.caption(f"📞 {row['응급실전화']}")

else:
    # 미검색 → 정적 미리보기 2열
    sym = symptom if symptom != "(선택 안 함)" else ""
    static_hospitals = recommend_hospitals(user_lat, user_lon, sym, er_df, topk=5)
    if not static_hospitals.empty:
        st.caption("거리 기반 미리보기 — 실시간 병상 정보 보려면 **🔍 실시간 병원 찾기** 클릭")
        rows_df = list(static_hospitals.iterrows())
        for row_i in range(0, len(rows_df), 2):
            grid_cols = st.columns(2)
            for col_j, (_, row) in enumerate(rows_df[row_i: row_i + 2]):
                with grid_cols[col_j]:
                    with st.container(border=True):
                        st.markdown(f"**{row_i+col_j+1}위 — {row.get('기관명','?')}**")
                        ca, cb = st.columns(2)
                        ca.metric("거리", f"{row.get('거리km',0):.2f} km")
                        cb.metric("분류", row.get("병원분류명", "-") or "-")
                        if row.get("응급실전화"): st.caption(f"📞 {row['응급실전화']}")

st.divider()

# ② 소방 안전센터 (하단, 기본 접힘)
with st.expander("🚒 가까운 소방 안전센터 TOP-3", expanded=False):
    if top_stations.empty:
        st.warning("소방 안전센터 데이터를 불러올 수 없습니다.")
    else:
        stn_cols = st.columns(3)
        for rank, (_, row) in enumerate(top_stations.iterrows(), 1):
            with stn_cols[rank - 1]:
                with st.container(border=True):
                    st.markdown(f"**{rank}위 — {row.get('기관명', '?')}**")
                    st.metric("거리", f"{row.get('거리km', 0):.2f} km")
                    st.metric("유형", row.get("유형", "-") or "-")
                    if row.get("상위 본부명"):
                        st.caption(f"관할: {row['상위 본부명']}")

st.divider()

# ── Folium 지도 ──────────────────────────────────────────────────────────────
st.subheader("🗺️ 지도로 보기")

m = folium.Map(location=[user_lat, user_lon], zoom_start=13)

# 내 위치 (파랑)
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

# 응급실 마커 — 실시간 결과 우선, 없으면 정적 fallback
def _hospital_marker_color(h: dict) -> str:
    """실시간 스코어 기반 마커 색상."""
    sym_ok   = h.get("symptom_ok")
    key_beds = h.get("key_bed_count")
    src      = h.get("data_source", "static")
    if src == "static":
        return "gray"
    if key_beds == 0:
        return "darkred"     # 만실
    if sym_ok is False:
        return "darkred"     # 수용 불가
    if sym_ok is True:
        return "green"       # 수용 가능
    if key_beds is not None and key_beds > 0:
        return "orange"      # 병상 있음, 수용 정보 없음
    return "cadetblue"       # 실시간 조회됐지만 병상 정보 없음


if rt_list:
    for h in rt_list:
        if not (h.get("lat") and h.get("lon")):
            continue
        color    = _hospital_marker_color(h)
        sym_ok   = h.get("symptom_ok")
        key_beds = h.get("key_bed_count")
        badge_txt = (
            "✅ 수용 가능" if sym_ok is True else
            "❌ 수용 불가" if sym_ok is False else
            f"병상 {key_beds}개" if key_beds is not None else "정보 없음"
        )
        popup_html = (
            f"<b>{h['name']}</b><br>"
            f"{h.get('class','')}<br>"
            f"거리: {h['distance_km']:.2f}km ({h['est_min']}분)<br>"
            f"{badge_txt}<br>"
            f"📞 {h.get('phone','')}"
        )
        folium.Marker(
            location=[h["lat"], h["lon"]],
            tooltip=f"🏥 {h['name']} ({h['distance_km']:.2f}km) {badge_txt}",
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color=color, icon="hospital", prefix="fa"),
        ).add_to(m)
else:
    # 정적 마커 (회색)
    sym = symptom if symptom != "(선택 안 함)" else ""
    static_hospitals = recommend_hospitals(user_lat, user_lon, sym, er_df, topk=5)
    for _, row in static_hospitals.iterrows():
        if "병원위도" in row and "병원경도" in row:
            name     = row.get("기관명", "")
            dist     = row.get("거리km", 0)
            cls_name = row.get("병원분류명", "")
            popup_html = f"<b>{name}</b><br>{cls_name}<br>거리: {dist:.2f}km"
            folium.Marker(
                location=[float(row["병원위도"]), float(row["병원경도"])],
                tooltip=f"🏥 {name} ({dist:.2f}km)",
                popup=folium.Popup(popup_html, max_width=200),
                icon=folium.Icon(color="gray", icon="hospital", prefix="fa"),
            ).add_to(m)

if _HAS_ST_FOLIUM:
    st_folium(m, width=None, height=500, returned_objects=[])
else:
    st.components.v1.html(m._repr_html_(), height=500, scrolling=False)

st.caption(
    "🔵 내 위치  🔴 소방 안전센터  "
    "🟢 수용 가능  🟠 병상 있음  🔴 수용불가/만실  ⚪ 정보없음"
)

st.divider()

with st.expander("💡 추천 알고리즘 안내"):
    st.markdown("""
**실시간 병원 추천 (E-Gen API)**
- 거리 기반 후보 15개 추출 후 E-Gen API 실시간 조회
- 스코어 = 거리 × 분류가중치 × 병상팩터 × 증상수용팩터 (낮을수록 우선)
- 분류가중치: 권역응급의료센터(×0.65), 지역응급의료센터(×0.80), 기관(×1.00)
- 병상팩터: >10개(×0.60), 5-10개(×0.75), 1-4개(×0.90), 0개(×2.00), 정보없음(×1.00)
- 증상수용팩터: 수용 가능(×0.50), 수용 불가(×2.50), 정보없음(×1.00)
- 중증 증상(흉통·의식저하·외상 등)은 중증질환 수용 가능 정보(오퍼레이션 2)도 조회

**소방 안전센터 추천**
- Haversine 거리 계산 후 거리 오름차순 TOP-3 반환

**지도 마커 색상**
- 🟢 초록: 수용 가능 + 병상 있음 | 🟠 주황: 병상 있음 (수용정보 없음)
- 🔴 진빨강: 수용 불가 또는 만실 | ⚪ 회색: 실시간 데이터 없음
    """)

st.info(
    "**⚠️ 실제 응급 상황에서는 119에 먼저 신고하세요.**  \n"
    "이 서비스는 데이터 분석 목적의 참고용이며, 실제 이송 결정에 활용하지 마세요."
)
