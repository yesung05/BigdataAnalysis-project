"""지도 임베드 헬퍼."""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


def embed_html_map(html_path: Path, height: int = 550):
    """HTML 파일을 읽어 st.components.v1.html()로 임베드."""
    if not html_path.exists():
        st.warning(f"지도 파일이 없습니다: {html_path.name}")
        return
    html_content = html_path.read_text(encoding="utf-8")
    components.html(html_content, height=height, scrolling=False)
