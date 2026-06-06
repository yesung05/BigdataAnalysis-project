"""AI Tool Calling 도구 스키마(TOOLS) + 디스패처(run_tool).

우선순위: data/analytics/*.json 파일 (사전 계산, 전체 데이터) → 없으면 live 계산(샘플)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent
_PROJ_DIR = _APP_DIR.parent
sys.path.insert(0, str(_PROJ_DIR))
sys.path.insert(0, str(_APP_DIR))

_ANALYTICS_DIR = _PROJ_DIR / "data" / "analytics"

# ── 서울 25개 자치구 중심 좌표 ────────────────────────────────────────────────
SEOUL_DISTRICTS: dict[str, tuple[float, float]] = {
    "강남구": (37.5172, 127.0473), "강동구": (37.5301, 127.1238),
    "강북구": (37.6396, 127.0255), "강서구": (37.5509, 126.8495),
    "관악구": (37.4784, 126.9516), "광진구": (37.5384, 127.0822),
    "구로구": (37.4954, 126.8874), "금천구": (37.4567, 126.8956),
    "노원구": (37.6541, 127.0568), "도봉구": (37.6688, 127.0471),
    "동대문구": (37.5744, 127.0401), "동작구": (37.5124, 126.9393),
    "마포구": (37.5615, 126.9088), "서대문구": (37.5791, 126.9368),
    "서초구": (37.4836, 127.0327), "성동구": (37.5633, 127.0369),
    "성북구": (37.5894, 127.0167), "송파구": (37.5145, 127.1059),
    "양천구": (37.5270, 126.8561), "영등포구": (37.5264, 126.8965),
    "용산구": (37.5311, 126.9809), "은평구": (37.6026, 126.9291),
    "종로구": (37.5735, 126.9790), "중구":   (37.5641, 126.9978),
    "중랑구": (37.6063, 127.0925),
}


# ── JSON 헬퍼 ────────────────────────────────────────────────────────────────
def _load(name: str) -> dict | None:
    """data/analytics/{name}.json 읽기. 없거나 실패하면 None."""
    path = _ANALYTICS_DIR / f"{name}.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _normalize_district(name: str) -> str:
    name = name.strip()
    if name and not name.endswith("구"):
        name += "구"
    return name


# ── OpenAI 도구 스키마 ───────────────────────────────────────────────────────
TOOLS: list[dict] = [
    # ── 분석 조회 ───────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "query_district_transfer_rate",
            "description": (
                "서울 자치구별 2차 이송(뺑뺑이) 발생률을 조회한다. "
                "district를 지정하면 해당 구 상세 정보만, 생략하면 25개 구 전체 순위를 반환한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string", "description": "자치구명 (예: '강남구'). 생략 가능."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_station_load_ranking",
            "description": "서울 소방 안전센터별 구급 출동 건수 순위를 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "top_n": {"type": "integer", "description": "반환할 순위 수 (기본 10, 최대 100)."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_symptom_severity",
            "description": (
                "주증상별 중증도 분포(긴급·응급·비응급·사망 비율)를 조회한다. "
                "symptom 지정 시 해당 증상만, 생략 시 빈도 상위 15개를 반환한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symptom": {"type": "string", "description": "주증상 이름 (예: '흉통'). 생략 가능."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_seasonal_demand",
            "description": "서울 구급 출동 건수의 계절·월·시간대별 패턴을 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "by": {
                        "type": "string",
                        "enum": ["season", "month", "hour", "all"],
                        "description": "'season'=계절, 'month'=월, 'hour'=시간대, 'all'=모두.",
                    }
                },
                "required": ["by"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_weather_correlation",
            "description": "기상 변수(기온·강수량·풍속·습도)와 구급 출동 건수 간 Pearson 상관계수를 반환한다.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_yearly_trend",
            "description": "서울 구급 출동 건수와 2차 이송률의 연도별 추이(2017~2022)를 반환한다.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_transfer_analysis",
            "description": "2차 이송(뺑뺑이) 거부 이유별 건수와 추가 이동 거리 통계를 반환한다.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_er_transfer_correlation",
            "description": (
                "자치구별 응급실 수와 2차 이송 발생률 간의 Pearson 상관분석 결과를 반환한다. "
                "'응급실이 많으면 뺑뺑이가 줄어드는가' 질문에 답한다."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_dispatch_completion",
            "description": "증상별 완료이송율(정상 종결 비율) 상위·하위 목록을 반환한다.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_hospitals_in_district",
            "description": "특정 자치구에 있는 응급실 목록(병원명·분류·전화번호)을 반환한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string", "description": "자치구명 (예: '강동구')."}
                },
                "required": ["district"],
            },
        },
    },
    # ── 위치 기반 추천 ──────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "recommend_hospitals_nearby",
            "description": (
                "자치구 중심 좌표를 기준으로 가장 가까운 응급실 TOP-N을 추천한다. "
                "거리·분류·전화번호를 포함한다. 실시간 병상 정보는 get_realtime_er_beds를 사용하라."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string", "description": "기준 자치구명."},
                    "symptom":  {"type": "string", "description": "환자 주요 증상. 생략 가능."},
                    "topk":     {"type": "integer", "description": "추천 개수 (기본 3)."},
                },
                "required": ["district"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_stations_nearby",
            "description": "자치구 중심 좌표 기준으로 가장 가까운 소방 안전센터 TOP-N을 추천한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string", "description": "기준 자치구명."},
                    "topk":     {"type": "integer", "description": "추천 개수 (기본 3)."},
                },
                "required": ["district"],
            },
        },
    },
    # ── E-Gen 실시간 ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_realtime_er_beds",
            "description": (
                "E-Gen API로 지금 이 자치구 응급실의 실시간 가용 병상 수와 장비 현황을 조회한다. "
                "'지금', '현재', '실시간' 키워드가 있을 때 우선 사용하라."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string", "description": "조회할 자치구명."}
                },
                "required": ["district"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_severe_disease_acceptance",
            "description": (
                "E-Gen API로 지금 중증질환자를 수용할 수 있는 응급실을 조회한다. "
                "흉통·뇌졸중·중증외상 등 심각한 증상일 때 우선 사용하라."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string", "description": "조회할 자치구명."},
                    "symptom":  {"type": "string", "description": "환자 증상 (예: '흉통', '의식저하'). 생략 가능."},
                },
                "required": ["district"],
            },
        },
    },
]


# ════════════════════════════════════════════════════════════════════════════
# 도구 구현
# ════════════════════════════════════════════════════════════════════════════

def _query_district_transfer_rate(args: dict) -> str:
    data = _load("district_transfer")
    district = _normalize_district(args.get("district", "")) if args.get("district") else None

    if data:
        districts = data.get("districts", [])
        meta = data.get("meta", {})
        note = f"(전체 CSV, {meta.get('years', [])} 기준)"

        if district:
            row = next((d for d in districts if d["district"] == district), None)
            if not row:
                return f"'{district}' 데이터를 찾을 수 없습니다."
            return (
                f"## {district} 2차 이송(뺑뺑이) 현황 {note}\n"
                f"- 발생률: **{row['rate_pct']:.3f}%** (전체 순위 {row['rank']}위 / {len(districts)}개 구)\n"
                f"- 출동 건수: {row['dispatches']:,}건\n"
                f"- 2차 이송 발생: {row['transfers']:,}건\n"
                f"- 서울 평균: {data.get('seoul_avg_pct', 0):.3f}%"
            )
        lines = [
            f"- {d['rank']}위 {d['district']}: **{d['rate_pct']:.3f}%** ({d['transfers']:,}건 / {d['dispatches']:,}건)"
            for d in districts
        ]
        highest = data.get("highest", {})
        lowest  = data.get("lowest", {})
        return (
            f"## 서울 자치구별 2차 이송 발생률 (높은 순) {note}\n"
            + "\n".join(lines)
            + f"\n\n서울 평균: {data.get('seoul_avg_pct', 0):.3f}% | "
            + f"최고: {highest.get('district','')} {highest.get('rate_pct',0):.3f}% | "
            + f"최저: {lowest.get('district','')} {lowest.get('rate_pct',0):.3f}%"
        )

    # fallback: live 계산
    try:
        from cache import get_district_transfer_rate
        df = get_district_transfer_rate().sort_values("발생률", ascending=False)
        if district:
            row = df[df["자치구"] == district]
            if row.empty:
                return f"'{district}' 데이터를 찾을 수 없습니다."
            r = row.iloc[0]
            return (f"## {district} 2차 이송 현황 (샘플 추정)\n"
                    f"- 발생률: {r['발생률']:.3f}%\n"
                    f"- 출동: {int(r['출동건수']):,}건 / 2차이송: {int(r['이송2차건수']):,}건")
        lines = [f"- {row['자치구']}: {row['발생률']:.3f}%" for _, row in df.iterrows()]
        return "## 자치구별 2차 이송 발생률 (샘플 추정)\n" + "\n".join(lines)
    except Exception as e:
        return f"⚠️ 조회 실패: {e}"


def _query_station_load_ranking(args: dict) -> str:
    top_n = min(int(args.get("top_n", 10)), 100)
    data = _load("station_load")

    if data:
        rankings = data.get("rankings", [])[:top_n]
        meta = data.get("meta", {})
        lines = [f"- {r['rank']}위 **{r['name']}**: {r['dispatches']:,}건" for r in rankings]
        return (f"## 소방 안전센터 출동 순위 TOP {top_n} "
                f"(전체 CSV, {meta.get('years',[])} 기준)\n"
                + "\n".join(lines))

    try:
        from cache import get_center_counts
        df = get_center_counts().head(top_n)
        lines = [f"- {i+1}위 {row['CNTR_NM']}: {int(row['출동건수']):,}건"
                 for i, (_, row) in enumerate(df.iterrows())]
        return f"## 소방 안전센터 출동 순위 TOP {top_n} (샘플 추정)\n" + "\n".join(lines)
    except Exception as e:
        return f"⚠️ 조회 실패: {e}"


def _query_symptom_severity(args: dict) -> str:
    symptom = args.get("symptom", "")
    data = _load("symptom_severity")

    if data:
        symptoms = data.get("symptoms", [])
        meta = data.get("meta", {})
        note = f"(전체 mgmt CSV, {meta.get('years',[])} 기준)"
        if symptom:
            matches = [s for s in symptoms if symptom in s["symptom"]]
            if not matches:
                return f"'{symptom}' 증상 데이터를 찾을 수 없습니다."
            lines = []
            for s in matches[:5]:
                sev_str = ", ".join(f"{k}: {v:.1f}%" for k, v in sorted(s["severity"].items(), key=lambda x: -x[1]))
                lines.append(f"- **{s['symptom']}** ({s['total']:,}건): {sev_str}")
            return f"## '{symptom}' 관련 증상 중증도 분포 {note}\n" + "\n".join(lines)
        lines = []
        for s in symptoms[:15]:
            sev_str = ", ".join(f"{k}: {v:.1f}%" for k, v in sorted(s["severity"].items(), key=lambda x: -x[1]) if v >= 5)
            lines.append(f"- **{s['symptom']}** ({s['total']:,}건): {sev_str}")
        return f"## 주증상별 중증도 분포 TOP 15 {note}\n" + "\n".join(lines)

    try:
        from cache import get_mgmt
        import pandas as pd
        mgmt = get_mgmt()
        if "MAIN_SYM_NM" not in mgmt.columns:
            return "⚠️ 증상 컬럼 없음."
        valid = mgmt.dropna(subset=["MAIN_SYM_NM", "SRIL_CLSF_NM"])
        if symptom:
            valid = valid[valid["MAIN_SYM_NM"].str.contains(symptom, na=False)]
        top = valid["MAIN_SYM_NM"].value_counts().head(15).index
        pivot = valid[valid["MAIN_SYM_NM"].isin(top)].groupby(["MAIN_SYM_NM","SRIL_CLSF_NM"]).size().unstack(fill_value=0)
        pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
        lines = [f"- {sym}: " + ", ".join(f"{c}: {pct.loc[sym,c]:.1f}%" for c in pct.columns if pct.loc[sym,c] >= 5)
                 for sym in pct.index]
        return "## 주증상별 중증도 (샘플)\n" + "\n".join(lines)
    except Exception as e:
        return f"⚠️ 조회 실패: {e}"


def _query_seasonal_demand(args: dict) -> str:
    by = args.get("by", "all")
    data = _load("seasonal_demand")

    if data:
        meta = data.get("meta", {})
        note = f"(전체 CSV, {meta.get('years',[])} 기준, 총 {meta.get('total',0):,}건)"
        parts = []

        if by in ("season", "all") and data.get("by_season"):
            lines = [f"- **{s['season']}**: {s['dispatches']:,}건 ({s['pct']:.1f}%)" for s in data["by_season"]]
            parts.append("### 계절별\n" + "\n".join(lines))

        if by in ("month", "all") and data.get("by_month"):
            lines = [f"- {s['month_name']}: {s['dispatches']:,}건 ({s['pct']:.1f}%)" for s in data["by_month"]]
            parts.append("### 월별\n" + "\n".join(lines))

        if by in ("hour", "all") and data.get("by_hour"):
            lines = [f"- {s['time_range']}: {s['dispatches']:,}건 ({s['pct']:.1f}%)" for s in data["by_hour"]]
            parts.append("### 시간대별\n" + "\n".join(lines))

        insight = data.get("insight", "")
        return (f"## 구급 출동 시간 패턴 {note}\n"
                + "\n\n".join(parts)
                + (f"\n\n💡 {insight}" if insight else ""))

    try:
        from cache import get_dispatch
        df = get_dispatch()
        seoul = df[df["GRNDS_CTPV_NM"].str.contains("서울", na=False)]
        parts = []
        if by in ("season", "all") and "SEASN_NM" in seoul.columns:
            vc = seoul["SEASN_NM"].value_counts()
            t = vc.sum()
            parts.append("### 계절별 (샘플)\n" + "\n".join(f"- {s}: {c:,}건 ({c/t*100:.1f}%)" for s, c in vc.items()))
        if by in ("month", "all") and "DCLR_MM" in seoul.columns:
            vc = seoul.groupby("DCLR_MM").size().sort_index()
            t = vc.sum()
            parts.append("### 월별 (샘플)\n" + "\n".join(f"- {int(m)}월: {v:,}건 ({v/t*100:.1f}%)" for m, v in vc.items()))
        if not parts:
            return "⚠️ 계절/월 컬럼이 샘플 데이터에 없습니다. scripts/generate_analytics.py를 먼저 실행하세요."
        return "## 구급 출동 시간 패턴 (샘플 추정)\n" + "\n\n".join(parts)
    except Exception as e:
        return f"⚠️ 조회 실패: {e}"


def _query_weather_correlation(args: dict) -> str:
    data = _load("weather_correlation")

    if data:
        corrs = data.get("correlations", [])
        meta = data.get("meta", {})
        lines = []
        for c in corrs:
            sig = "✅ 유의(p<0.05)" if c["significant"] else "비유의"
            lines.append(f"- **{c['variable']}**: r={c['r']:.3f}, p={c['p']:.4f}, r²={c['r2']:.3f} ({sig})")
        note = f"(전체 CSV, {meta.get('years',[])} 기준, {meta.get('days_analyzed',0):,}일 분석)"
        return "## 기상 변수 × 구급 출동 건수 Pearson 상관 " + note + "\n" + "\n".join(lines)

    try:
        from scipy.stats import pearsonr
        from cache import get_dispatch
        df = get_dispatch()
        seoul = df[df["GRNDS_CTPV_NM"].str.contains("서울", na=False)]
        wmap = {"HR_UNIT_ARTMP":"기온(°C)","HR_UNIT_RN":"강수량","HR_UNIT_WSPD":"풍속","HR_UNIT_HUM":"습도"}
        avail = [c for c in wmap if c in seoul.columns]
        if not avail:
            return "⚠️ 기상 컬럼 없음."
        agg = {"GRNDS_SGG_NM": "count"}
        agg.update({c: "mean" for c in avail})
        daily = seoul.groupby("DCLR_YMD").agg(agg).rename(columns={"GRNDS_SGG_NM":"count"}).dropna()
        lines = []
        for c in avail:
            if daily[c].std() > 0:
                r, p = pearsonr(daily["count"], daily[c])
                lines.append(f"- {wmap[c]}: r={r:.3f}, p={p:.4f} ({'유의' if p<0.05 else '비유의'})")
        return "## 기상 × 출동 Pearson 상관 (샘플)\n" + "\n".join(lines)
    except Exception as e:
        return f"⚠️ 조회 실패: {e}"


def _query_yearly_trend(args: dict) -> str:
    data = _load("yearly_trend")
    if data:
        yearly = data.get("yearly", [])
        lines = [
            f"- {y['year']}년: {y['dispatches']:,}건 (2차이송률 {y['transfer_rate_pct']:.3f}%, {y['transfers']:,}건)"
            for y in yearly
        ]
        return "## 서울 구급 출동 연도별 추이 (전체 CSV)\n" + "\n".join(lines)
    return "⚠️ 연도별 통계 파일이 없습니다. scripts/generate_analytics.py를 먼저 실행하세요."


def _query_transfer_analysis(args: dict) -> str:
    data = _load("transfer_analysis")
    if data:
        reasons = data.get("reasons", [])
        dist   = data.get("distance_km", {})
        meta   = data.get("meta", {})
        r_lines = [f"- **{r['reason']}**: {r['count']:,}건 ({r['pct']:.1f}%)" for r in reasons]
        d_lines = []
        if dist:
            d_lines = [
                f"- 중앙값: {dist.get('median',0):.2f}km | 평균: {dist.get('mean',0):.2f}km",
                f"- 25%ile: {dist.get('p25',0):.2f}km / 75%ile: {dist.get('p75',0):.2f}km / 90%ile: {dist.get('p90',0):.2f}km",
                f"- 최대: {dist.get('max',0):.1f}km | 2차이송 전체 건수: {dist.get('count',0):,}건",
            ]
        note = f"(전체 CSV, {meta.get('years',[])} 기준)"
        return (
            f"## 2차 이송(뺑뺑이) 분석 {note}\n"
            "### 거부 이유별 건수\n" + "\n".join(r_lines)
            + ("\n\n### 추가 이동 거리 통계\n" + "\n".join(d_lines) if d_lines else "")
        )
    return "⚠️ 분석 파일이 없습니다. scripts/generate_analytics.py를 먼저 실행하세요."


def _query_er_transfer_correlation(args: dict) -> str:
    data = _load("er_transfer_corr")
    if not data or "pearson_r" not in data:
        return "⚠️ 상관분석 파일이 없습니다. scripts/generate_analytics.py를 먼저 실행하세요."
    r, p = data["pearson_r"], data["p_value"]
    sig = "✅ 통계적으로 유의(p<0.05)" if data["significant"] else "⚠️ 통계적으로 비유의"
    districts = data.get("districts", [])
    d_lines = [
        f"- {d['district']}: 응급실 {d['er_count']}개 / 2차이송률 {d['transfer_rate_pct']:.3f}%"
        for d in districts
    ]
    return (
        "## 자치구별 응급실 수 × 2차 이송 발생률 상관분석 (전체 데이터)\n"
        f"- Pearson r = **{r:.4f}**, p = {p:.4f} ({sig})\n"
        f"- r² = {data['r_squared']:.4f} → 응급실 수가 2차이송률 변동의 {data['r_squared']*100:.1f}% 설명\n"
        f"- 방향: {data['direction']}\n"
        "\n### 자치구별 상세 (응급실 많은 순)\n" + "\n".join(d_lines)
    )


def _query_dispatch_completion(args: dict) -> str:
    data = _load("dispatch_completion")
    if not data:
        return "⚠️ 완료이송율 파일이 없습니다. scripts/generate_analytics.py를 먼저 실행하세요."
    top = data.get("top_completion", [])
    bot = data.get("bottom_completion", [])
    meta = data.get("meta", {})
    t_lines = [f"- {r['symptom']}: {r['completion_rate_pct']:.1f}% ({r['count']:,}건)" for r in top]
    b_lines = [f"- {r['symptom']}: {r['completion_rate_pct']:.1f}% ({r['count']:,}건)" for r in bot]
    return (
        f"## 증상별 완료이송율 (전체 CSV, {meta.get('years',[])} 기준)\n"
        "### 완료율 상위 15개\n" + "\n".join(t_lines)
        + "\n\n### 완료율 하위 15개\n" + "\n".join(b_lines)
    )


def _list_hospitals_in_district(args: dict) -> str:
    district = _normalize_district(args.get("district", ""))
    data = _load("er_locations")

    if data:
        by_dist = data.get("by_district", {})
        hospitals = by_dist.get(district)
        if hospitals is None:
            return f"'{district}' 응급실 데이터를 찾을 수 없습니다. 서울 25개 자치구만 지원합니다."
        lines = [
            f"- **{h['name']}** ({h['class']}) — ☎ {h['phone']}\n  주소: {h['address']}"
            for h in hospitals
        ]
        return f"## {district} 응급실 목록 ({len(hospitals)}개소)\n" + "\n".join(lines)

    try:
        from cache import get_er_locations
        er = get_er_locations().copy()
        er["자치구"] = er["주소"].str.split().str[1]
        subset = er[er["자치구"] == district]
        if subset.empty:
            return f"'{district}' 응급실 데이터를 찾을 수 없습니다."
        lines = [f"- {r['기관명']} ({r.get('병원분류명','')}) — {r.get('응급실전화','')}"
                 for _, r in subset.iterrows()]
        return f"## {district} 응급실 목록 ({len(subset)}개소)\n" + "\n".join(lines)
    except Exception as e:
        return f"⚠️ 조회 실패: {e}"


def _recommend_hospitals_nearby(args: dict) -> str:
    from cache import get_er_locations
    from src.recommend.hospital import recommend_hospitals
    district = _normalize_district(args.get("district", ""))
    symptom  = args.get("symptom", "")
    topk     = int(args.get("topk", 3))
    coords   = SEOUL_DISTRICTS.get(district)
    if coords is None:
        return f"'{district}' 좌표 정보가 없습니다."
    lat, lon = coords
    result = recommend_hospitals(lat, lon, symptom, get_er_locations(), topk=topk)
    if result.empty:
        return "추천 결과가 없습니다."
    lines = []
    for i, (_, row) in enumerate(result.iterrows(), 1):
        name  = row.get("기관명", "")
        dist  = row.get("거리km", float("nan"))
        cls   = row.get("병원분류명", "")
        phone = row.get("응급실전화", "")
        addr  = row.get("주소", "")
        lines.append(f"{i}위 **{name}** ({cls})\n   거리: {dist:.2f}km | ☎ {phone}\n   주소: {addr}")
    header = f"## {district} 기준 가까운 응급실 TOP {topk}"
    if symptom:
        header += f" (증상: {symptom})"
    return header + "\n" + "\n".join(lines)


def _recommend_stations_nearby(args: dict) -> str:
    from cache import get_station_coords
    from src.recommend.station import recommend_stations
    district = _normalize_district(args.get("district", ""))
    topk     = int(args.get("topk", 3))
    coords   = SEOUL_DISTRICTS.get(district)
    if coords is None:
        return f"'{district}' 좌표 정보가 없습니다."
    lat, lon = coords
    station_df = get_station_coords()
    seoul_stn = station_df[
        station_df["위도"].between(37.40, 37.72) & station_df["경도"].between(126.73, 127.25)
    ].copy()
    result = recommend_stations(lat, lon, seoul_stn, topk=topk)
    if result.empty:
        return "추천 결과가 없습니다."
    lines = [f"{i+1}위 **{row.get('기관명','')}** ({row.get('유형','')}) — {row.get('거리km',0):.2f}km"
             for i, (_, row) in enumerate(result.iterrows())]
    return f"## {district} 기준 가까운 소방 안전센터 TOP {topk}\n" + "\n".join(lines)


def _get_realtime_er_beds(args: dict) -> str:
    """NEMC Mediboard 실시간 병상 조회 — 서울 전체에서 해당 자치구 병원 필터."""
    from src.api.nemc import handy_beds, SYMPTOM_YCODES
    district = _normalize_district(args.get("district", ""))
    symptom  = args.get("symptom", "")
    try:
        all_hospitals = handy_beds(emogloca=11)
    except Exception as e:
        return f"⚠️ 실시간 조회 실패: {e}\n정적 목록은 list_hospitals_in_district를 사용하세요."

    # 자치구 필터
    items = [h for h in all_hospitals
             if district in h.get("address", "")]
    if not items:
        items = all_hospitals  # fallback: 전체 반환

    y_codes = set(SYMPTOM_YCODES.get(symptom, []))
    lines = []
    for h in items:
        avail = h.get("generalEmergencyAvailable", "?")
        total = h.get("generalEmergencyTotal", "?")
        child = h.get("childEmergencyAvailable")
        npir  = h.get("npirAvailable")

        beds_parts = [f"응급실 {avail}/{total}개"]
        if child is not None:
            beds_parts.append(f"소아 {child}개")
        if npir is not None:
            beds_parts.append(f"음압 {npir}개")

        unavail_codes = {m.get("code") for m in h.get("unavailableMessages", [])}
        if y_codes and y_codes & unavail_codes:
            sym_tag = f" ❌ {symptom} 수용불가"
        elif y_codes:
            sym_tag = f" ✅ {symptom} 수용거부 기록없음"
        else:
            sym_tag = ""

        er_msg = h.get("erMessages", [])
        msg_str = f"\n  📢 {er_msg[0]['message'][:50]}" if er_msg else ""

        lines.append(
            f"**{h.get('emergencyRoomName','')}** "
            f"({h.get('emergencyInstitutionType','')}){sym_tag}\n"
            f"  병상: {', '.join(beds_parts)}{msg_str}"
        )

    header = f"## {district} 응급실 실시간 병상 현황" if district else "## 서울 응급실 실시간 병상 현황"
    return header + "\n" + "\n\n".join(lines)


def _get_severe_disease_acceptance(args: dict) -> str:
    """NEMC unavailableMessages로 중증질환 수용 가능 응급실 조회."""
    from src.api.nemc import handy_beds, SYMPTOM_YCODES
    district = _normalize_district(args.get("district", ""))
    symptom  = args.get("symptom", "")
    y_codes  = set(SYMPTOM_YCODES.get(symptom, []))
    try:
        all_hospitals = handy_beds(emogloca=11)
    except Exception as e:
        return f"⚠️ 실시간 조회 실패: {e}"

    items = [h for h in all_hospitals if district in h.get("address", "")]
    if not items:
        return f"'{district}' 응급실 정보가 없습니다."

    lines = []
    for h in items:
        unavail_codes = {m.get("code") for m in h.get("unavailableMessages", [])}
        if y_codes:
            rejected = bool(y_codes & unavail_codes)
            ok_tag = "❌ 수용 불가" if rejected else "✅ 수용 거부 기록없음"
        else:
            ok_tag = ""
        avail = h.get("generalEmergencyAvailable", "?")
        total = h.get("generalEmergencyTotal", "?")
        lines.append(
            f"{ok_tag} **{h.get('emergencyRoomName','')}** "
            f"(응급실 {avail}/{total}개)"
        )
    header = f"## {district} 중증질환 수용 현황"
    if symptom:
        header += f" — {symptom}"
    return header + "\n" + "\n".join(lines)


# ── 디스패치 테이블 ──────────────────────────────────────────────────────────
_DISPATCH: dict = {
    "query_district_transfer_rate":  _query_district_transfer_rate,
    "query_station_load_ranking":    _query_station_load_ranking,
    "query_symptom_severity":        _query_symptom_severity,
    "query_seasonal_demand":         _query_seasonal_demand,
    "query_weather_correlation":     _query_weather_correlation,
    "query_yearly_trend":            _query_yearly_trend,
    "query_transfer_analysis":       _query_transfer_analysis,
    "query_er_transfer_correlation": _query_er_transfer_correlation,
    "query_dispatch_completion":     _query_dispatch_completion,
    "list_hospitals_in_district":    _list_hospitals_in_district,
    "recommend_hospitals_nearby":    _recommend_hospitals_nearby,
    "recommend_stations_nearby":     _recommend_stations_nearby,
    "get_realtime_er_beds":          _get_realtime_er_beds,
    "get_severe_disease_acceptance": _get_severe_disease_acceptance,
}


def run_tool(name: str, args: dict) -> str:
    try:
        return _DISPATCH[name](args)
    except KeyError:
        return f"⚠️ 알 수 없는 도구: {name}"
    except Exception as exc:
        return f"⚠️ {name} 실행 실패: {exc}"


# ── analytics 기반 시스템 프롬프트 보강 ─────────────────────────────────────
def build_analytics_context() -> str:
    """사전 계산된 JSON에서 핵심 통계를 읽어 시스템 프롬프트용 컨텍스트 생성."""
    sections: list[str] = []

    dt = _load("district_transfer")
    if dt:
        top5 = dt["districts"][:5]
        bot5 = dt["districts"][-5:]
        lines = [f"  - {d['district']}: {d['rate_pct']:.3f}%" for d in top5]
        lines += ["  - ..."]
        lines += [f"  - {d['district']}: {d['rate_pct']:.3f}%" for d in bot5]
        sections.append(
            f"**2차 이송(뺑뺑이) 발생률** (서울 평균 {dt.get('seoul_avg_pct',0):.3f}%, "
            f"{dt['meta'].get('years',[])} 전체 데이터 기준)\n"
            + "\n".join(lines)
        )

    sd = _load("seasonal_demand")
    if sd and sd.get("by_season"):
        s_str = " > ".join(f"{s['season']}({s['pct']:.1f}%)" for s in sd["by_season"])
        peak_m = sd["by_month"][0] if sd.get("by_month") else {}
        peak_h = sd["by_hour"][0] if sd.get("by_hour") else {}
        sections.append(
            f"**계절별 출동 패턴** (전체 데이터): {s_str}\n"
            f"  - 피크 월: {peak_m.get('month_name','')} ({peak_m.get('pct',0):.1f}%)\n"
            f"  - 피크 시간대: {peak_h.get('time_range','')} ({peak_h.get('pct',0):.1f}%)"
        )

    wc = _load("weather_correlation")
    if wc and wc.get("correlations"):
        sig = [c for c in wc["correlations"] if c["significant"]]
        if sig:
            sig_str = ", ".join(f"{c['variable']} r={c['r']:.3f}" for c in sig)
            sections.append(f"**기상 상관** (유의한 변수): {sig_str}")
        else:
            sections.append("**기상 상관**: 통계적으로 유의한 기상 변수 없음")

    stn = _load("station_load")
    if stn and stn.get("rankings"):
        top5s = stn["rankings"][:5]
        s_str = ", ".join(f"{r['name']}({r['dispatches']:,}건)" for r in top5s)
        sections.append(f"**출동 부하 상위 안전센터**: {s_str}")

    er = _load("er_locations")
    if er:
        total = er.get("meta", {}).get("total", 0)
        cls_str = ", ".join(f"{c['class']} {c['count']}개" for c in er.get("by_classification", []))
        sections.append(f"**서울 응급실 총 {total}개소**: {cls_str}")

    tc = _load("er_transfer_corr")
    if tc and "pearson_r" in tc:
        sig = "유의" if tc["significant"] else "비유의"
        sections.append(
            f"**응급실수 × 2차이송률 상관**: r={tc['pearson_r']:.3f} ({sig}), {tc['direction']}"
        )

    yt = _load("yearly_trend")
    if yt and yt.get("yearly"):
        first = yt["yearly"][0]
        last  = yt["yearly"][-1]
        sections.append(
            f"**연도별 추이**: {first['year']}년 {first['dispatches']:,}건 → "
            f"{last['year']}년 {last['dispatches']:,}건 "
            f"(2차이송률 {last['transfer_rate_pct']:.3f}%)"
        )

    if not sections:
        return ""
    return "## 사전 계산된 핵심 분석 결과 (전체 데이터 기반)\n\n" + "\n\n".join(sections)
