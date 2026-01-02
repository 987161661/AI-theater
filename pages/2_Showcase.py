import streamlit as st
import asyncio
import websockets
import json

st.set_page_config(page_title="AI Theater Showcase", page_icon="🎭", layout="wide", initial_sidebar_state="collapsed")

from components.chat_box import render_chat_box

# Custom CSS to hide controls
st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;}
    .reportview-container {
        background: black;
    }
    h1 {
        text-align: center;
        font-family: 'Courier New', Courier, monospace;
        color: #f0f0f0;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎭 AI Theater - LIVE")

WS_URL = "ws://localhost:8000/ws"

# Initialize history if empty (though shared session might populate it)
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# Main Display
st.caption("沉浸式观影模式 | Connection established")
st.divider()

render_chat_box()

# Auto-connect loop
# We reuse the logic from Theater page but strictly for view
empty_slot = st.empty()

async def listen_ws():
    try:
        async with websockets.connect(WS_URL) as websocket:
            while True:
                msg = await websocket.recv()
                data = json.loads(msg)
                st.session_state["chat_history"].append(data)
                st.rerun()
    except Exception as e:
        empty_slot.error(f"Connection lost: {e}")

# Run
asyncio.run(listen_ws())
