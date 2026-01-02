import streamlit as st
import socket
import subprocess
import sys
import os
import time

def is_port_in_use(port: int) -> bool:
    """Check if a port is in use on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

@st.cache_resource
def ensure_backend_running():
    """
    Ensure the backend server (chat_server.py) is running on port 8000.
    If not, start it automatically.
    This function is cached by Streamlit resource caching mechanism,
    so it generally runs once per session unless the cache is cleared.
    """
    if not is_port_in_use(8000):
        msg_container = st.empty()
        msg_container.warning("检测到后台服务未运行，正在自动启动... 🚀")
        
        # Determine the root directory of the project
        # core/utils/server_manager.py -> core/utils -> core -> project_root
        current_file_path = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
        
        # Command to start uvicorn
        # Using run_backend.py wrapper to capture crash logs
        cmd = [sys.executable, "run_backend.py"]
        
        try:
            # Run in background
            # Allow stdout/stderr to inherit to see logs in the main console
            subprocess.Popen(
                cmd,
                cwd=project_root,
                # stdout=subprocess.DEVNULL, # Removed to allow logging
                # stderr=subprocess.DEVNULL  # Removed to allow logging
            )
            
            # Wait for up to 10 seconds for the server to start
            for _ in range(10):
                if is_port_in_use(8000):
                    msg_container.success("后台服务已成功启动！ ✅")
                    time.sleep(2)
                    msg_container.empty()
                    return True
                time.sleep(1)
            
            msg_container.error("后台服务启动超时。请尝试手动运行: `uvicorn chat_server:app --port 8000`")
            return False
            
        except Exception as e:
            msg_container.error(f"无法自动启动后台服务: {e}")
            return False
    return True
