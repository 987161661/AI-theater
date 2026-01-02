import streamlit as st
import pandas as pd
import re
import json
import requests
from core.director import Director
from core.utils.rag_engine import RAGEngine
from core.llm_provider import LLMProvider
from core.state.manager import state_manager
import os

def handle_theme_generation(client, model_name):
    """
    Handles the backend call for theme generation.
    Must be called BEFORE any UI rendering to avoid state modification errors.
    """
    if st.session_state.get("trigger_theme_gen"):
        st.session_state.trigger_theme_gen = False # Reset flag
        
        if not st.session_state.llm_configs:
            st.toast("请先配置 LLM！", icon="⚠️")
        else:
            cfg = st.session_state.llm_configs[0]
            # Ensure parameters are initialized
            if "director_genre" not in st.session_state: st.session_state.director_genre = "🎲 随机"
            if "director_reality" not in st.session_state: st.session_state.director_reality = "🏙️ 艺术加工的现实"
            count = st.session_state.get("director_theme_count", 1)
            
            payload = {
                "genre": st.session_state.director_genre,
                "reality": st.session_state.director_reality,
                "stage": st.session_state.get("current_stage_type", "聊天群聊"),
                "count": count,
                "llm_config": cfg
            }
            
            with st.spinner(f"正在构思 {count} 个灵感... (后端生成)"):
                try:
                    response = requests.post("http://localhost:8000/generate_theme", json=payload)
                    if response.status_code == 200:
                        themes = response.json().get("themes", [])
                        if themes:
                            st.session_state.generated_themes_cache = themes
                            # Default select the first one if current theme is empty
                            if not st.session_state.scenario_theme:
                                st.session_state.scenario_theme = themes[0]
                            st.toast(f"成功获取 {len(themes)} 个灵感！", icon="✨")
                    else:
                        st.error(f"生成失败: {response.text}")
                except Exception as e:
                    st.error(f"连接后端失败: {e}")

