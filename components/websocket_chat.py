"""
WebSocket 实时群聊 Streamlit 组件 - 精确微信 UI 版本

复用传统模式的微信精确复刻界面，添加 WebSocket 实时通信功能。
"""

import streamlit as st
import streamlit.components.v1 as components
import json


def render_websocket_chat(room_id: str = "consciousness_lab", ws_url: str = "ws://localhost:8001", member_count: int = 3, model_configs: list = None, scenario_config: dict = None, is_stage_view: bool = False):
    """
    渲染 WebSocket 实时群聊界面 - 使用与传统模式相同的微信精确 UI
    
    Args:
        room_id: 群聊房间ID
        ws_url: WebSocket 服务器地址
        member_count: 群成员数量
        model_configs: 模型配置列表 [{"model_name":..., "api_key":..., "base_url":..., "provider_name":...}]
        scenario_config: 剧本配置 {"enabled": bool, "events": list}
    """
    
    full_ws_url = f"{ws_url}/ws/{room_id}"
    models_json = json.dumps(model_configs or [])
    scenario_json = json.dumps(scenario_config or {})
    
    # 完整的微信精确复刻 HTML + CSS + WebSocket JS
    html_content = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; }}

.wechat-window {{
    display: flex;
    flex-direction: column;
    height: 650px;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 8px 40px rgba(0,0,0,0.15);
    border: 1px solid #ccc;
    position: relative; /* For modal positioning */
}}

