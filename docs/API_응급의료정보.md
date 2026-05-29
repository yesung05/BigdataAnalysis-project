# 전국 응급의료정보조회 API 레퍼런스

**서비스명(영문):** `ErmctInfoInqireService`  
**Base URL:** `http://apis.data.go.kr/B552657/ErmctInfoInqireService`  
**방식:** REST GET / 응답: XML  
**갱신주기:** 일 1회 (병상정보는 실시간)  
**API 키:** `.env`의 `EMER_API_KEY` 사용

---

## 오퍼레이션 목록

| # | 오퍼레이션(영문) | 설명 | 프로젝트 활용 |
|---|----------------|------|-------------|
| 1 | `getEmrrmRltmUsefulSckbdInfoInqire` | 응급실 **실시간** 가용병상 조회 | ★ 병원 추천 핵심 |
| 2 | `getSrsillDissAceptncPosblInfoInqire` | 중증질환자 수용가능정보 조회 | ★ 중증 증상 추천 |
| 3 | `getEgytListInfoInqire` | 응급의료기관 목록 조회 | 병원 목록 수집 |
| 4 | `getEgytLcinfoInqire` | 응급의료기관 위치정보 조회 | GPS 좌표 수집 |
| 5 | `getEgytBassInfoInqire` | 응급의료기관 기본정보 조회 | 진료과목 수집 |
| 6 | `getStrmListInfoInqire` | 외상센터 목록 조회 | 외상 추천 |
| 7 | `getStrmLcinfoInqire` | 외상센터 위치정보 조회 | 외상센터 GPS |
| 8 | `getStrmBassInfoInqire` | 외상센터 기본정보 조회 | - |
| 9 | `getEmrrmSrsillDissMsgInqire` | 응급실 및 중증질환 메시지 조회 | - |

---

## 1. 응급실 실시간 가용병상 조회

**URL:** `.../getEmrrmRltmUsefulSckbdInfoInqire`

### 요청 파라미터

| 파라미터 | 설명 | 필수 | 예시 |
|---------|------|------|------|
| `serviceKey` | API 인증키 | ✅ | `EMER_API_KEY` |
| `STAGE1` | 시도 | ✅ | `서울특별시` |
| `STAGE2` | 시군구 | ✅ | `강남구` |
| `pageNo` | 페이지 번호 | - | `1` |
| `numOfRows` | 목록 건수 | - | `10` |

### 주요 응답 필드

| 필드 | 설명 | 비고 |
|------|------|------|
| `hpid` | 기관 ID | 다른 API와 연결 키 |
| `dutyName` | 기관명 | |
| `dutyTel3` | 응급실 전화 | |
| `hvidate` | 정보 입력 일시 | 최신 여부 확인용 |
| **병상 수** | | |
| `hvec` | 응급실 일반 병상 | 숫자 |
| `hvoc` | 수술실 | 숫자 |
| `hvicc` | 중환자실 일반 | 숫자 |
| `hvcc` | 중환자실 신경과 | 숫자 |
| `hvccc` | 중환자실 흉부외과 | 숫자 |
| `hvncc` | 중환자실 신생아 | 숫자 |
| `hv2` | 중환자실 내과 | 숫자 |
| `hv3` | 중환자실 외과 | 숫자 |
| `hv6` | 중환자실 신경외과 | 숫자 |
| `hv34` | 중환자실 심장내과 | 숫자 |
| `hv9` | 중환자실 외상 | 숫자 |
| `hv31` | [응급전용] 중환자실 | 숫자 |
| `hv36` | [응급전용] 입원실 | 숫자 |
| `hvgc` | 입원실 일반 | 숫자 |
| **장비 가용 여부** (Y/N) | | |
| `hvctayn` | CT | Y/N |
| `hvmriayn` | MRI | Y/N |
| `hvangioayn` | 혈관촬영기 | Y/N |
| `hvventiayn` | 인공호흡기 | Y/N |
| `hvecmoayn` | ECMO | Y/N |
| `hvcrrtayn` | CRRT | Y/N |
| `hvoxyayn` | 고압산소치료기 | Y/N |
| `hvhypoayn` | 중심체온조절유도기 | Y/N |
| `hvamyn` | 구급차 가용 여부 | Y/N |
| **기준 병상 수** (HVS*) | | |
| `HVS01` | 일반_기준 | |
| `HVS05` | [응급전용] 중환자실_기준 | |
| `HVS27` | CT_기준 | |
| `HVS28` | MRI_기준 | |

