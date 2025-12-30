import streamlit as st

def inject_custom_css():
    st.markdown("""
    <style>
        .stButton>button {
            border-radius: 8px;
        }
        .provider-card {
            border: 1px solid #e0e0e0;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            background-color: #ffffff;
        }
        .model-row {
            padding: 10px;
            border-bottom: 1px solid #f0f0f0;
        }
        .status-badge-success {
            background-color: #d4edda;
            color: #155724;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.8em;
            border: 1px solid #c3e6cb;
        }
        .status-badge-fail {
            background-color: #f8d7da;
            color: #721c24;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.8em;
            border: 1px solid #f5c6cb;
        }
        /* Hide default Streamlit anchor links to make it cleaner */
        .css-15zrgzn {display: none}
    </style>
    """, unsafe_allow_html=True)

def get_provider_logo_url(name: str) -> str:
    """Returns a logo URL for common providers."""
    name_lower = name.lower()
    if "deepseek" in name_lower:
        return "https://chat.deepseek.com/favicon.ico" # Use official or placeholder
    elif "moonshot" in name_lower or "kimi" in name_lower:
        return "https://www.moonshot.cn/favicon.ico" 
    elif "openai" in name_lower or "gpt" in name_lower:
        return "https://openai.com/favicon.ico"
    elif "claude" in name_lower or "anthropic" in name_lower:
        return "https://anthropic.com/favicon.ico"
    else:
        return "https://cdn-icons-png.flaticon.com/512/2585/2585186.png" # Generic Robot

def get_model_tags(model_id: str):
    """Simple heuristic to tag models."""
    tags = []
    mid = model_id.lower()
    
    # Context Logic
    if "128k" in mid or "-128" in mid:
        tags.append("128k Context")
    elif "32k" in mid:
        tags.append("32k Context")
    
    # Cap Logic
    if "vision" in mid or "4v" in mid or "claude-3" in mid:
        tags.append("👀 Vision")
    
    if "preview" in mid:
        tags.append("🧪 Preview")
        
    if "gpt-4" in mid or "claude-3-opus" in mid:
        tags.append("🔥 SOTA")
        
    if "turbo" in mid or "flash" in mid:
        tags.append("⚡ Fast")
        
    return tags

def render_status_badge(status: str):
    if status == "success":
        return '<span class="status-badge-success">● API Connected</span>'
    elif status == "fail":
        return '<span class="status-badge-fail">● Connection Failed</span>'
    else:
        return '<span style="color:grey">● Unknown</span>'
