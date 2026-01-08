import streamlit as st

st.set_page_config(page_title="Harvester Hub", page_icon="🌀")
st.title("🌀 Harvester Hub")

st.markdown("### Available Services")

if st.button("Chaos Harvester"):
    st.markdown("[➡️ Open Chaos Harvester](http://localhost:8501)")

if st.button("Web Harvester"):
    st.markdown("[➡️ Open Web Harvester](http://localhost:8502)")

if st.button("Audio Harvester"):
    st.markdown("[➡️ Open Audio Harvester](http://localhost:8503)")
