"""Playwright로 Streamlit 앱 전체 페이지 스크린샷 캡처."""
import asyncio
import sys
import io
from pathlib import Path
from playwright.async_api import async_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://localhost:8502"
OUT  = Path(__file__).resolve().parent.parent / "docs" / "imgs"
OUT.mkdir(parents=True, exist_ok=True)

# (사이드바 링크 텍스트, 저장 파일명)
PAGES = [
    (None,          "00_home.png"),
    ("데이터 현황",   "01_data_status.png"),
    ("출동 트렌드",   "02_yearly_trend.png"),
    ("뺑뺑이 분석",   "03_transfer_rate.png"),
    ("응급실 상관",   "04_er_correlation.png"),
    ("소방서 현황",   "05_fire_station.png"),
    ("증상 분석",    "06_symptom.png"),
    ("날씨 상관",    "07_weather_scatter.png"),
    ("신고유형 추세", "08_report_type.png"),
    ("추천 서비스",  "09_recommend_cards.png"),
    ("AI 챗봇",     "10_ai_chatbot.png"),
]

async def wait_for_content(page, timeout_ms=45000):
    """Plotly 차트가 로드될 때까지 대기. 없으면 timeout 후 진행."""
    try:
        await page.locator(".js-plotly-plot").first.wait_for(
            state="visible", timeout=timeout_ms
        )
        await asyncio.sleep(2)
    except Exception:
        await asyncio.sleep(3)

async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page    = await browser.new_page(viewport={"width": 1400, "height": 900})

        # Home 로드
        print(f"  -> {BASE}  (00_home.png)")
        await page.goto(BASE, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        await page.screenshot(path=str(OUT / "00_home.png"), full_page=False)
        print("    saved 00_home.png")

        for sidebar_text, fname in PAGES[1:]:
            print(f"  -> sidebar: {sidebar_text}  ({fname})")
            try:
                link = page.get_by_role("link", name=sidebar_text).first
                await link.wait_for(timeout=8000)
                await link.click()
                await wait_for_content(page)
                await page.evaluate("window.scrollTo(0, 0)")
                await page.screenshot(path=str(OUT / fname), full_page=False)
                print(f"    saved {fname}")
            except Exception as e:
                print(f"    FAIL {fname}: {e}")
                try:
                    await page.screenshot(path=str(OUT / fname), full_page=False)
                    print(f"    saved (fallback) {fname}")
                except Exception:
                    pass

        await browser.close()

asyncio.run(capture())
print("\nDone.")
