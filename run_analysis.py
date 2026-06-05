"""소방청 구급 데이터 분석 통합 실행 스크립트.

사용법:
  python run_analysis.py              # 전체 분석 실행
  python run_analysis.py --bbang      # 뺑뺑이 심층분석만
  python run_analysis.py --station    # 소방서 출동 부하 지도만
  python run_analysis.py --symptom    # 증상 분석만
  python run_analysis.py --weather    # 날씨×출동 상관만
  python run_analysis.py --timeseries # 시계열 트렌드만

출력 디렉토리: outputs/figures/
"""
import argparse
import time
from pathlib import Path

# 출력 경로 사전 생성
from src.config import FIGURES_DIR  # noqa: 경로 생성 side-effect


def _run_bbang():
    from src.analysis.bbang import run
    run()


def _run_station():
    from src.analysis.station_load import run
    run()


def _run_symptom():
    from src.analysis.symptom import run
    run()


def _run_weather():
    from src.analysis.weather import run
    run()


def _run_timeseries():
    from src.analysis.time_series import run
    run()


ANALYSES = {
    "bbang":      ("뺑뺑이 심층분석",       _run_bbang),
    "station":    ("소방서 출동 부하 지도",   _run_station),
    "symptom":    ("증상 분석",             _run_symptom),
    "weather":    ("날씨×출동 상관",         _run_weather),
    "timeseries": ("시계열 트렌드",          _run_timeseries),
}


def main():
    parser = argparse.ArgumentParser(description="소방청 구급 데이터 분석")
    for key in ANALYSES:
        parser.add_argument(f"--{key}", action="store_true", help=ANALYSES[key][0])
    args = parser.parse_args()

    selected = {k for k in ANALYSES if getattr(args, k)}
    if not selected:
        selected = set(ANALYSES.keys())

    print("=" * 60)
    print("  소방청 구급 데이터 분석 시작")
    print(f"  출력 경로: {FIGURES_DIR}")
    print("=" * 60)

    total_start = time.time()
    results = {}

    for key in ANALYSES:
        if key not in selected:
            continue
        label, func = ANALYSES[key]
        print(f"\n{'─'*60}")
        print(f"  [{label}]")
        t0 = time.time()
        try:
            func()
            elapsed = time.time() - t0
            results[label] = f"완료 ({elapsed:.1f}s)"
        except Exception as e:
            elapsed = time.time() - t0
            results[label] = f"오류: {e}"
            print(f"  [ERROR] {e}")

    total_elapsed = time.time() - total_start

    print("\n" + "=" * 60)
    print("  분석 결과 요약")
    print("=" * 60)
    for label, status in results.items():
        print(f"  {label:20s}: {status}")
    print(f"\n  총 소요 시간: {total_elapsed:.1f}초")
    print(f"  저장 위치:   {FIGURES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
