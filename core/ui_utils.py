import streamlit as st

def inject_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap');
        
        * { font-family: 'Outfit', sans-serif; }

        /* Glassmorphism Effect */
        .stApp {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #1a1a2e 100%);
            color: #ffffff;
        }

        .glass-card {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .glass-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.15);
        }

        .stButton>button {
            border-radius: 14px;
            background: linear-gradient(135deg, #e94560 0%, #c62828 100%);
            color: white;
            border: none;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stButton>button:hover {
            transform: scale(1.02);
            box-shadow: 0 8px 20px rgba(233, 69, 96, 0.5);
        }

        .status-badge-success {
            background: rgba(40, 167, 69, 0.15);
            color: #4cd137;
            padding: 6px 12px;
            border-radius: 24px;
            font-size: 0.8em;
            border: 1px solid rgba(76, 209, 55, 0.3);
            font-weight: 600;
            box-shadow: 0 0 10px rgba(76, 209, 55, 0.2);
        }

        /* Message Bubble Animations */
        @keyframes fadeInSlide {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .chat-msg {
            animation: fadeInSlide 0.5s ease-out forwards;
        }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background: rgba(15, 52, 96, 0.98) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
        }

        /* Hide default Streamlit anchor links */
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
