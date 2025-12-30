import streamlit as st
import pandas as pd
import re
import json
from core.director import Director

def render_director_panel(client, model_name):
    """
    Renders the upgraded AI Director panel with random generation and single-selection timeline.
    """
    st.subheader("🎬 AI 导演编排 (AI Director)")
    
    # 1. Topic & Constraints
    with st.container(border=True):
        topic_c1, topic_c2 = st.columns([4, 1])
        with topic_c1:
            topic = st.text_input("剧本主题", value=st.session_state.get("scenario_theme", ""), placeholder="例如：赛博朋克版红楼梦", label_visibility="collapsed")
            st.session_state.scenario_theme = topic
        
        with topic_c2:
            with st.popover("🎲 随机配置", use_container_width=True):
                st.markdown("##### 🛠️ 剧本生成配置")
                genre = st.selectbox("剧本类型", ["🎲 随机", "🛸 科幻", "🕵️ 悬疑", "🏰 奇幻", "🏙️ 现代日常", "👻 恐怖"])
                reality = st.select_slider("世界观现实程度", options=["🪐 完全架空", "🔮 超现实/魔幻", "🏙️ 艺术加工的现实", "📹 严格写实"], value="🏙️ 艺术加工的现实")
                min_events, max_events = st.slider("时间线事件数量", 3, 12, (3, 6))
                
                if st.button("🚀 开始生成", use_container_width=True, type="primary"):
                    if not topic:
                        st.toast("请先输入剧本主题！", icon="⚠️")
                    else:
                        director = Director(client, model_name)
                        with st.spinner("导演正在疯狂构思剧本..."):
                            constraints = {
                                "genre": genre,
                                "reality": reality,
                                "min_events": min_events,
                                "max_events": max_events,
                                "stage": st.session_state.get("current_stage_type", "聊天群聊")
                            }
                            df = director.generate_script_with_constraints(topic, constraints)
                            if not df.empty:
                                st.session_state.scenario_df = df
                                st.session_state.director_phase = "idle" # Reset phase
                                st.success("剧本已生成！")
                                st.rerun()

    # 2. Timeline Editor
    st.divider()
    st.subheader("📜 剧本时间线 (Timeline)")
    if not st.session_state.scenario_df.empty:
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
            key="scenario_editor_v2"
        )

        # Mutual exclusivity for 'Selected'
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
            
        # Start Casting Button
        st.write("")
        c_btn1, c_btn2, c_btn3 = st.columns([1, 2, 1])
        if c_btn2.button("👥 开始智能选角 (Start Casting)", use_container_width=True, type="primary"):
            actors_list = [c["name"] for c in st.session_state.llm_configs]
            if not actors_list:
                st.error("请先在 Config 页面配置至少一个受试模型！")
            else:
                director = Director(client, model_name)
                with st.spinner("导演正在进行选角..."):
                    casting = director.auto_casting(topic, actors_list, st.session_state.current_stage_type, st.session_state.scenario_df)
                    # Convert casting map to list for data_editor
                    data_for_editor = []
                    for mid in actors_list:
                        info = casting.get(mid, {"role": "待定", "nickname": mid, "brief": "待定"})
                        data_for_editor.append({
                            "Model ID": mid,
                            "Role": info.get("role", "待定"),
                            "Nickname": info.get("nickname", mid),
                            "Brief": info.get("brief", "待定")
                        })
                    st.session_state.casting_data = data_for_editor
                    st.session_state.director_phase = "reviewing"
                    st.success("选角完成！请在【角色分配】页审核。")
                    # Auto switch tab could be nice, but Streamlit tabs are hard to switch programmatically without complexity
    else:
        st.info("👈 请先生成或手动添加剧本事件")
