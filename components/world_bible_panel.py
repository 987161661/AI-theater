import streamlit as st
import pandas as pd
from core.director import Director

def render_world_bible_panel(client, model_name):
    """
    Renders Stage Selection, World Bible Generation, and Casting Review.
    """
    st.subheader("🌍 阶段一：世界观与舞台 (Stage & Bible)")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        stage_options = ['聊天群聊', '网站论坛', '跑团桌', '辩论赛', '审判法庭', '博弈游戏', '传话筒迷宫']
        selected_stage = st.selectbox(
            "选择当前的交互舞台", 
            stage_options, 
            index=stage_options.index(st.session_state.current_stage_type) if st.session_state.current_stage_type in stage_options else 0,
            key="stage_selection_ui"
        )
        st.session_state.current_stage_type = selected_stage

        if st.button("🏟️ 构建世界观 (Generate Bible)", use_container_width=True, type="primary"):
            if st.session_state.scenario_df.empty:
                st.warning("请先在导演面板生成剧本时间线")
            else:
                director = Director(client, model_name)
                with st.spinner("正在同步世界观与群名..."):
                    bible = director.generate_world_bible(
                        st.session_state.scenario_theme, 
                        st.session_state.scenario_df, 
                        selected_stage
                    )
                    st.session_state.world_bible = bible
                    st.success("世界观与群名已同步！")

    with col2:
        if st.session_state.world_bible:
            with st.container(border=True):
                st.markdown(f"**🏷️ 房间/群名**: {st.session_state.world_bible.get('group_name')}")
                st.markdown(f"**📖 世界观设定**: {st.session_state.world_bible.get('world_bible')}")
        else:
            st.info("点击左侧按钮生成共享世界观。")

    st.divider()
    st.subheader("🎭 阶段二：选角审核与讲戏 (Casting Review & Persona)")
    
    if "casting_data" in st.session_state and st.session_state.casting_data:
        st.info("🧠 导演已完成初步选角。您可以微调角色和简介，然后点击生成详细人设。")
        
        edited_casting = st.data_editor(
            st.session_state.casting_data,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Model ID": st.column_config.TextColumn("演员模型", disabled=True),
                "Role": st.column_config.TextColumn("角色名", required=True),
                "Nickname": st.column_config.TextColumn("群昵称", required=True),
                "Brief": st.column_config.TextColumn("角色简介", width="large")
            },
            key="casting_editor_v2"
        )
        st.session_state.casting_data = edited_casting

        c1, c2 = st.columns([1, 3])
        if c1.button("🎬 确认并生成详细人设", type="primary"):
            director = Director(client, model_name)
            with st.status("🎬 导演正在分别为演员讲戏...", expanded=True) as status:
                all_nicknames = [r["Nickname"] for r in edited_casting]
                
                for row in edited_casting:
                    mid = row["Model ID"]
                    status.write(f"正在为 {mid} ({row['Role']}) 构思...")
                    
                    persona = director._caster.generate_persona(
                        mid, row, 
                        st.session_state.scenario_theme,
                        st.session_state.world_bible,
                        st.session_state.current_stage_type,
                        all_nicknames
                    )
                    
                    st.session_state.custom_prompts[mid] = persona.get("system_prompt", "")
                    st.session_state.custom_memories[mid] = "\n".join(persona.get("initial_memories", []))
                    st.session_state.nicknames[mid] = row["Nickname"]
                
                st.session_state.prompt_version += 1
                status.update(label="🎉 所有演员已就绪！", state="complete")
                st.rerun()
    else:
        st.info("请先在【AI 导演】面板完成智能选角。")

    # 3. Persona Preview (Optional Expanders)
    if st.session_state.custom_prompts:
        with st.expander("🔍 查看已生成的人设详情", expanded=False):
            for mid, prompt in st.session_state.custom_prompts.items():
                st.markdown(f"**{mid}** (昵称: {st.session_state.nicknames.get(mid, mid)})")
                st.caption("System Prompt")
                st.text_area(f"Prompt_{mid}", value=prompt, height=150, key=f"preview_prompt_{mid}")
                st.caption("Memories")
                st.text_area(f"Mem_{mid}", value=st.session_state.custom_memories.get(mid, ""), height=100, key=f"preview_mem_{mid}")
                st.divider()