def render_director_panel(client, model_name):
    """
    Renders the upgraded AI Director panel with stage selection, 
    script persistence, automated choreography, and enhanced casting.
    """
    
    st.subheader("🎬 AI 导演编排 (AI Director)")
    
    # 0. Stage Selection (Prioritized Workflow)
    with st.container(border=True):
        st.markdown("##### 🏟️ 第一步：选择表演舞台 (Select Stage)")
        stage_options = ['聊天群聊', '网站论坛', '跑团桌', '辩论赛', '审判法庭', '博弈游戏', '传话筒迷宫']
        selected_stage = st.selectbox(
            "当前舞台环境", 
            stage_options, 
            index=stage_options.index(st.session_state.current_stage_type) if st.session_state.current_stage_type in stage_options else 0,
            key="director_stage_selection"
        )
        st.session_state.current_stage_type = selected_stage
        st.caption(f"导演将根据 **{selected_stage}** 的规则来构思后续剧本与选角。")

    # 1. RAG Engine Initialization
    if "rag_engine" not in st.session_state:
        if st.session_state.llm_configs:
            cfg = st.session_state.llm_configs[0]
            provider = LLMProvider(cfg["api_key"], cfg["base_url"], cfg["model"])
            st.session_state.rag_engine = RAGEngine(provider)
        else:
            st.session_state.rag_engine = None

    # 2. Topic & Generation
    st.write("")
    st.markdown("##### 📝 第二步：剧本构思与生成 (Script Generation)")
    
    if "director_genre" not in st.session_state: st.session_state.director_genre = "🎲 随机"
    if "director_reality" not in st.session_state: st.session_state.director_reality = "🏙️ 艺术加工的现实"
    if "generated_themes_cache" not in st.session_state: st.session_state.generated_themes_cache = []
    
    with st.container(border=True):
        topic_c1, topic_c2, topic_c3 = st.columns([3, 1, 1])
        
        with topic_c1:
            # Theme Input / Selection
            if st.session_state.generated_themes_cache:
                selected_theme = st.selectbox(
                    "选择或输入剧本主题", 
                    options=st.session_state.generated_themes_cache,
                    index=0,
                    key="scenario_theme_select",
                    label_visibility="collapsed"
                )
                # Sync selection to the main state variable
                if selected_theme != st.session_state.get("scenario_theme"):
                    st.session_state.scenario_theme = selected_theme
            else:
                st.text_input("剧本主题", key="scenario_theme", placeholder="例如：赛博朋克版红楼梦", label_visibility="collapsed")
        
        with topic_c2:
            # Theme Count Counter
            if "director_theme_count" not in st.session_state: st.session_state.director_theme_count = 1
            
            cnt_c1, cnt_c2, cnt_c3 = st.columns([1, 2, 1])
            with cnt_c1:
                if st.button("➖", key="theme_cnt_minus", use_container_width=True):
                    if st.session_state.director_theme_count > 1:
                        st.session_state.director_theme_count -= 1
            with cnt_c2:
                 st.markdown(f"<div style='text-align: center; line-height: 2.2;'><b>{st.session_state.director_theme_count}</b></div>", unsafe_allow_html=True)
            with cnt_c3:
                if st.button("➕", key="theme_cnt_plus", use_container_width=True):
                     st.session_state.director_theme_count += 1

        with topic_c3:
            # Use on_click callback to trigger the logic at the start of the NEXT run
            def on_inspire_click():
                st.session_state.trigger_theme_gen = True
            
            st.button(
                "✨ 灵感", 
                use_container_width=True, 
                help=f"点击生成 {st.session_state.director_theme_count} 个随机灵感",
                on_click=on_inspire_click
            )
        
        # Additional Config Popover (Below main row or integrated if space allows, kept separate for clarity)
        with st.popover("⚙️ 更多配置", use_container_width=True):
            st.markdown("##### 🛠️ 剧本生成配置")
            genre_opts = ["🎲 随机", "🛸 科幻", "🕵️ 悬疑", "🏰 奇幻", "🏙️ 现代日常", "👻 恐怖"]
            genre = st.selectbox("剧本类型", genre_opts, 
                                    index=genre_opts.index(st.session_state.director_genre) if st.session_state.director_genre in genre_opts else 0)
            st.session_state.director_genre = genre
            
            reality_opts = ["🪐 完全架空", "🔮 超现实/魔幻", "🏙️ 艺术加工的现实", "📹 严格写实"]
            reality = st.select_slider("世界观现实程度", options=reality_opts, 
                                        value=st.session_state.director_reality if st.session_state.director_reality in reality_opts else "🏙️ 艺术加工的现实")
            st.session_state.director_reality = reality
            
            min_events, max_events = st.slider("时间线事件数量", 3, 12, (3, 6))
            
        if st.button("🚀 开始生成剧本结构", use_container_width=True, type="primary"):
            if not st.session_state.scenario_theme:
                st.toast("请先输入或生成剧本主题！", icon="⚠️")
            else:
                director = Director(client, model_name, st.session_state.get("rag_engine"))
                with st.spinner("导演正在疯狂构思剧本..."):
                    constraints = {
                        "genre": st.session_state.director_genre,
                        "reality": st.session_state.director_reality,
                        "min_events": min_events,
                        "max_events": max_events,
                        "stage": st.session_state.current_stage_type
                    }
                    df = director.generate_script_with_constraints(st.session_state.scenario_theme, constraints)
                    if not df.empty:
                        st.session_state.scenario_df = df
                        st.session_state.director_phase = "idle" 
                        st.success("剧本已生成！")
                        st.rerun()

        uploaded_file = st.file_uploader("📥 上传素材 (PDF/Text) 增强剧作灵感", type=["pdf", "txt", "md"])
        if uploaded_file and st.session_state.rag_engine:
            with st.spinner("正在解析素材..."):
                temp_path = f"temp_{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                
                if uploaded_file.type == "application/pdf":
                    st.session_state.rag_engine.process_pdf(temp_path)
                else:
                    with open(temp_path, "r", encoding="utf-8") as f:
                        st.session_state.rag_engine.process_text(f.read())
                
                os.remove(temp_path)
                st.success(f"已学习素材：{uploaded_file.name}")

    # 3. Script Persistence
    st.write("")
    st.markdown("##### 💾 剧本存档 (Save / Load)")
    p_c1, p_c2 = st.columns([1, 1])
    
    with p_c1:
        if st.button("📁 保存当前剧本", use_container_width=True):
            if st.session_state.scenario_df.empty:
                st.warning("当前没有可保存的剧本时间线。")
            else:
                content = st.session_state.scenario_df.to_dict("records")
                script_id = state_manager.db.save_script(st.session_state.scenario_theme, content)
                st.success(f"剧本已存档 (ID: {script_id})")
    
    with p_c2:
        with st.popover("📂 加载历史剧本", use_container_width=True):
            scripts = state_manager.db.get_all_scripts()
            if not scripts:
                st.info("暂无存档。")
            else:
                for s in scripts:
                    sc1, sc2 = st.columns([3, 1])
                    sc1.write(f"**{s['topic']}**")
                    sc1.caption(f"创建于: {s['created_at']}")
                    if sc2.button("加载", key=f"load_s_{s['id']}"):
                        full_script = state_manager.db.get_script_by_id(s["id"])
                        if full_script:
                            st.session_state.scenario_df = pd.DataFrame(full_script["content"])
                            st.session_state.scenario_theme = full_script["topic"]
                            st.success("剧本已调出！")
                            st.rerun()
                    if sc2.button("🗑️", key=f"del_s_{s['id']}"):
                        state_manager.db.delete_script(s["id"])
                        st.rerun()

    # 4. Timeline Editor
    st.divider()
    st.subheader("📜 剧本时间线 (Timeline)")
    if not st.session_state.scenario_df.empty:
        # Ensure "Selected" column exists
        if "Selected" not in st.session_state.scenario_df.columns:
            st.session_state.scenario_df.insert(0, "Selected", False)
            # Default select the first row
            if len(st.session_state.scenario_df) > 0:
                st.session_state.scenario_df.at[0, "Selected"] = True

        # Display Event Detail Box based on selection
        selected_rows = st.session_state.scenario_df[st.session_state.scenario_df["Selected"]]
        
        # Determine content to display
        if not selected_rows.empty:
            # Show selected event
            current_event = selected_rows.iloc[0]
            evt_time = current_event.get("Time", "Unknown Time")
            evt_desc = current_event.get("Event", "No Description")
            evt_goal = current_event.get("Goal", "")
            
            st.info(f"**📌 当前选中：{evt_time}**\n\n{evt_desc}\n\n*🎯 阶段目标：{evt_goal}*")
        else:
            # Fallback (should ideally be covered by default selection, but just in case)
            st.info("👈 请在下方勾选某一幕以查看详细事件内容")

        old_df = st.session_state.scenario_df.copy()
        
        edited_df = st.data_editor(
            st.session_state.scenario_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Selected": st.column_config.CheckboxColumn("✨", help="勾选以激活此时间点", default=False, width="small"),
                "Time": st.column_config.TextColumn("虚拟时间"),
                "Event": st.column_config.TextColumn("事件描述", width="large"),
                "Goal": st.column_config.TextColumn("阶段性目标")
            },
            hide_index=True,
            key="scenario_editor_v3"
        )

        if not edited_df["Selected"].equals(old_df["Selected"]):
            new_selected = edited_df.index[edited_df["Selected"]].tolist()
            old_selected = old_df.index[old_df["Selected"]].tolist()
            newly_clicked = list(set(new_selected) - set(old_selected))
            
            if newly_clicked:
                target_idx = newly_clicked[0]
                edited_df["Selected"] = False
                edited_df.at[target_idx, "Selected"] = True
            
            st.session_state.scenario_df = edited_df
            st.rerun()
        else:
            st.session_state.scenario_df = edited_df
            
        # Start Casting Button with Participation Preference
        st.divider()
        st.subheader("👥 角色选定 (Role Suggestion)")
        c_opt1, c_opt2 = st.columns([1, 1])
        with c_opt1:
            deep_participation = st.checkbox("👤 深度参与剧情 (Deep Participation)", 
                                             value=st.session_state.get("user_deep_participation", False),
                                             help="勾选后，导演将为您分配核心剧情任务；否则降级为普通客串。")
            st.session_state.user_deep_participation = deep_participation
        
        with c_opt2:
            if st.button("🪄 开始智能选角", use_container_width=True, type="primary"):
                director = Director(client, model_name)
                try:
                    with st.spinner("导演正在审稿并建议人选..."):
                        # Pass participation preference
                        suggested_roles = director.auto_casting(
                            st.session_state.scenario_theme, 
                            [], # Dynamic roles don't need actor list yet
                            st.session_state.current_stage_type, 
                            st.session_state.scenario_df,
                            deep_participation
                        )
                        
                        if suggested_roles:
                            # Store suggested roles in state
                            st.session_state.casting_data = suggested_roles
                            st.session_state.director_phase = "reviewing"
                            
                            # Trigger navigation flag (we'll use this in the main page)
                            st.session_state.nav_to_casting = True
                            st.success("选角建议已生成！即将前往分配模块。")
                            st.rerun()
                        else:
                            import traceback
                            traceback.print_exc()
                            st.error("未能生成有效的角色建议，请稍后重试。详细错误请查看终端日志。")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    st.error(f"智能选角发生错误: {e}")
                    with st.expander("错误详情"):
                        st.code(traceback.format_exc())
                    # Do not navigate
    else:
        st.info("👈 请先选择舞台并生成或手动添加剧本事件")
