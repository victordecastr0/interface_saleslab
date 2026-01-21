from pathlib import Path
import streamlit as st


def inject_badges_css() -> None:
    """Inject badges CSS into Streamlit."""
    
    css_path = Path(__file__).resolve().parent / "badges.css"
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)