### 예시 요청
```
GET .../getEmrrmRltmUsefulSckbdInfoInqire
  ?serviceKey=<KEY>&STAGE1=서울특별시&STAGE2=강남구&pageNo=1&numOfRows=10
```

---

## 2. 중증질환자 수용가능정보 조회

**URL:** `.../getSrsillDissAceptncPosblInfoInqire`

### 요청 파라미터

| 파라미터 | 설명 | 필수 | 예시 |
|---------|------|------|------|
| `serviceKey` | API 인증키 | ✅ | |
| `STAGE1` | 시도 | ✅ | `서울특별시` |
| `STAGE2` | 시군구 | ✅ | `강남구` |
| `SM_TYPE` | 중증질환 유형 코드 | - | `1` (Y인 병원만 반환) |
| `pageNo` | 페이지 번호 | - | `1` |
| `numOfRows` | 목록 건수 | - | `10` |

### 주요 응답 필드 (MKioskTy*)

| 필드 | 설명 | 증상 매핑 |
|------|------|----------|
| `dutyName` | 기관명 | |
| `hpid` | 기관 ID | |
| `MKioskTy1` | 뇌출혈 수술 | 의식저하, 두통 |
| `MKioskTy2` | 뇌경색 재관류 | 의식저하, 편측마비 |
| `MKioskTy3` | 심근경색 재관류 (수술) | 흉통, 심정지 |
| `MKioskTy4` | 심근경색 재관류 (시술) | 흉통 |
| `MKioskTy5` | 복부손상 수술 | 복부외상 |
| `MKioskTy6` | 사지접합 수술 | 절단 외상 |
| `MKioskTy7` | 응급내시경 | 토혈, 혈변 |
| `MKioskTy8` | 응급투석 | 신부전 |
| `MKioskTy9` | 조산산모 | 분만 |
| `MKioskTy10` | 정신질환자 | 자해, 정신과 |
| `MKioskTy11` | 중증화상 (1차) | 화상 |
| `MKioskTy12` | 중증화상 (2차) | 화상 |
| `MKioskTy15` | 소아 응급 | 소아 |
| `MKioskTy19` | 중증외상 | 교통사고, 추락 |
| `MKioskTy22` | 투석 (HD) | |
| `MKioskTy23` | CRRT | |
| `MKioskTy25` | HIV 감염 응급 | |
| `MKioskTy28` | 응급게이트키퍼 (정신과) | |

> 응답값: `Y` (수용 가능) / `N` (불가) / `정보미제공`  
> `*Msg` 필드: 수용 불가 시 사유 또는 대기시간 메시지

### 예시 요청
```
GET .../getSrsillDissAceptncPosblInfoInqire
  ?serviceKey=<KEY>&STAGE1=서울특별시&STAGE2=강남구&pageNo=1&numOfRows=20
```

---

## 3. 응급의료기관 목록 조회

**URL:** `.../getEgytListInfoInqire`

### 요청 파라미터

| 파라미터 | 설명 | 필수 | 예시 |
|---------|------|------|------|
| `serviceKey` | API 인증키 | ✅ | |
| `STAGE1` | 시도 | - | `서울특별시` |
| `STAGE2` | 시군구 | - | `강남구` |
| `pageNo` | 페이지 번호 | - | `1` |
| `numOfRows` | 목록 건수 | - | `100` |

> ⚠️ `STAGE1` 필터가 서울만 반환하지 않을 수 있음. `wgs84Lat/wgs84Lon`으로 직접 거리 필터 권장.

### 주요 응답 필드

| 필드 | 설명 |
|------|------|
| `hpid` | 기관 ID (기관 간 연결 키) |
| `dutyName` | 기관명 |
| `dutyAddr` | 주소 |
| `dutyTel1` | 대표 전화 |
| `dutyTel3` | 응급실 전화 |
| `dutyEmcls` | 응급의료기관 분류 코드 |
| `dutyEmclsName` | 응급의료기관 분류명 |
| `wgs84Lat` | 위도 (WGS84) |
| `wgs84Lon` | 경도 (WGS84) |

