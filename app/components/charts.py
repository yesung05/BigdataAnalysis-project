"""차트 헬퍼 유틸."""
import streamlit as st


def metric_row(items: list):
    """items: [{label, value, delta?, help?}, ...] → st.columns + st.metric."""
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        col.metric(
            label=item["label"],
            value=item["value"],
            delta=item.get("delta"),
            help=item.get("help"),
        )


def section_header(title: str, subtitle: str = ""):
    st.subheader(title)
    if subtitle:
        st.caption(subtitle)
