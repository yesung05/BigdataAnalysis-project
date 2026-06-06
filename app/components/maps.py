"""지도 임베드 헬퍼."""
from pathlib import Path

import streamlit as st


def embed_html_map(html_path: Path, height: int = 550):
    """HTML 파일을 읽어 st.iframe()으로 임베드."""
    if not html_path.exists():
        st.warning(f"지도 파일이 없습니다: {html_path.name}")
        return
    html_content = html_path.read_text(encoding="utf-8")
    st.iframe(html_content, height=height, scrolling=False)