### 기관 분류 코드 (dutyEmcls)

| 코드 | 분류명 |
|------|--------|
| `G001` | 권역응급의료센터 |
| `G002` | 전문응급의료센터 |
| `G003` | 지역응급의료센터 |
| `G004` | 지역응급의료기관 |
| `G009` | 응급실운영신고기관 |

---

## 4. 응급의료기관 위치정보 조회

**URL:** `.../getEgytLcinfoInqire`

### 요청 파라미터

| 파라미터 | 설명 | 필수 |
|---------|------|------|
| `serviceKey` | API 인증키 | ✅ |
| `STAGE1` | 시도 | - |
| `STAGE2` | 시군구 | - |
| `pageNo` / `numOfRows` | 페이지 | - |

### 주요 응답 필드

| 필드 | 설명 |
|------|------|
| `hpid` | 기관 ID |
| `dutyName` | 기관명 |
| `dutyAddr` | 주소 |
| `wgs84Lat` | 위도 |
| `wgs84Lon` | 경도 |

---

## 5. 응급의료기관 기본정보 조회

**URL:** `.../getEgytBassInfoInqire`

### 요청 파라미터

| 파라미터 | 설명 | 필수 |
|---------|------|------|
| `serviceKey` | API 인증키 | ✅ |
| `HPID` | 기관 ID | ✅ |

> `hpid`를 알고 있을 때 상세 정보 조회

### 주요 응답 필드

| 필드 | 설명 |
|------|------|
| `hpid` | 기관 ID |
| `dutyName` | 기관명 |
| `dutyAddr` | 주소 |
| `dutyTel1` | 대표 전화 |
| `dutyTel3` | 응급실 전화 |
| `dutyTime*S` / `dutyTime*C` | 진료 시작/종료 시간 |
| `dutyInf` | 기관 소개 |
| `wgs84Lat` / `wgs84Lon` | GPS 좌표 |

---

## 6–7. 외상센터 목록 / 위치정보 조회

**URL:** `.../getStrmListInfoInqire` / `.../getStrmLcinfoInqire`

- 파라미터 및 응답 구조는 응급의료기관 목록/위치 조회(#3, #4)와 동일
- 중증외상 (`MKioskTy19`) 수용 가능 병원 추천 시 활용

---

## 증상 → API 필드 매핑 (추천 서비스용)

| 증상 (`PTN_SYM_SE_NM`) | 우선 확인 필드 |
|------------------------|--------------|
| 심정지, 흉통 | `MKioskTy3`, `MKioskTy4`, `hvicc`, `hvcrrtayn`, `hvecmoayn` |
| 의식저하, 두통, 편측마비 | `MKioskTy1`, `MKioskTy2`, `hvcc`, `hvctayn`, `hvmriayn` |
| 중증외상, 교통사고, 추락 | `MKioskTy19`, `hv9`, 외상센터 API |
| 화상 | `MKioskTy11`, `MKioskTy12` |
| 호흡곤란 | `hvventiayn`, `hvicc`, `hvec` |
| 소아 관련 | `MKioskTy15`, `hvncc` |
| 일반/기타 | `hvec` (응급실 일반 병상) |

---

## Python 코드 템플릿

```python
import requests, os
from xml.etree import ElementTree as ET
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("EMER_API_KEY")
BASE = "http://apis.data.go.kr/B552657/ErmctInfoInqireService"

def call_api(operation, params):
    params["serviceKey"] = KEY
    r = requests.get(f"{BASE}/{operation}", params=params, timeout=10)
    root = ET.fromstring(r.text)
    return [
        {child.tag: child.text for child in item}
        for item in root.findall(".//item")
    ]

# 실시간 병상 조회
beds = call_api("getEmrrmRltmUsefulSckbdInfoInqire", {
    "STAGE1": "서울특별시", "STAGE2": "강남구", "numOfRows": 30
})

# 중증질환 수용 조회
severe = call_api("getSrsillDissAceptncPosblInfoInqire", {
    "STAGE1": "서울특별시", "numOfRows": 100
})

# 병원 목록 (GPS 포함)
hospitals = call_api("getEgytListInfoInqire", {
    "STAGE1": "서울특별시", "numOfRows": 100
})
```
