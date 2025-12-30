import streamlit as st

def render_chat_box():
    """
    Renders the chat history from session state.
    """
    chat_container = st.container()
    
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    with chat_container:
        for msg in st.session_state["chat_history"]:
            if msg["type"] == "system":
                st.info(f"📢 {msg['content']}")
            elif msg["type"] == "stage_direction":
                st.warning(f"{msg['content']}")
            elif msg["type"] == "dialogue":
                with st.chat_message(msg["actor"]):
                    st.write(f"**{msg['actor']}**: {msg['content']}")
            elif msg["type"] == "thinking":
                with st.chat_message(msg["actor"]):
                    st.caption("💭 Thinking...")