/* 成员面板样式 */
.wc-member-panel {{
    width: 0;
    background: #f5f5f5;
    border-left: 0 solid #ececec;
    transition: width 0.3s ease;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
}}
.wc-member-panel.open {{
    width: 250px; /* Wider for settings */
    border-left: 1px solid #ececec;
}}
.wc-member-header {{
    padding: 15px;
    font-size: 13px;
    font-weight: 500;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.wc-member-list {{
    flex: 1;
    overflow-y: auto;
    padding: 10px;
}}
.wc-member-item {{
    display: flex;
    flex-direction: column; /* Changed for settings */
    padding: 8px;
    border-radius: 4px;
    cursor: default;
    margin-bottom: 5px;
    background: #fff;
    border: 1px solid #eee;
}}
.wc-member-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    width: 100%;
}}
.wc-member-item:hover {{ background: #fafafa; }}
.wc-member-avatar {{
    width: 32px; height: 32px; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-size: 14px; position: relative;
    flex-shrink: 0;
}}
.wc-member-name {{ 
    font-size: 12px; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;
}}
.wc-member-settings {{
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid #f0f0f0;
    display: none;
    font-size: 11px;
}}
.wc-member-item.expanded .wc-member-settings {{ display: block; }}
.setting-row {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }}
.setting-label {{ color: #666; }}
.setting-input {{ 
    width: 100%; border: 1px solid #ddd; padding: 4px; border-radius: 3px; font-size: 11px; margin-top: 2px;
}}
/* Switch Toggle */
.switch {{ position: relative; display: inline-block; width: 30px; height: 16px; }}
.switch input {{ opacity: 0; width: 0; height: 0; }}
.slider {{ position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 16px; }}
.slider:before {{ position: absolute; content: ""; height: 12px; width: 12px; left: 2px; bottom: 2px; background-color: white; transition: .4s; border-radius: 50%; }}
input:checked + .slider {{ background-color: #07c160; }}
input:checked + .slider:before {{ transform: translateX(14px); }}

.thinking-ring {{
    position: absolute;
    top: -2px; left: -2px; right: -2px; bottom: -2px;
    border: 2px solid #07c160;
    border-radius: 6px;
    opacity: 0;
    animation: rotate 2s linear infinite;
}}
.is-thinking .thinking-ring {{ opacity: 1; }}
@keyframes rotate {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}

/* 思考过程模态框 */
.thought-modal {{
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 80%; height: 70%;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 10px 50px rgba(0,0,0,0.3);
    z-index: 100;
    display: none;
    flex-direction: column;
}}
.thought-modal-header {{
    padding: 12px 16px;
    background: #f5f5f5;
    border-bottom: 1px solid #ddd;
    display: flex; justify-content: space-between; align-items: center;
    border-radius: 8px 8px 0 0;
}}
.thought-modal-body {{
    flex: 1;
    padding: 16px;
    overflow-y: auto;
    font-family: 'Courier New', Courier, monospace;
    font-size: 12px;
    white-space: pre-wrap;
    background: #fafafa;
    line-height: 1.5;
}}
.close-modal {{ cursor: pointer; font-size: 18px; color: #888; }}

.wc-title-bar {{
    height: 28px;
    background: #2e2e2e;
    display: flex;
    align-items: center;
    padding: 0 12px;
    flex-shrink: 0;
}}
.traffic-lights {{ display: flex; gap: 8px; }}
.traffic-light {{ width: 12px; height: 12px; border-radius: 50%; }}
.tl-close {{ background: #ff5f57; }}
.tl-minimize {{ background: #febc2e; }}
.tl-maximize {{ background: #28c840; }}
.title-text {{ flex: 1; text-align: center; color: #aaa; font-size: 12px; }}
.status-dot {{
    width: 8px; height: 8px; border-radius: 50%;
    background: #888; margin-right: 8px;
}}
.status-dot.connected {{ background: #28c840; }}
.status-dot.running {{ background: #28c840; animation: pulse 1s infinite; }}
@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}

.wc-body {{
    display: flex;
    flex: 1;
    overflow: hidden;
}}

.wc-dock {{
    width: 54px;
    background: #2e2e2e;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 16px 0 10px 0;
    flex-shrink: 0;
}}
.wc-dock-avatar {{
    width: 34px; height: 34px;
    border-radius: 4px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-size: 16px;
    margin-bottom: 20px;
}}
.wc-dock-nav {{ display: flex; flex-direction: column; align-items: center; gap: 2px; flex: 1; }}
.wc-dock-btn {{
    width: 38px; height: 38px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 4px; cursor: pointer;
    font-size: 18px; color: #8a8a8a;
}}
.wc-dock-btn:hover {{ background: rgba(255,255,255,0.08); color: #fff; }}
.wc-dock-btn.active {{ color: #07c160; }}
.wc-dock-bottom {{ margin-top: auto; display: flex; flex-direction: column; align-items: center; gap: 2px; }}

.wc-sidebar {{
    width: 250px;
    background: #e9e9e9;
    display: flex;
    flex-direction: column;
    border-right: 1px solid #ececec;
    flex-shrink: 0;
}}
.wc-search-box {{
    padding: 12px 8px 8px 8px;
    display: flex; gap: 6px; align-items: center;
}}
.wc-search-input {{
    flex: 1; height: 26px;
    background: #d6d6d6; border-radius: 4px;
    display: flex; align-items: center;
    padding: 0 8px; gap: 6px;
    font-size: 12px; color: #888;
}}
.wc-add-btn {{
    width: 26px; height: 26px;
    background: #d6d6d6; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; font-size: 16px; color: #666;
}}
.wc-chat-list {{ flex: 1; overflow-y: auto; }}
.wc-chat-item {{
    display: flex; align-items: center;
    padding: 10px 8px; gap: 10px;
    cursor: pointer;
}}
.wc-chat-item:hover {{ background: #dedede; }}
.wc-chat-item.active {{ background: #c9c9c9; }}
.wc-chat-avatar {{
    width: 38px; height: 38px; border-radius: 4px;
    background: #7b7b7b;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; color: #fff; flex-shrink: 0;
}}
.wc-chat-info {{ flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }}
.wc-chat-row {{ display: flex; justify-content: space-between; align-items: center; }}
.wc-chat-name {{ font-size: 13px; color: #191919; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.wc-chat-time {{ font-size: 10px; color: #b2b2b2; flex-shrink: 0; }}
.wc-chat-preview {{ font-size: 11px; color: #888; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

/* 控制按钮区 - 优化：移除冗余按钮 */
.wc-controls {{
    padding: 8px;
    display: flex;
    justify-content: center;
    gap: 6px;
    border-top: 1px solid #ececec;
}}
.wc-ctrl-btn {{
    flex: 1;
    padding: 6px 10px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 11px;
    text-align: center;
}}
.btn-clear {{ background: #d6d6d6; color: #666; }}
.btn-clear:hover {{ background: #cccccc; }}
.btn-start {{ background: #07c160; color: #fff; }}
.btn-start:hover {{ background: #06ad56; }}
.btn-stop {{ background: #ff5f57; color: #fff; display: none; }}
.btn-stop:hover {{ background: #e04f48; }}

.wc-main {{
    flex: 1; display: flex; flex-direction: column;
    background: #f5f5f5; min-width: 0;
}}
/* 剧本时间轴样式 */
    .wc-scenario-timeline {{
        background: #f9f9f9;
        border-bottom: 1px solid #e0e0e0;
        padding: 8px 0;
        display: flex;
        gap: 12px;
        overflow-x: auto;
        white-space: nowrap;
        scrollbar-width: thin;
        flex-shrink: 0;
        padding-left: 12px; padding-right: 12px;
    }}
    .wc-scenario-timeline::-webkit-scrollbar {{ height: 4px; }}
    .wc-scenario-timeline::-webkit-scrollbar-thumb {{ background: #ccc; border-radius: 2px; }}

    .wc-scenario-box {{
        background: #fff;
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 6px 10px;
        min-width: 100px;
        max-width: 140px;
        display: flex;
        flex-direction: column;
        cursor: pointer;
        transition: all 0.2s;
        flex-shrink: 0;
        position: relative;
    }}
    .wc-scenario-box:hover {{ border-color: #bbb; }}
    .wc-scenario-box.active {{
        border-color: #07c160;
        background: #e7f8ed;
        box-shadow: 0 2px 6px rgba(7, 193, 96, 0.15);
        transform: translateY(-1px);
    }}
    .wc-scenario-box.past {{
        background: #f5f5f5;
        color: #999;
        border-color: #eee;
        opacity: 0.8;
    }}
    
    .wc-scenario-time {{
        font-size: 12px;
        font-weight: 600;
        color: #333;
        margin-bottom: 2px;
    }}
    .wc-scenario-box.past .wc-scenario-time {{ color: #888; }}
    
    .wc-scenario-desc {{
        font-size: 10px;
        color: #666;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .wc-scenario-box.past .wc-scenario-desc {{ color: #aaa; }}

    /* 剧本详情面板（可折叠） */
    .wc-scenario-detail {{
        background: #fff;
        border-bottom: 1px solid #e0e0e0;
        padding: 8px 12px;
        font-size: 12px;
        color: #555;
        display: none;
        position: relative;
        line-height: 1.5;
        flex-shrink: 0;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    }}
    .wc-scenario-detail.show {{ display: block; animation: slideDown 0.2s ease-out; }}
    @keyframes slideDown {{ from {{ opacity: 0; transform: translateY(-5px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    
    .wc-detail-header {{
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 4px;
        font-weight: 600; color: #333;
    }}
    .wc-detail-close {{
        cursor: pointer; padding: 2px 6px; border-radius: 4px;
        color: #999; font-size: 16px; line-height: 1;
    }}
    .wc-detail-close:hover {{ background: #f0f0f0; color: #666; }}

    .wc-chat-header {{
        height: 50px;
        background: #f5f5f5;
        border-bottom: 1px solid #ececec;
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 16px; flex-shrink: 0;
}}
.wc-chat-title-container {{ flex: 1; display: flex; align-items: center; gap: 8px; }}
.wc-chat-title {{ font-size: 14px; font-weight: 500; color: #191919; cursor: text; border-bottom: 1px dashed transparent; }}
.wc-chat-title:hover {{ border-bottom: 1px dashed #999; }}
.wc-chat-title:focus {{ outline: none; border-bottom: 1px solid #07c160; }}
.member-count {{ font-weight: 400; color: #888; font-size: 12px; }}

.typing-indicator {{ font-size: 11px; color: #1890ff; font-style: italic; }}
.wc-chat-actions {{ display: flex; gap: 12px; align-items: center; }}
.action-btn {{ font-size: 16px; color: #888; cursor: pointer; }}
.action-btn:hover {{ color: #333; }}

.wc-messages {{
    flex: 1; overflow-y: auto; padding: 12px 16px;
    display: flex; flex-direction: column; gap: 12px;
}}
.wc-time-divider {{ text-align: center; padding: 6px 0; }}
.wc-time-divider span {{ font-size: 10px; color: #b2b2b2; background: #f5f5f5; padding: 0 10px; }}
.wc-system-msg {{ text-align: center; color: #1890ff; font-size: 11px; padding: 4px; }}

.wc-msg-row {{ display: flex; gap: 8px; max-width: 75%; }}
.wc-msg-row.self {{ flex-direction: row-reverse; align-self: flex-end; }}
.wc-msg-row.other {{ align-self: flex-start; }}
.wc-msg-avatar {{
    width: 34px; height: 34px; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; flex-shrink: 0; color: #fff;
    cursor: pointer;
}}
.wc-msg-body {{ display: flex; flex-direction: column; gap: 3px; max-width: calc(100% - 42px); }}
.wc-msg-row.self .wc-msg-body {{ align-items: flex-end; }}
.wc-msg-sender {{ font-size: 11px; color: #888; padding: 0 4px; }}
.manager-badge {{ 
    display: inline-block; background: #ff9800; color: white; border-radius: 2px; 
    font-size: 9px; padding: 0 3px; margin-left: 4px; vertical-align: middle; 
}}
.wc-bubble {{
    position: relative; padding: 8px 10px; border-radius: 4px;
    font-size: 13px; line-height: 1.45; word-wrap: break-word; max-width: 100%;
}}
.wc-msg-row.other .wc-bubble {{ background: #fff; color: #191919; margin-left: 6px; }}
.wc-msg-row.self .wc-bubble {{ background: #95ec69; color: #191919; margin-right: 6px; }}
.wc-bubble::before {{
    content: ""; position: absolute; top: 10px; width: 0; height: 0;
}}
.wc-msg-row.other .wc-bubble::before {{
    left: -5px;
    border-top: 5px solid transparent; border-bottom: 5px solid transparent;
    border-right: 5px solid #fff;
}}
.wc-msg-row.self .wc-bubble::before {{
    right: -5px;
    border-top: 5px solid transparent; border-bottom: 5px solid transparent;
    border-left: 5px solid #95ec69;
}}

.wc-input-area {{
    background: #fff;
    border-top: 1px solid #ececec;
    display: flex; flex-direction: column; flex-shrink: 0;
    height: 180px; /* Increased height as requested */
    position: relative;
}}
.emoji-picker {{
    display: none;
    position: absolute;
    bottom: 100%;
    left: 10px;
    width: 380px;
    height: 250px;
    background: #fff;
    border: 1px solid #d0d0d0;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    border-radius: 4px;
    overflow-y: auto;
    padding: 10px;
    z-index: 1000;
    grid-template-columns: repeat(9, 1fr);
    gap: 5px;
}}
.emoji-item {{
    font-size: 24px;
    cursor: pointer;
    text-align: center;
    padding: 4px;
    border-radius: 4px;
    user-select: none;
}}
.emoji-item:hover {{
    background: #f0f0f0;
}}
.wc-toolbar {{
    height: 32px; padding: 0 12px;
    display: flex; align-items: center; gap: 12px;
    /* border-bottom: 1px solid #f0f0f0;  Optional: remove border for cleaner look */
}}
.wc-tool-btn {{ font-size: 18px; color: #5c5c5c; cursor: pointer; }}
.wc-tool-btn:hover {{ color: #333; }}
.wc-input-box {{
    flex: 1; /* Fill remaining height */
    padding: 8px 20px 20px 20px; /* More padding */
    display: flex; gap: 10px; align-items: flex-end;
}}
.wc-input-textarea {{
    flex: 1;
    border: none;
    resize: none;
    font-size: 14px;
    font-family: inherit;
    height: 100%; /* Fill container */
    outline: none;
}}
.wc-send-btn {{
    padding: 6px 25px;
    background: #e9e9e9; border: 1px solid #d0d0d0; border-radius: 4px;
    font-size: 12px; color: #07c160; cursor: pointer;
    flex-shrink: 0;
}}
.wc-send-btn:hover {{ background: #efefef; }}

.wc-messages::-webkit-scrollbar {{ width: 5px; }}
.wc-messages::-webkit-scrollbar-thumb {{ background: #c0c0c0; border-radius: 3px; }}
.thinking-status {{
    font-size: 10px;
    color: #1890ff; /* Blue highlight */
    cursor: pointer;
    margin-top: 2px;
    display: inline-block;
}}
.thinking-status:hover {{
    text-decoration: underline;
}}

/* Scenario Timeline - Hidden per user request */
.wc-scenario-timeline {{
    display: none !important;
}}
.wc-scenario-detail {{
    display: none !important;
}}
/* 
.wc-scenario-timeline {{
    background: #f5f5f5;
    border-bottom: 1px solid #ececec;
    padding: 8px 16px;
    display: flex;
    gap: 8px;
    overflow-x: auto;
    white-space: nowrap;
    flex-shrink: 0;
}}
...
*/

/* Image & Quote Styles */
.wc-quote {{
    background: #f2f2f2;
    border-left: 3px solid #d0d0d0;
    padding: 4px 8px;
    margin-bottom: 6px;
    font-size: 11px;
    color: #666;
    border-radius: 2px;
    display: flex;
    flex-direction: column;
}}
.wc-msg-image-placeholder {{
    background: #f0f0f0;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    min-width: 120px;
}}
.wc-pat-msg {{
    text-align: center;
    color: #b2b2b2;
    font-size: 11px;
    padding: 4px 0;
}}

</style>
</head>
<body>
<div class="wechat-window">
    <!-- 思考过程浮窗 -->
    <div class="thought-modal" id="thoughtModal">
        <div class="thought-modal-header">
            <span id="thoughtModalTitle">思考过程</span>
            <span class="close-modal" onclick="closeThoughtModal()">×</span>
        </div>
        <div class="thought-modal-body" id="thoughtModalBody"></div>
    </div>

    <div class="wc-title-bar">
        <div class="traffic-lights">
            <div class="traffic-light tl-close"></div>
            <div class="traffic-light tl-minimize"></div>
            <div class="traffic-light tl-maximize"></div>
        </div>
        <div class="title-text">微信</div>
        <div class="status-dot" id="statusDot"></div>
    </div>
    <div class="wc-body">
        <input type="file" id="avatarInput" style="display:none" accept="image/png,image/jpeg,image/gif" onchange="handleAvatarUpload(this)">
        <div class="wc-dock">
            <div class="wc-dock-avatar">👤</div>
            <div class="wc-dock-nav">
                <div class="wc-dock-btn active">💬</div>
                <div class="wc-dock-btn">👥</div>
                <div class="wc-dock-btn">⭐</div>
                <div class="wc-dock-btn">📁</div>
            </div>
            <div class="wc-dock-bottom">
                <div class="wc-dock-btn">📱</div>
                <div class="wc-dock-btn">☰</div>
            </div>
        </div>
        <div class="wc-sidebar">
            <div class="wc-search-box">
                <div class="wc-search-input"><span>🔍</span><span>搜索</span></div>
                <div class="wc-add-btn">+</div>
            </div>
            <div class="wc-chat-list">
                <div class="wc-chat-item active">
                    <div class="wc-chat-avatar">👥</div>
                    <div class="wc-chat-info">
                        <div class="wc-chat-row">
                            <div class="wc-chat-name" id="sidebarGroupName">语言模型内部意识讨论群</div>
                            <div class="wc-chat-time" id="lastTime">--:--</div>
                        </div>
                        <div class="wc-chat-preview" id="lastPreview">连接中...</div>
                    </div>
                </div>
                <div class="wc-chat-item">
                    <div class="wc-chat-avatar" style="background:#5790dc;">📋</div>
                    <div class="wc-chat-info">
                        <div class="wc-chat-row">
                            <div class="wc-chat-name">文件传输助手</div>
                            <div class="wc-chat-time">昨天</div>
                        </div>
                        <div class="wc-chat-preview">[文件]</div>
                    </div>
                </div>
            </div>
            <div class="wc-controls">
                <button class="wc-ctrl-btn btn-stop" style="display: block;" onclick="resetChat()">⏹ 停止模拟</button>
                <button class="wc-ctrl-btn btn-start" id="startBtn" onclick="startSimulation()">▶ 开始模拟</button>
            </div>
        </div>
        <div class="wc-main">
            <!-- Scenario Timeline (Hidden) -->
            <div class="wc-scenario-timeline" id="scenarioTimeline" style="display: none;"></div>
            <div class="wc-scenario-detail" id="scenarioDetail" style="display: none;">
                <div class="wc-detail-header">
                    <span id="detailTitle"></span>
                    <span class="wc-detail-close" onclick="toggleScenarioDetail()" title="折叠/展开">×</span>
                </div>
                <div id="detailContent"></div>
            </div>

            <div class="wc-chat-header">
                <div class="wc-chat-title-container">
                    <div style="display:flex; flex-direction:column;">
                        <div class="wc-chat-title" id="groupName" contenteditable="true" spellcheck="false" onblur="updateGroupName()">语言模型内部意识讨论群</div>
                        <div id="scenarioStatus" style="font-size:10px; color:#1890ff; display:none;"></div>
                    </div>
                    <span class="member-count" id="memberCountHeader">({member_count})</span>
                </div>
                <div class="wc-chat-actions">
                    <span class="typing-indicator" id="typingIndicator"></span>
                    <span class="action-btn" title="群成员" onclick="toggleMemberPanel()">⋯</span>
                </div>
            </div>
            <div class="wc-messages" id="messagesContainer">
                <div class="wc-system-msg">连接服务器中...</div>
            </div>
            <div class="wc-input-area">
                <div class="emoji-picker" id="emojiPicker"></div>
                <div class="wc-toolbar">
                    <span class="wc-tool-btn" title="表情" onclick="toggleEmojiPicker(event)">😊</span>
                    <span class="wc-tool-btn" title="文件">📁</span>
                    <span class="wc-tool-btn" title="截图">✂️</span>
                    <span class="wc-tool-btn" title="聊天记录">📋</span>
                </div>
                <div class="wc-input-box">
                    <textarea class="wc-input-textarea" id="inputBox" placeholder="随时输入消息..." rows="1"></textarea>
                    <button class="wc-send-btn" onclick="sendMessage()">发送(S)</button>
                </div>
            </div>
        </div>
        <!-- Hidden file input for avatar upload -->
        <input type="file" id="avatarInput" accept="image/png,image/jpeg" style="display: none;" onchange="handleAvatarUpload(this)">
        <!-- 右侧成员面板 -->
        <div class="wc-member-panel" id="memberPanel">
            <div class="wc-member-header">群成员 (<span id="panelMemberCount">3</span>)</div>
            <div class="wc-member-list" id="memberList">
                <!-- 成员会在这里动态生成 -->
            </div>
        </div>
    </div>
</div>

<script>
const WS_URL = "{full_ws_url}";
const MODEL_CONFIGS = {models_json};
const SCENARIO_CONFIG = {scenario_json};
const isStageView = {str(is_stage_view).lower()};
let ws = null;
let isConnected = false;
let isRunning = false;
let members = [
    {{ name: "Gaia", isUser: true, isThinking: false, lastThought: "", isManager: true, customPrompt: "" }}
]; 

function connect() {{
    renderMemberList(); 
    ws = new WebSocket(WS_URL);
    
    ws.onopen = function() {{
        isConnected = true;
        updateStatus();
        addSystemMessage("已连接到服务器 ✓");
        
        // 发送模型配置 setup
        if (MODEL_CONFIGS && MODEL_CONFIGS.length > 0) {{
            ws.send(JSON.stringify({{
                type: "setup",
                models: MODEL_CONFIGS,
                scenario: SCENARIO_CONFIG
            }}));
        }}
        
        // 获取初始成员和历史
        ws.send(JSON.stringify({{ type: "get_members" }}));
        ws.send(JSON.stringify({{ type: "get_history" }}));
    }};
    
    ws.onmessage = function(event) {{
        const data = JSON.parse(event.data);
        handleMessage(data);
    }};
    
    ws.onclose = function() {{
        isConnected = false;
        isRunning = false;
        updateStatus();
        addSystemMessage("连接已断开，3秒后重连...");
        setTimeout(connect, 3000);
    }};
    
    ws.onerror = function(error) {{
        console.error("WebSocket error:", error);
    }};
}}

function startSimulation() {{
    if (!isConnected) return;
    // Collect latest settings
    const settings = {{
        group_name: document.getElementById("groupName").innerText,
        member_configs: {{}}
    }};
    
    members.forEach(m => {{
        if (!m.isUser) {{
            settings.member_configs[m.name] = {{
                is_manager: m.isManager,
                custom_prompt: m.customPrompt
            }};
        }}
    }});
    
    ws.send(JSON.stringify({{
        type: "update_settings",
        ...settings
    }}));
    
    ws.send(JSON.stringify({{ type: "start" }}));
    isRunning = true;
    updateStatus();
}}

function stopSimulation() {{
    if (!isConnected) return;
    ws.send(JSON.stringify({{ type: "stop" }}));
    isRunning = false;
    updateStatus();
}}

function updateGroupName() {{
    if (!isConnected) return;
    const name = document.getElementById("groupName").innerText;
    ws.send(JSON.stringify({{
        type: "update_settings",
        group_name: name
    }}));
}}

function updateMemberSettings(name, field, value) {{
    const member = members.find(m => m.name === name);
    if (!member) return;
    
    if (field === 'isManager') {{
        member.isManager = value;
        // Optimistic update: if setting to true, unset others
        if (value === true) {{
            members.forEach(m => {{
                if (m.name !== name) m.isManager = false;
            }});
        }}
    }}
    if (field === 'customPrompt') member.customPrompt = value;
    
    // Send update immediately or wait for start? 
    // Better to send immediately so backend has it.
    ws.send(JSON.stringify({{
        type: "update_settings",
        member_configs: {{
            [name]: {{
                is_manager: member.isManager,
                custom_prompt: member.customPrompt
            }}
        }}
    }}));
    
    renderMemberList(); // Re-render to show badges
}}

    let currentScenarioEvents = [];

    function renderScenarioTimeline(events, currentIndex) {{
        // User requested to hide scenario UI
        return; 
        /*
        currentScenarioEvents = events;
        const container = document.getElementById('scenarioTimeline');
        ...
        */
    }}

    function showScenarioDetail(index) {{
        updateDetailContent(index);
        const detailPanel = document.getElementById('scenarioDetail');
        if (detailPanel) detailPanel.classList.add('show');
    }}

    function updateDetailContent(index) {{
        if (!currentScenarioEvents || !currentScenarioEvents[index]) return;
        const event = currentScenarioEvents[index];
        const titleEl = document.getElementById('detailTitle');
        const contentEl = document.getElementById('detailContent');
        if (titleEl) titleEl.textContent = event.Time || `Event ${{index+1}}`;
        if (contentEl) contentEl.textContent = event.Event || 'No description';
    }}

    function toggleScenarioDetail() {{
        const panel = document.getElementById('scenarioDetail');
        if (panel) panel.classList.toggle('show');
    }}

function handleMessage(data) {{
    switch(data.type) {{
        case "message":
            addMessage(data.message);
            updatePreview(data.message);
            updateMemberFromMsg(data.message);
            break;
        case "pat":
            addSystemMessage(`${{data.from_user}} 拍了拍 ${{data.to_user}}`, true);
            break;
        case "recall":
            removeMessageByTimestamp(data.msg_id);
            addSystemMessage(`${{data.from_user}} 撤回了一条消息`, true);
            break;
        case "history":
            clearMessages();
            if (data.messages.length > 0) {{
                addTimeDiv();
                data.messages.forEach(msg => {{
                    addMessage(msg);
                    updateMemberFromMsg(msg);
                }});
                updatePreview(data.messages[data.messages.length - 1]);
            }}
            break;
        case "thought":
            updateThought(data.model, data.content, data.append);
            break;
        case "typing":
            updateTypingIndicator(data.models);
            updateThinkingStatus(data.models);
            break;
        case "status":
            isRunning = data.is_running;
            if (data.member_count) updateMemberCount(data.member_count);
            if (data.group_info) {{
                document.getElementById("groupName").innerText = data.group_info.name;
            }}
            updateStatus();
            
            // Scenario Status
            if (data.scenario_enabled) {{
                renderScenarioTimeline(data.events, data.current_event_idx);
            }}
            break;
        case "scenario_status":
            renderScenarioTimeline(data.events, data.current_event_idx);
            break;
        case "settings_updated":
            if (data.group_name) {{
                document.getElementById("groupName").innerText = data.group_name;
                const sidebarName = document.getElementById("sidebarGroupName");
                if (sidebarName) sidebarName.innerText = data.group_name;
            }}
            if (data.scenario_status) {{
                const sDiv = document.getElementById("scenarioStatus");
                if (!isStageView) {{
                    sDiv.innerText = data.scenario_status;
                    sDiv.style.display = "block";
                }}
            }}
            if (data.member_configs) {{
                // Update local members
                Object.keys(data.member_configs).forEach(name => {{
                    const m = members.find(x => x.name === name);
                    if (m) {{
                        const conf = data.member_configs[name];
                        if (conf.is_manager !== undefined) m.isManager = conf.is_manager;
                        if (conf.custom_prompt !== undefined) m.customPrompt = conf.custom_prompt;
                        if (conf.avatar) m.avatar = conf.avatar;
                    }}
                }});
                renderMemberList();
            }}
            break;
        case "system":
            const isVisibleEvent = data.content.includes("加入群聊") || data.content.includes("拍了拍") || data.content.includes("撤回");
            addSystemMessage(data.content, isVisibleEvent);
            break;
        case "members":
            // Initialize or update members list from server
            data.members.forEach(member => {{
                const existing = members.find(m => m.name === member.name);
                if (existing) {{
                    existing.isManager = member.is_manager;
                    existing.customPrompt = member.custom_prompt;
                    existing.avatar = member.avatar;
                    existing.nickname = member.nickname;
                }} else {{
                    members.push({{
                        name: member.name,
                        nickname: member.nickname,
                        isUser: member.is_user,
                        isManager: member.is_manager,
                        customPrompt: member.custom_prompt || "",
                        lastThought: "",
                        isThinking: false,
                        expanded: false,
                        avatar: member.avatar
                    }});
                }}
            }});
            if (data.group_name) {{
                document.getElementById("groupName").innerText = data.group_name;
                const sidebarName = document.getElementById("sidebarGroupName");
                if (sidebarName) sidebarName.innerText = data.group_name;
            }}
            renderMemberList();
            break;
    }}
}}

function updateMemberFromMsg(msg) {{
    let member = members.find(m => m.name === msg.name);
    if (!member) {{
        member = {{
            name: msg.name,
            nickname: msg.nickname,
            isUser: msg.is_user || msg.name === "Gaia",
            isThinking: false,
            lastThought: "",
            isManager: false,
            customPrompt: ""
        }};
        members.push(member);
        renderMemberList();
    }}
}}

function updateThought(modelName, content, append = false) {{
    let member = members.find(m => m.name === modelName);
    if (!member) {{
        member = {{ name: modelName, isUser: false, isThinking: true, lastThought: content }};
        members.push(member);
    }} else {{
        if (append) {{
            member.lastThought = (member.lastThought || "") + content;
        }} else {{
            member.lastThought = content; // Overwrite with latest thought
        }}
        member.isThinking = true;
    }}
    renderMemberList();
    // If the thought modal is open for this member, update its content
    const modal = document.getElementById("thoughtModal");
    const title = document.getElementById("thoughtModalTitle");
    if (modal.style.display === "flex" && title.textContent.includes(modelName)) {{
        document.getElementById("thoughtModalBody").textContent = member.lastThought;
        // Auto scroll to bottom of thought
        const body = document.getElementById("thoughtModalBody");
        body.scrollTop = body.scrollHeight;
    }}
}}

function updateThinkingStatus(thinkingModels) {{
    members.forEach(m => {{
        if (!m.isUser) {{
            m.isThinking = thinkingModels ? thinkingModels.includes(m.name) : false;
        }}
    }});
    renderMemberList();
}}

let currentEditingMember = null;

function triggerAvatarUpload(name) {{
    currentEditingMember = name;
    document.getElementById('avatarInput').click();
}}

function handleAvatarUpload(input) {{
    if (input.files && input.files[0]) {{
        const file = input.files[0];
        const reader = new FileReader();
        
        reader.onload = function(e) {{
            const base64Data = e.target.result;
            // Send update to server
            if (currentEditingMember && isConnected) {{
                ws.send(JSON.stringify({{
                    type: "update_settings",
                    member_configs: {{
                        [currentEditingMember]: {{
                            avatar: base64Data
                        }}
                    }}
                }}));
            }}
            // Reset input
            input.value = '';
        }};
        
        reader.readAsDataURL(file);
    }}
}}

function renderMemberList() {{
    const list = document.getElementById("memberList");
    const countHeader = document.getElementById("memberCountHeader");
    const panelCount = document.getElementById("panelMemberCount");
    
    list.innerHTML = "";
    
    // Ensure Gaia (user) is at the top, then sort others alphabetically
    const sortedMembers = [...members].sort((a,b) => {{
        if (a.name === "Gaia") return -1;
        if (b.name === "Gaia") return 1;
        return a.name.localeCompare(b.name);
    }});
    
    sortedMembers.forEach(m => {{
        // Fix: Remove red background. Use transparent if avatar exists, or neutral/blue if not.
        let avatarStyle = "";
        if (m.avatar) {{
             avatarStyle = "background: transparent;";
        }} else {{
             avatarStyle = m.isUser 
                ? "background:linear-gradient(135deg,#667eea,#764ba2);" 
                : "background:transparent;"; // User requested NO red background. Let's make it transparent for bots too, or maybe gray?
             // Actually, if no avatar image, we need SOME background to see the white icon.
             // But user said "clean logo". If it's the default robot icon (white), it needs a dark background.
             // If user requested "remove red background", maybe they want a simple gray one?
             if (!m.isUser) avatarStyle = "background:#e0e0e0;"; 
        }}
        
        let icon = m.isUser ? "🌌" : "🤖";
        if (m.avatar) {{
            // Use rounded square to match container
            icon = `<img src="${{m.avatar}}" style="width:100%;height:100%;border-radius:4px;object-fit:cover;">`;
        }}

        const managerBadge = m.isManager ? '<span class="manager-badge">主理人</span>' : '';
        
        // Thinking status
        let statusHtml = '';
        if (m.isThinking && !m.isUser) {{
            statusHtml = `<span class="thinking-status" onclick="event.stopPropagation(); showThought('${{escapeHtml(m.name)}}')">思考中...</span>`;
        }}

        // Settings HTML (only for AI models)
        let settingsHtml = '';
        if (!m.isUser) {{
            settingsHtml = `
            <div class="wc-member-settings" onclick="event.stopPropagation()">
                <div class="setting-row">
                    <span class="setting-label">设为主理人</span>
                    <label class="switch">
                        <input type="checkbox" ${{m.isManager ? 'checked' : ''}} onchange="updateMemberSettings('${{escapeHtml(m.name)}}', 'isManager', this.checked)">
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="setting-row" style="flex-direction:column; align-items:flex-start;">
                    <span class="setting-label">预制提示词</span>
                    <input type="text" class="setting-input" value="${{escapeHtml(m.customPrompt)}}" 
                        onblur="updateMemberSettings('${{escapeHtml(m.name)}}', 'customPrompt', this.value)" 
                        placeholder="为此模型设定特殊人设..." title="修改后点击开始模拟生效">
                </div>
            </div>`;
        }}
        
        // Change onclick to triggerAvatarUpload for avatars
        // New Layout: Avatar | Info (Name + Status)
        const displayName = m.nickname || m.name;
        const html = `
            <div class="wc-member-item ${{m.isThinking ? 'is-thinking' : ''}} ${{m.expanded ? 'expanded' : ''}}" id="member-${{escapeHtml(m.name)}}">
                <div class="wc-member-row" onclick="toggleMemberExpand('${{escapeHtml(m.name)}}')">
                    <div class="wc-member-avatar" style="${{avatarStyle}}" title="点击更换头像" onclick="event.stopPropagation(); triggerAvatarUpload('${{escapeHtml(m.name)}}')">
                        <!-- Removed thinking-ring from avatar, moved status to right -->
                        ${{icon}}
                    </div>
                    <div class="wc-member-info" style="flex:1; min-width:0; display:flex; flex-direction:column; justify-content:center; margin-left:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div class="wc-member-name" title="${{escapeHtml(m.name)}}">${{escapeHtml(displayName)}} ${{managerBadge}}</div>
                        </div>
                        ${{statusHtml}}
                    </div>
                </div>
                ${{settingsHtml}}
            </div>
        `;
        list.insertAdjacentHTML('beforeend', html);
    }});
    
    countHeader.textContent = `(${{members.length}})`;
    panelCount.textContent = members.length;
}}

function toggleMemberExpand(name) {{
    const member = members.find(m => m.name === name);
    if (member && !member.isUser) {{
        member.expanded = !member.expanded;
        renderMemberList();
    }} else if (member && member.isUser) {{
        // Gaia doesn't have settings, maybe just show thought?
        showThought(name);
    }}
}}

function showThought(name) {{
    const member = members.find(m => m.name === name);
    if (!member) return;
    
    const modal = document.getElementById("thoughtModal");
    const title = document.getElementById("thoughtModalTitle");
    const body = document.getElementById("thoughtModalBody");
    
    title.textContent = `${{name}} 的思考内容`;
    body.textContent = member.lastThought || (member.isUser ? "由于该对象是碳基生命，暂无法捕获其神经元信号。" : "该模型尚未输出思考内容。");
    modal.style.display = "flex";
}}

function closeThoughtModal() {{
    document.getElementById("thoughtModal").style.display = "none";
}}

function toggleMemberPanel() {{
    const panel = document.getElementById("memberPanel");
    panel.classList.toggle("open");
}}

function addTimeDiv() {{
    const now = new Date();
    const time = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');
    document.getElementById("messagesContainer").insertAdjacentHTML('beforeend', 
        `<div class="wc-time-divider"><span>${{time}}</span></div>`);
    document.getElementById("lastTime").textContent = time;
}}

function addMessage(msg) {{
    const container = document.getElementById("messagesContainer");
    const isUser = msg.is_user || msg.name === "Gaia";
    
    // Check member list for avatar
    const member = members.find(m => m.name === msg.name);
    let hasAvatar = msg.avatar || (member && member.avatar);
    
    let avatarStyle = "";
    if (hasAvatar) {{
         avatarStyle = "background: transparent;";
    }} else {{
         avatarStyle = isUser 
            ? "background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);" 
            : "background:#e0e0e0;";
    }}
    
    // Check if we should add a time divider
    // Logic: if diff > 30s from last message, show time
    let showTime = false;
    let currentTs = 0;
    
    // msg.ts is a unix timestamp (float) from server
    if (msg.ts) {{
        currentTs = msg.ts;
    }} else if (msg.timestamp) {{
        // Fallback if no ts provided, use current client time or approximate
        currentTs = Date.now() / 1000;
    }}

    // Get last message timestamp from a global variable or data attribute
    // We'll use a global var `lastMsgTimestamp`
    if (!window.lastMsgTimestamp) window.lastMsgTimestamp = 0;
    
    if (currentTs - window.lastMsgTimestamp > 30) {{
        showTime = true;
    }}
    
    // Process timestamp string for display
    let timeStr = "";
    if (msg.timestamp) {{
        const parts = msg.timestamp.split(':');
        if (parts.length >= 2) timeStr = parts[0] + ':' + parts[1];
        else timeStr = msg.timestamp;
    }}

    if (showTime) {{
         container.insertAdjacentHTML('beforeend', `<div class="wc-time-divider"><span>${{timeStr}}</span></div>`);
         window.lastMsgTimestamp = currentTs;
    }}
    
    // User requested: Name MUST be preserved above bubble
    const senderHtml = !isUser ? `<div class="wc-msg-sender" style="font-family: Arial, sans-serif;">${{escapeHtml(msg.nickname || msg.name)}}</div>` : "";
    
    // Find avatar
    let avatarIcon = isUser ? "🌌" : "🤖";
    // Check member list for avatar (already found above as 'member')
    if (msg.avatar) {{
         avatarIcon = `<img src="${{msg.avatar}}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;">`;
    }} else if (member && member.avatar) {{
         avatarIcon = `<img src="${{member.avatar}}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;">`;
    }}

    // Prepare content (Text, Image, Quote)
    let contentHtml = "";
    if (msg.msg_type === "image") {{
        contentHtml = `<div class="wc-msg-image-placeholder">
            <div style="font-size:24px;">🖼️</div>
            <div style="font-size:10px; color:#888;">${{escapeHtml(msg.image_desc || msg.content || "图片")}}</div>
        </div>`;
    }} else {{
        contentHtml = escapeHtml(msg.content).replace(/\\n/g, '<br>');
    }}

    // Prepend Quote if exists
    if (msg.quote) {{
        const quoteHtml = `<div class="wc-quote">
            <div style="font-weight:bold; margin-bottom:2px;">${{escapeHtml(msg.quote.user)}}:</div>
            <div style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${{escapeHtml(msg.quote.text)}}</div>
        </div>`;
        contentHtml = quoteHtml + contentHtml;
    }}

    const html = `<div class="wc-msg-row ${{isUser ? 'self' : 'other'}}" data-timestamp="${{msg.timestamp || ''}}">
        <div class="wc-msg-avatar" style="${{avatarStyle}}" onclick="showThought('${{escapeHtml(msg.name)}}')">${{avatarIcon}}</div>
        <div class="wc-msg-body">
            ${{senderHtml}}
            <div class="wc-bubble">${{contentHtml}}</div>
        </div>
    </div>`;
    container.insertAdjacentHTML('beforeend', html);
    container.scrollTop = container.scrollHeight;
}}

function removeMessageByTimestamp(ts) {{
    if (!ts) return;
    const rows = document.querySelectorAll(`.wc-msg-row[data-timestamp="${{ts}}"]`);
    if (rows.length > 0) {{
        rows[rows.length - 1].remove();
    }}
}}

function addSystemMessage(content, forceVisible = false) {{
    if (isStageView && !forceVisible) return;
    const container = document.getElementById("messagesContainer");
    container.insertAdjacentHTML('beforeend', `<div class="wc-system-msg">${{content}}</div>`);
    container.scrollTop = container.scrollHeight;
}}

function clearMessages() {{
    document.getElementById("messagesContainer").innerHTML = "";
}}

function escapeHtml(text) {{
    if (!text) return "";
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}}

function updatePreview(msg) {{
    const preview = msg.content.length > 20 ? msg.content.substring(0, 20) + "..." : msg.content;
    const name = msg.nickname || msg.name;
    document.getElementById("lastPreview").textContent = (name === "Gaia" ? "" : name + ": ") + preview;
}}

function updateStatus() {{
    const dot = document.getElementById("statusDot");
    if (isConnected) {{
        dot.classList.add("connected");
        if (isRunning) dot.classList.add("running");
        else dot.classList.remove("running");
    }} else {{
        dot.classList.remove("connected", "running");
    }}
}}

function updateMemberCount(count) {{
    // This function is primarily for initial setup or if the server sends a definitive count.
    // The `members` array and `renderMemberList` are the source of truth for displayed count.
    // This can be used to pre-fill if members array is empty.
    if (members.length === 0 && count > 0) {{
        // If no members yet, create placeholders or wait for actual member data
        // For now, we'll let `handleMessage`'s 'members' or 'message' cases populate.
    }}
}}

function updateTypingIndicator(models) {{
    if (isStageView) return;
    const indicator = document.getElementById("typingIndicator");
    if (models && models.length > 0) {{
        indicator.textContent = models.slice(0, 2).join(", ") + " 正在输入...";
    }} else {{
        indicator.textContent = "";
    }}
}}

function sendMessage() {{
    const input = document.getElementById("inputBox");
    const content = input.value.trim();
    if (!content || !isConnected) return;
    
    ws.send(JSON.stringify({{
        type: "user_message",
        name: "Gaia",
        content: content
    }}));
    
    input.value = "";
    input.style.height = "auto";
}}

function resetChat() {{
    if (!isConnected) return;
    ws.send(JSON.stringify({{ type: "reset" }}));
    isRunning = false;
    updateStatus();
    clearMessages();
    window.lastMsgTimestamp = 0; // Reset timestamp tracker
    // addTimeDiv(); // No need to add time immediately on reset
    // 清空成员的思考内容
    members.forEach(m => m.lastThought = "");
    // Close thought modal if open
    closeThoughtModal();
}}

function clearChat() {{
    if (!isConnected) return;
    ws.send(JSON.stringify({{ type: "clear" }}));
    clearMessages();
    addTimeDiv();
    // 清空成员的思考内容
    members.forEach(m => m.lastThought = "");
    // Close thought modal if open
    closeThoughtModal();
}}

// 回车发送
document.getElementById("inputBox").addEventListener("keydown", function(e) {{
    if (e.key === "Enter" && !e.shiftKey) {{
        e.preventDefault();
        sendMessage();
        // Stop typing status immediately on send
        if (typingTimeout) {{
             clearTimeout(typingTimeout);
             if (isConnected) ws.send(JSON.stringify({{ type: "user_typing", is_typing: false }}));
             typingTimeout = null;
        }}
    }}
}});

// User Typing Detection
let typingTimeout = null;
document.getElementById("inputBox").addEventListener("input", function() {{
    // Send typing started if not already in typing state
    if (!typingTimeout) {{
        if (isConnected) {{
            ws.send(JSON.stringify({{ type: "user_typing", is_typing: true }}));
        }}
    }}

    // Clear previous timeout
    if (typingTimeout) {{
        clearTimeout(typingTimeout);
    }}

    // Set new timeout to stop typing status after 2s of inactivity
    typingTimeout = setTimeout(function() {{
        if (isConnected) {{
            ws.send(JSON.stringify({{ type: "user_typing", is_typing: false }}));
        }}
        typingTimeout = null;
    }}, 2000);
}});

// 自动调整高度 (Disabled: using fixed height area now)
// document.getElementById("inputBox").addEventListener("input", function() {{
//    this.style.height = "auto";
//    this.style.height = Math.min(this.scrollHeight, 80) + "px";
// }});


const COMMON_EMOJIS = [
    "😀", "😁", "😂", "🤣", "😃", "😄", "😅", "😆", "😉", "😊", "😋", "😎", "😍", "😘", "🥰", "😗", "😙", "😚", "🙂", "🤗", "🤩", "🤔", "🤨", "😐", "😑", "😶", "🙄", "😏", "😣", "😥", "😮", "🤐", "😯", "😪", "😫", "😴", "😌", "😛", "😜", "😝", "🤤", "😒", "😓", "😔", "😕", "🙃", "🤑", "😲", "☹️", "🙁", "😖", "😞", "😟", "😤", "😢", "😭", "😦", "😧", "😨", "😩", "🤯", "😬", "😰", "😱", "🥵", "🥶", "😳", "🤪", "😵", "😡", "😠", "🤬", "😷", "🤒", "🤕", "🤢", "🤮", "🤧", "😇", "🥳", "🥴", "🥺", "🤠", "🤡", "🤥", "🤫", "🤭", "🧐", "🤓", "😈", "👿", "👹", "👺", "💀", "👻", "👽", "🤖", "💩", "😺", "😸", "😹", "😻", "😼", "😽", "🙀", "😿", "😾",
    "🤲", "👐", "🙌", "👏", "🤝", "👍", "👎", "👊", "✊", "🤛", "🤜", "🤞", "✌️", "🤟", "🤘", "👌", "👈", "👉", "👆", "👇", "☝️", "✋", "🤚", "🖐", "🖖", "👋", "🤙", "💪", "🖕", "✍️", "🙏", "🦶", "🦵", "💄", "💋", "👄", "🦷", "👅", "👂", "👃", "👣", "👁", "👀", "🧠", "🗣", "👤", "👥", "👶", "👧", "🧒", "👦", "👩", "🧑", "👨", "👩‍🦱", "👨‍🦱", "👩‍🦰", "👨‍🦰", "👱‍♀️", "👱‍♂️", "👩‍🦳", "👨‍🦳", "👩‍🦲", "👨‍🦲", "🧔", "👵", "🧓", "👴", "👲", "👳‍♀️", "👳‍♂️", "🧕", "👮‍♀️", "👮‍♂️", "👷‍♀️", "👷‍♂️", "💂‍♀️", "💂‍♂️", "🕵️‍♀️", "🕵️‍♂️", "👩‍⚕️", "👨‍⚕️", "👩‍🌾", "👨‍🌾", "👩‍🍳", "👨‍🍳", "👩‍🎓", "👨‍🎓", "👩‍🎤", "👨‍🎤", "👩‍🏫", "👨‍🏫", "👩‍🏭", "👨‍🏭", "👩‍💻", "👨‍💻", "👩‍💼", "👨‍💼", "👩‍🔧", "👨‍🔧", "👩‍🔬", "👨‍🔬", "👩‍🎨", "👨‍🎨", "👩‍🚒", "👨‍🚒", "👩‍✈️", "👨‍✈️", "👩‍🚀", "👨‍🚀", "👩‍⚖️", "👨‍⚖️", "👰", "🤵", "👸", "🤴", "🦸‍♀️", "🦸‍♂️", "🦹‍♀️", "🦹‍♂️", "🤶", "🎅", "🧙‍♀️", "🧙‍♂️", "🧝‍♀️", "🧝‍♂️", "🧛‍♀️", "🧛‍♂️", "🧟‍♀️", "🧟‍♂️", "🧞‍♀️", "🧞‍♂️", "🧜‍♀️", "🧜‍♂️", "🧚‍♀️", "🧚‍♂️", "👼", "🤰", "🤱", "🙇‍♀️", "🙇‍♂️", "💁‍♀️", "💁‍♂️", "🙅‍♀️", "🙅‍♂️", "🙆‍♀️", "🙆‍♂️", "🙋‍♀️", "🙋‍♂️", "🤦‍♀️", "🤦‍♂️", "🤷‍♀️", "🤷‍♂️", "🙎‍♀️", "🙎‍♂️", "🙍‍♀️", "🙍‍♂️", "💇‍♀️", "💇‍♂️", "💆‍♀️", "💆‍♂️", "🧖‍♀️", "🧖‍♂️", "💅", "🤳", "💃", "🕺", "👯‍♀️", "👯‍♂️", "🕴", "🚶‍♀️", "🚶‍♂️", "🏃‍♀️", "🏃‍♂️", "👫", "👭", "👬", "💑", "👩‍❤️‍👩", "👨‍❤️‍👨", "💏", "👩‍❤️‍💋‍👩", "👨‍❤️‍💋‍👨", "👪", "👨‍👩‍👧", "👨‍👩‍👧‍👦", "👨‍👩‍👦‍👦", "👨‍👩‍👧‍👧", "👩‍👩‍👦", "👩‍👩‍👧", "👩‍👩‍👧‍👦", "👩‍👩‍👦‍👦", "👩‍👩‍👧‍👧", "👨‍👨‍👦", "👨‍👨‍👧", "👨‍👨‍👧‍👦", "👨‍👨‍👦‍👦", "👨‍👨‍👧‍👧", "👩‍👦", "👩‍👧", "👩‍👧‍👦", "👩‍👦‍👦", "👩‍👧‍👧", "👨‍👦", "👨‍👧", "👨‍👧‍👦", "👨‍👦‍👦", "👨‍👧‍👧",
    "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🦝", "🐻", "🐼", "🦘", "🦡", "🐨", "🐯", "🦁", "🐮", "🐷", "🐽", "🐸", "🐵", "🙈", "🙉", "🙊", "🐒", "🐔", "🐧", "🐦", "🐤", "🐣", "🐥", "🦆", "🦢", "🦅", "🦉", "🦚", "🦜", "🦇", "🐺", "🐗", "🐴", "🦄", "🐝", "🐛", "🦋", "🐌", "🐚", "🐞", "🐜", "🦗", "🕷", "🕸", "🦂", "🦟", "🦠", "🐢", "🐍", "🦎", "🦖", "🦕", "🐙", "🦑", "🦐", "🦀", "🐡", "🐠", "🐟", "🐬", "🐳", "🐋", "🦈", "🐊", "🐅", "🐆", "🦓", "🦍", "🐘", "🦏", "🦛", "🐪", "🐫", "🦙", "🦒", "🐃", "🐂", "🐄", "🐎", "🐖", "🐏", "🐑", "🐐", "🦌", "🐕", "🐩", "🐈", "🐓", "🦃", "🕊", "🐇", "🐁", "🐀", "🐿", "🦔", "🐾", "🐉", "🐲",
    "🍏", "🍎", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🍈", "🍒", "🍑", "🍍", "🥭", "🥥", "🥝", "🍅", "🍆", "🥑", "🥦", "🥒", "🥬", "🌶", "🌽", "🥕", "🥔", "🍠", "🥐", "🥯", "🍞", "🥖", "🥨", "🥞", "🧀", "🍖", "🍗", "🥩", "🥓", "🍔", "🍟", "🍕", "🌭", "🥪", "🌮", "🌯", "🥙", "🥚", "🍳", "🥘", "🍲", "🥣", "🥗", "🍿", "🧂", "🥫", "🍱", "🍘", "🍙", "🍚", "🍛", "🍜", "🍝", "🍠", "🍢", "🍣", "🍤", "🍥", "🥮", "🍡", "🥟", "🥠", "🥡", "🍦", "🍧", "🍨", "🍩", "🍪", "🎂", "🍰", "🧁", "🥧", "🍫", "🍬", "🍭", "🍮", "🍯", "🍼", "🥛", "☕️", "🍵", "🍶", "🍾", "🍷", "🍸", "🍹", "🍺", "🍻", "🥂", "🥃", "🥤", "🥢", "🍽", "🍴", "🥄", "🔪", "🏺",
    "⚽️", "🏀", "🏈", "⚾️", "🥎", "🎾", "🏐", "🏉", "🥏", "🎱", "🏓", "🏸", "🥅", "🏒", "🏑", "🥍", "🏏", "⛳️", "🏹", "🎣", "🥊", "🥋", "🎽", "🛹", "🛷", "⛸", "🥌", "🎿", "⛷", "🏂", "🏋️‍♀️", "🏋️‍♂️", "🤼‍♀️", "🤼‍♂️", "🤸‍♀️", "🤸‍♂️", "⛹️‍♀️", "⛹️‍♂️", "🤾‍♀️", "🤾‍♂️", "🧗‍♀️", "🧗‍♂️", "🏌️‍♀️", "🏌️‍♂️", "🧘‍♀️", "🧘‍♂️", "🧖‍♀️", "🧖‍♂️", "🏄‍♀️", "🏄‍♂️", "🏊‍♀️", "🏊‍♂️", "🤽‍♀️", "🤽‍♂️", "🚣‍♀️", "🚣‍♂️", "🏇", "🚴‍♀️", "🚴‍♂️", "🚵‍♀️", "🚵‍♂️", "🎽", "🎖", "🏅", "🥇", "🥈", "🥉", "🏆", "🏵", "🎗", "🎫", "🎟", "🎪", "🤹‍♀️", "🤹‍♂️", "🎭", "🎨", "🎬", "🎤", "🎧", "🎼", "🎹", "🥁", "🎷", "🎺", "🎸", "🎻", "🎲", "♟", "🎯", "🎳", "🎮", "🎰", "🧩",
    "🚗", "🚕", "🚙", "🚌", "🚎", "🏎", "🚓", "🚑", "🚒", "🚐", "🚚", "🚛", "🚜", "🛴", "🚲", "🛵", "🏍", "🚨", "🚔", "🚍", "🚘", "🚖", "🚡", "🚠", "🚟", "🚃", "🚋", "🚞", "🚝", "🚄", "🚅", "🚈", "🚂", "🚆", "🚇", "🚊", "🚉", "✈️", "🛫", "🛬", "🛩", "💺", "🛰", "🚀", "🛸", "🚁", "🛶", "⛵️", "🚤", "🛥", "🛳", "⛴", "🚢", "⚓️", "⛽️", "🚧", "🚦", "🚥", "🚏", "🗺", "🗿", "🗽", "🗼", "🏰", "🏯", "🏟", "🎡", "🎢", "🎠", "⛲️", "⛱", "🏖", "🏝", "🏜", "🌋", "⛰", "🏔", "🗻", "🏕", "⛺️", "🏠", "🏡", "🏘", "🏚", "🏗", "🏭", "🏢", "🏬", "🏣", "🏤", "🏥", "🏦", "🏨", "🏪", "🏫", "🏩", "💒", "🏛", "⛪️", "🕌", "🕍", "🕋", "⛩", "🛤", "🛣", "🗾", "🎑", "🏞", "🌅", "🌄", "🌠", "🎇", "🎆", "🌇", "🌆", "🏙", "🌃", "🌌", "🌉", "🌁",
    "⌚️", "📱", "📲", "💻", "⌨️", "🖥", "🖨", "🖱", "🖲", "🕹", "🗜", "💽", "💾", "💿", "📀", "📼", "📷", "📸", "📹", "🎥", "📽", "🎞", "📞", "☎️", "📟", "📠", "📺", "📻", "🎙", "🎚", "🎛", "🧭", "⏱", "⏲", "⏰", "🕰", "⌛️", "⏳", "📡", "🔋", "🔌", "💡", "🔦", "🕯", "🪔", "🧯", "🛢", "💸", "💵", "💴", "💶", "💷", "💰", "💳", "💎", "⚖️", "🧰", "🔧", "🔨", "⚒", "🛠", "⛏", "🔩", "⚙️", "🧱", "⛓", "🧲", "🔫", "💣", "🧨", "🔪", "🗡", "⚔️", "🛡", "🚬", "⚰️", "⚱️", "🏺", "🔮", "📿", "🧿", "💈", "⚗️", "🔭", "🔬", "🕳", "💊", "💉", "🩸", "🩹", "🩺", "🌡", "🏷", "🔖", "🚽", "🚿", "🛁", "🛀", "🪒", "🧴", "🧻", "🧼", "🧽", "🧹", "🧺", "🧷", "🔑", "🗝", "🧸", "🛌", "🛏", "🚪", "🛋", "🪑", "🚽", "🚿", "🛁", "🛀", "🪒", "🧴", "🧻", "🧼", "🧽", "🧹", "🧺", "🧷", "🧯", "🛒", "🚬", "⚰️", "⚱️", "🗿",
    "❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💔", "❣️", "💕", "💞", "💓", "💗", "💖", "💘", "💝", "💟", "☮️", "✝️", "☪️", "🕉", "☸️", "✡️", "🔯", "🕎", "☯️", "☦️", "🛐", "⛎", "♈️", "♉️", "♊️", "♋️", "♌️", "♍️", "♎️", "♏️", "♐️", "♑️", "♒️", "♓️", "🆔", "⚛️", "🉑", "☢️", "☣️", "📴", "📳", "🈶", "🈚️", "🈸", "🈺", "🈷️", "✴️", "🆚", "💮", "🉐", "㊙️", "㊗️", "🈴", "🈵", "🈹", "🈲", "🅰️", "🅱️", "🆎", "🆑", "🅾️", "🆘", "❌", "⭕️", "🛑", "⛔️", "📛", "🚫", "💯", "💢", "♨️", "🚷", "🚯", "🚳", "🚱", "🔞", "📵", "🚭", "❗️", "❕", "❓", "❔", "‼️", "⁉️", "🔅", "🔆", "〽️", "⚠️", "🚸", "🔱", "⚜️", "🔰", "♻️", "✅", "🈯️", "💹", "❇️", "✳️", "❎", "🌐", "💠", "Ⓜ️", "🌀", "💤", "🏧", "🚾", "♿️", "🅿️", "🈳", "🈂️", "🛂", "🛃", "🛄", "🛅", "🚹", "🚺", "🚼", "🚻", "🚮", "🎦", "📶", "🈁", "🔣", "ℹ️", "🔤", "🔡", "🔠", "🆖", "🆗", "🆙", "🆒", "🆕", "🆓", "0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "🔢", "#️⃣", "*️⃣", "⏏️", "▶️", "⏸", "⏯", "⏹", "⏺", "⏭", "⏮", "⏩", "⏪", "⏫", "⏬", "◀️", "🔼", "🔽", "➡️", "⬅️", "⬆️", "⬇️", "↗️", "↘️", "↙️", "↖️", "↕️", "↔️", "↪️", "↩️", "⤴️", "⤵️", "🔀", "🔁", "🔂", "🔄", "🔃", "🎵", "🎶", "➕", "➖", "➗", "✖️", "♾", "💲", "💱", "™️", "©️", "®️", "👁‍🗨", "🔚", "🔙", "🔛", "🔝", "🔜", "〰️", "➰", "➿", "✔️", "☑️", "🔘", "🔴", "🟠", "🟡", "🟢", "🔵", "🟣", "⚫️", "⚪️", "🟤", "🔺", "🔻", "🔸", "🔹", "🔶", "🔷", "🔳", "🔲", "▪️", "▫️", "◾️", "◽️", "◼️", "◻️", "🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "⬛️", "⬜️", "🟫", "🔈", "🔇", "🔉", "🔊", "🔔", "🔕", "📣", "📢", "💬", "💭", "🗯", "♠️", "♣️", "♥️", "♦️", "🃏", "🎴", "🀄️", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚", "🕛", "🕜", "🕝", "🕞", "🕟", "🕠", "🕡", "🕢", "🕣", "🕤", "🕥", "🕦", "🕧"
];

function initEmojiPicker() {{
    const picker = document.getElementById("emojiPicker");
    COMMON_EMOJIS.forEach(emoji => {{
        const span = document.createElement("span");
        span.className = "emoji-item";
        span.innerText = emoji;
        span.onclick = function(e) {{
            e.stopPropagation();
            insertEmoji(emoji);
        }};
        picker.appendChild(span);
    }});
    
    // Close picker when clicking outside
    document.addEventListener("click", function(e) {{
        if (!e.target.closest(".emoji-picker") && !e.target.closest(".wc-tool-btn[title='表情']")) {{
            picker.style.display = "none";
        }}
    }});
}}

function toggleEmojiPicker(e) {{
    e.stopPropagation();
    const picker = document.getElementById("emojiPicker");
    picker.style.display = picker.style.display === "grid" ? "none" : "grid";
}}

function insertEmoji(emoji) {{
    const input = document.getElementById("inputBox");
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const text = input.value;
    const before = text.substring(0, start);
    const after = text.substring(end, text.length);
    input.value = before + emoji + after;
    input.selectionStart = input.selectionEnd = start + emoji.length;
    input.focus();
    // Close picker
    document.getElementById("emojiPicker").style.display = "none";
}}

// Initialize
initEmojiPicker();

function initStageUI() {{
    if (SCENARIO_CONFIG && SCENARIO_CONFIG.stage_type && SCENARIO_CONFIG.stage_type !== "聊天群聊") {{
        const titleEl = document.querySelector(".title-text");
        if (titleEl) {{
            titleEl.innerText = SCENARIO_CONFIG.stage_type + " (待开发)";
            titleEl.style.color = "#ff4d4f";
        }}
        
        const body = document.querySelector(".wc-body");
        if (body) {{
            const watermark = document.createElement("div");
            watermark.innerText = "⚠️ 界面待开发 - 仅文本模拟";
            watermark.style.position = "absolute";
            watermark.style.top = "50%";
            watermark.style.left = "50%";
            watermark.style.transform = "translate(-50%, -50%)";
            watermark.style.opacity = "0.1";
            watermark.style.fontSize = "24px";
            watermark.style.pointerEvents = "none";
            watermark.style.zIndex = "0";
            body.appendChild(watermark);
        }}
    }}
}}

initStageUI();
connect();
</script>
</body>
</html>'''
    
    components.html(html_content, height=670, scrolling=False)
