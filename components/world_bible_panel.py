import streamlit as st
import pandas as pd
from core.director import Director
from core.state.manager import state_manager

def render_world_bible_panel(client, model_name):
    """
    Renders World Bible Generation and Enhanced Flexible Casting Review.
    """
    # --- AUTOMATION: Auto-generate World Bible if empty but script exists ---
    if not st.session_state.world_bible and not st.session_state.scenario_df.empty:
        with st.spinner("🌟 导演正在根据剧本构思世界观基本法..."):
            director = Director(client, model_name)
            bible = director.generate_world_bible(
                st.session_state.scenario_theme, 
                st.session_state.scenario_df, 
                st.session_state.current_stage_type
            )
            st.session_state.world_bible = bible
            st.success("✨ 世界观基本法已自动同步！")
            st.rerun()

    st.subheader("🌍 阶段一：世界观设定 (World Bible)")
    
    # === [NEW] Load Project Snapshot ===
    with st.expander("📂 读取工程存档 (Load Project)", expanded=False):
        presets = state_manager.db.get_presets("project_snapshot")
        if not presets:
            st.caption("暂无存档。请先配置并保存一个项目。")
        else:
            c_load1, c_load2 = st.columns([3, 1])
            selected_pid = c_load1.selectbox("选择存档", presets, format_func=lambda x: f"{x['name']} ({x['created_at']})", key="load_proj_sel")
            if c_load2.button("📥 读取"):
                full_data = state_manager.db.get_preset_by_id(selected_pid["id"])
                if full_data and "content" in full_data:
                    content = full_data["content"]
                    # Restore Session State
                    st.session_state.scenario_theme = content.get("theme", "")
                    st.session_state.current_stage_type = content.get("stage_type", "聊天群聊")
                    st.session_state.world_bible = content.get("world_bible", {})
                    st.session_state.casting_data = content.get("casting_data", [])
                    st.session_state.actor_personas = content.get("actor_personas", {})
                    
                    # Restore DataFrame
                    import json
                    if "scenario_df_json" in content:
                        st.session_state.scenario_df = pd.read_json(content["scenario_df_json"])
                    
                    # Restore Legacy keys for compatibility
                    st.session_state.custom_prompts = {}
                    st.session_state.custom_memories = {}
                    st.session_state.nicknames = {}
                    for aid, p in st.session_state.actor_personas.items():
                        mid = p.get("model_id")
                        if mid:
                            st.session_state.custom_prompts[mid] = p.get("system_prompt", "")
                            st.session_state.custom_memories[mid] = "\n".join(p.get("initial_memories", []))
                            st.session_state.nicknames[mid] = p.get("nickname", "")
                    
                    st.success(f"✅ 已读取存档：{full_data['name']}")
                    st.rerun()

    if st.session_state.world_bible:
        with st.container(border=True):
            st.markdown(f"**🏷️ 房间/群名**: {st.session_state.world_bible.get('group_name')}")
            st.markdown(f"**📖 世界观设定**: {st.session_state.world_bible.get('world_bible')}")
            
            # Allow manual refresh if needed
            if st.button("🔄 重新同步世界观", use_container_width=False):
                st.session_state.world_bible = {}
                st.rerun()
    else:
        st.info("导演正在等待剧本生成以同步世界观。")

    st.divider()
    st.subheader("🎭 阶段二：灵活选角工作台 (Flexible Casting)")
    
    # Debugging: show raw state if empty but user thinks it should be there
    if not st.session_state.casting_data:
        st.info("请先在【AI 导演】面板完成智能选角建议。")
        if st.session_state.scenario_df.empty:
            st.caption("⚠️ 尚未生成剧本时间线，导演无法建议角色。")
        return

    st.info("🧠 导演已根据剧本建议了以下角色及其表演形式。请为 AI 角色分配模型，并配置脚本规则。")
    
    # We'll use a container and manual rendering instead of data_editor for complex per-row inputs
    # Use a copy to iterate while modifying
    for i, role in enumerate(st.session_state.casting_data):
        with st.container(border=True):
            # Layout: Delete | Info | Source | Assignment
            c_del, c1, c2, c3 = st.columns([0.5, 2, 2.5, 2])
            
            with c_del:
                st.write("") # Spacer
                if st.button("🗑️", key=f"del_role_{i}", help="删除该角色建議"):
                    st.session_state.casting_data.pop(i)
                    st.rerun()

            with c1:
                st.markdown(f"**{role['role']}** ({role['nickname']})")
                st.caption(role['brief'])
            
            with c2:
                # Performer Source Selection
                source_key = f"source_{i}_{role['role']}"
                source_options = ["🤖 AI 代言", "📜 脚本机器人", "👤 真人客串"]
                
                # Determine index based on source_type
                current_idx = 0
                stype = role.get("source_type", "AI")
                if stype == "AI": current_idx = 0
                elif stype == "Script": current_idx = 1
                elif stype == "User": current_idx = 2
                
                selected_source = st.selectbox("表演来源", source_options, index=current_idx, key=source_key)
                role["source_type_ui"] = selected_source # Sync back
            
            with c3:
                # Dynamic Assignment UI based on Source
                if "🤖 AI" in selected_source:
                    model_key = f"model_assign_{i}"
                    all_models = [c["name"] for c in st.session_state.llm_configs]
                    if not all_models:
                        st.warning("请先配置服务商")
                        assigned_model = None
                    else:
                        assigned_model = st.selectbox("分配模型", all_models, key=model_key)
                    role["assigned_model"] = assigned_model
                    
                elif "📜 脚本机器人" in selected_source:
                    with st.popover("⚙️ 配置脚本逻辑", use_container_width=True):
                        st.markdown("##### 🤖 傻瓜式脚本配置")
                        st.caption("设置该角色在何时说出何种固定话语。")
                        
                        # Load existing or empty
                        current_conf = role.get("script_config", {})
                        
                        trigger_type = st.radio("触发类型", ["定时发送", "关键词触发", "特定场景"], 
                                              index=["定时发送", "关键词触发", "特定场景"].index(current_conf.get("type", "定时发送")) if current_conf.get("type") in ["定时发送", "关键词触发", "特定场景"] else 0,
                                              key=f"trig_type_{i}")
                        trigger_val = st.text_input("触发条件", value=current_conf.get("condition", ""), placeholder="例如：10:00 或 听到'你好'", key=f"trig_val_{i}")
                        script_text = st.text_area("发送文本", value=current_conf.get("text", ""), placeholder="输入角色要说的话...", key=f"trig_text_{i}")
                        
                        role["script_config"] = {"type": trigger_type, "condition": trigger_val, "text": script_text}
                        if st.button("确定保存", key=f"save_script_{i}"):
                            st.success("脚本逻辑已锁定")
                
                elif "👤 真人客串" in selected_source:
                    participation_type = st.radio("参与方式", ["深度扮演 (参与主线)", "客串 (路人观察)"], 
                                                 index=0 if st.session_state.get("user_deep_participation", False) else 1,
                                                 key=f"user_type_{i}")
                    st.caption("📍 该角色将由您在舞台页亲自发送消息。")
                    role["user_participation_type"] = participation_type

    # Add Custom Role Button
    with st.expander("➕ 添加自定义角色", expanded=False):
        with st.form("add_role_form"):
            c_new1, c_new2, c_new3 = st.columns(3)
            new_role = c_new1.text_input("角色名", placeholder="例如：神秘人")
            new_nick = c_new2.text_input("群昵称", placeholder="例如：X")
            new_brief = c_new3.text_input("简介", placeholder="例如：突然闯入的不速之客")
            
            if st.form_submit_button("添加角色"):
                if new_role and new_nick:
                    st.session_state.casting_data.append({
                        "role": new_role,
                        "nickname": new_nick,
                        "brief": new_brief,
                        "source_type": "AI" # Default
                    })
                    st.rerun()
                else:
                    st.warning("角色名和昵称不能为空")

    # Global Actions
    st.write("")
    ga1, ga2 = st.columns([1, 3])
    if ga1.button("🎬 确认分配并讲戏", type="primary", use_container_width=True):
        director = Director(client, model_name)
        with st.status("🎬 导演正在分别为演员讲戏...", expanded=True) as status:
            all_nicknames = [r["nickname"] for r in st.session_state.casting_data]
            
            for i, row in enumerate(st.session_state.casting_data):
                # 生成唯一角色ID
                actor_id = f"{row.get('role', 'Actor')}_{i}"
                
                # Only AI sources need detailed persona generation
                if "🤖 AI" in row.get("source_type_ui", "AI"):
                    mid = row.get("assigned_model")
                    if not mid: continue
                    
                    status.write(f"正在为 {mid} ({row['role']}) 构思...")
                    persona = director._caster.generate_persona(
                        mid, row, 
                        st.session_state.scenario_theme,
                        st.session_state.world_bible,
                        st.session_state.current_stage_type,
                        all_nicknames
                    )
                    
                    # === 新数据结构：以角色为中心 ===
                    st.session_state.actor_personas[actor_id] = {
                        "model_id": mid,
                        "role_name": row.get("role", ""),
                        "nickname": row.get("nickname", ""),
                        "brief": row.get("brief", ""),
                        "source_type": "AI",
                        "system_prompt": persona.get("system_prompt", ""),
                        "initial_memories": persona.get("initial_memories", [])
                    }
                    
                    # === 旧数据结构：向后兼容（最后一个同模型的角色会覆盖前面的） ===
                    st.session_state.custom_prompts[mid] = persona.get("system_prompt", "")
                    st.session_state.custom_memories[mid] = "\n".join(persona.get("initial_memories", []))
                    st.session_state.nicknames[mid] = row["nickname"]
                
                elif "📜 脚本机器人" in row.get("source_type_ui", ""):
                    # Auto-generate script config if missing
                    script_conf = row.get("script_config")
                    if not script_conf or not script_conf.get("text"):
                         status.write(f"正在配置脚本机器人 {row['role']}...")
                         script_conf = director._caster.generate_script_config(
                            row,
                            st.session_state.scenario_theme,
                            st.session_state.world_bible
                         )
                         row["script_config"] = script_conf # Save back

                    # 脚本机器人也记录到新结构
                    st.session_state.actor_personas[actor_id] = {
                        "model_id": None,
                        "role_name": row.get("role", ""),
                        "nickname": row.get("nickname", ""),
                        "brief": row.get("brief", ""),
                        "source_type": "Script",
                        "script_config": script_conf
                    }
                
                elif "👤 真人客串" in row.get("source_type_ui", ""):
                    # 真人客串也记录
                    st.session_state.actor_personas[actor_id] = {
                        "model_id": None,
                        "role_name": row.get("role", ""),
                        "nickname": row.get("nickname", ""),
                        "brief": row.get("brief", ""),
                        "source_type": "User",
                        "participation_type": row.get("user_participation_type", "")
                    }
                    st.session_state.nicknames["User"] = row["nickname"]
            
            st.session_state.prompt_version += 1
            status.update(label="🎉 演员阵型已就绪！", state="complete")
            st.rerun()
    
    # ========================================================================================
    # 🎭 阶段三：演员人设详情展示与编辑 (Actor Personas Detail)
    # ========================================================================================
    st.divider()
    st.subheader("🎭 阶段三：演员人设详情 (Actor Personas)")
    
    # 只在生成完成后显示（至少要有角色分配数据）
    if not st.session_state.casting_data:
        st.info("演员人设尚未生成。请先完成上方的【灵活选角工作台】并点击'确认分配并讲戏'。")
        return
    
    st.success("✨ 导演已为每位演员量身定制了人设与背景故事。您可以在下方查看和编辑。")
    st.caption("💡 **提示**：修改后的内容会自动保存到数据库。")
    
    # 定义更新函数 - 同步到 session_state 和数据库
    def update_actor_prompt(actor_id: str, key: str):
        """更新演员的系统提示词"""
        new_value = st.session_state.get(key, "")
        
        # 更新新数据结构
        if actor_id in st.session_state.actor_personas:
            st.session_state.actor_personas[actor_id]["system_prompt"] = new_value
            
            # 同时更新旧数据结构（向后兼容）
            model_id = st.session_state.actor_personas[actor_id].get("model_id")
            if model_id:
                st.session_state.custom_prompts[model_id] = new_value
        
        # 同步到数据库 (如果有活动的 performance)
        perf = state_manager.db.get_latest_performance()
        if perf and actor_id in st.session_state.actor_personas:
            persona_data = st.session_state.actor_personas[actor_id]
            persona = {
                "system_prompt": new_value,
                "role": persona_data.get("role_name", "Unknown"),
                "nickname": persona_data.get("nickname", "")
            }
            memories = persona_data.get("initial_memories", [])
            if isinstance(memories, str):
                memories = memories.split("\n")
            state_manager.db.save_actor_state(perf["id"], actor_id, persona, memories)
    
    def update_actor_memories(actor_id: str, key: str):
        """更新演员的初始记忆"""
        new_value = st.session_state.get(key, "")
        memories_list = new_value.split("\n") if new_value else []
        
        # 更新新数据结构
        if actor_id in st.session_state.actor_personas:
            st.session_state.actor_personas[actor_id]["initial_memories"] = memories_list
            
            # 同时更新旧数据结构（向后兼容）
            model_id = st.session_state.actor_personas[actor_id].get("model_id")
            if model_id:
                st.session_state.custom_memories[model_id] = new_value
        
        # 同步到数据库
        perf = state_manager.db.get_latest_performance()
        if perf and actor_id in st.session_state.actor_personas:
            persona_data = st.session_state.actor_personas[actor_id]
            persona = {
                "system_prompt": persona_data.get("system_prompt", ""),
                "role": persona_data.get("role_name", "Unknown"),
                "nickname": persona_data.get("nickname", "")
            }
            state_manager.db.save_actor_state(perf["id"], actor_id, persona, memories_list)
    
    # 为每个演员创建可折叠卡片
    current_ver = st.session_state.prompt_version
    
    # 遍历所有角色（包括AI、脚本机器人、真人客串）
    for i, role in enumerate(st.session_state.casting_data):
        source_type = role.get("source_type_ui", "🤖 AI 代言")
        role_name = role.get("role", "未命名角色")
        nickname = role.get("nickname", role_name)
        brief = role.get("brief", "")
        
        # 生成唯一角色ID（与生成时保持一致）
        actor_id = f"{role_name}_{i}"
        
        # 构建展示标题
        if "🤖 AI" in source_type:
            model_id = role.get("assigned_model", "N/A")
            title = f"🤖 {model_id} - {role_name} ({nickname})"
            icon = "🤖"
        elif "📜 脚本机器人" in source_type:
            title = f"📜 脚本机器人 - {role_name} ({nickname})"
            icon = "📜"
        elif "👤 真人客串" in source_type:
            title = f"👤 真人客串 - {role_name} ({nickname})"
            icon = "👤"
        else:
            title = f"⚙️ {role_name} ({nickname})"
            icon = "⚙️"
        
        with st.expander(title, expanded=(i == 0)):  # 默认展开第一个
            
            # ============ AI 演员界面 ============
            if "🤖 AI" in source_type:
                model_id = role.get("assigned_model")
                if not model_id:
                    st.warning("⚠️ 该角色尚未分配模型")
                    continue
                
                # 从新数据结构读取（如果存在），否则回退到旧结构
                if actor_id in st.session_state.actor_personas:
                    persona_data = st.session_state.actor_personas[actor_id]
                    prompt = persona_data.get("system_prompt", "")
                    memories = persona_data.get("initial_memories", [])
                    if isinstance(memories, list):
                        memories = "\n".join(memories)
                else:
                    # 回退到旧数据结构
                    prompt = st.session_state.custom_prompts.get(model_id, "")
                    memories = st.session_state.custom_memories.get(model_id, "")
                
                col1, col2 = st.columns([3, 2])
                
                with col1:
                    st.markdown("##### 📜 系统提示词 (System Prompt)")
                    prompt_key = f"edit_prompt_{i}_{actor_id}_v{current_ver}"
                    st.text_area(
                        "系统提示词",
                        value=prompt,
                        height=250,
                        key=prompt_key,
                        on_change=update_actor_prompt,
                        args=(actor_id, prompt_key),  # 使用 actor_id
                        label_visibility="collapsed",
                        help="这是AI演员的核心人格设定，包含角色背景、性格特征、行为规范等。"
                    )
                
                with col2:
                    # 显示角色元信息
                    st.markdown("##### 🎭 角色信息")
                    info_container = st.container(border=True)
                    with info_container:
                        st.markdown(f"**角色名**: {role_name}")
                        st.markdown(f"**昵称**: {nickname}")
                        st.markdown(f"**简介**: {brief}")
                        st.markdown(f"**模型**: {model_id}")
                    
                    st.write("")  # 间距
                    st.markdown("##### 🧠 初始记忆 (Initial Memories)")
                    memory_key = f"edit_memory_{i}_{actor_id}_v{current_ver}"
                    st.text_area(
                        "初始记忆",
                        value=memories,
                        height=180,
                        key=memory_key,
                        on_change=update_actor_memories,
                        args=(actor_id, memory_key),  # 使用 actor_id
                        label_visibility="collapsed",
                        help="演员的背景记忆和秘密信息，每行一条。",
                        placeholder="例如：\n我是卧底，不能告诉任何人\n我记得昨天和警长吵了一架"
                    )
            
            # ============ 脚本机器人界面 ============
            elif "📜 脚本机器人" in source_type:
                st.markdown("##### 🎭 角色信息")
                info_col1, info_col2 = st.columns([1, 1])
                with info_col1:
                    st.markdown(f"**角色名**: {role_name}")
                    st.markdown(f"**昵称**: {nickname}")
                with info_col2:
                    st.markdown(f"**简介**: {brief}")
                    st.markdown(f"**类型**: 脚本控制（非AI）")
                
                st.divider()
                st.markdown("##### 🤖 脚本逻辑配置")
                st.caption("设置该角色在何时说出何种固定话语。")
                
                # 获取或初始化脚本配置
                script_config = role.get("script_config", {})
                script_key_base = f"script_{i}_{role_name}"
                
                config_col1, config_col2 = st.columns([1, 2])
                
                with config_col1:
                    trigger_type = st.selectbox(
                        "触发类型", 
                        ["定时发送", "关键词触发", "特定场景"],
                        index=["定时发送", "关键词触发", "特定场景"].index(script_config.get("type", "定时发送")) if script_config.get("type") in ["定时发送", "关键词触发", "特定场景"] else 0,
                        key=f"{script_key_base}_type"
                    )
                    
                    trigger_val = st.text_input(
                        "触发条件", 
                        value=script_config.get("condition", ""),
                        placeholder="例如：10:00 或 听到'你好'",
                        key=f"{script_key_base}_condition",
                        help="定时：输入虚拟时间如'Day 1 10:00' | 关键词：输入关键字如'你好' | 场景：输入场景描述"
                    )
                
                with config_col2:
                    script_text = st.text_area(
                        "发送文本", 
                        value=script_config.get("text", ""),
                        placeholder="输入角色要说的话...",
                        height=120,
                        key=f"{script_key_base}_text",
                        help="该角色在触发条件满足时会自动发送此内容"
                    )
                
                # 更新配置到 casting_data
                if st.button("💾 保存脚本配置", key=f"{script_key_base}_save"):
                    role["script_config"] = {
                        "type": trigger_type,
                        "condition": st.session_state[f"{script_key_base}_condition"],
                        "text": st.session_state[f"{script_key_base}_text"]
                    }
                    st.success("✅ 脚本逻辑已保存！")
                    st.rerun()
            
            # ============ 真人客串界面 ============
            elif "👤 真人客串" in source_type:
                st.markdown("##### 🎭 角色信息")
                info_container = st.container(border=True)
                with info_container:
                    st.markdown(f"**角色名**: {role_name}")
                    st.markdown(f"**昵称**: {nickname}")
                    st.markdown(f"**简介**: {brief}")
                    st.markdown(f"**表演者**: 您（真人）")
                
                st.divider()
                st.markdown("##### 📍 客串提示")
                participation_type = role.get("user_participation_type", "客串 (路人观察)")
                
                if "深度扮演" in participation_type:
                    st.info("🎯 **深度参与模式**：您将作为核心角色参与主线剧情。请在舞台页面中积极互动，推动情节发展。")
                else:
                    st.info("👀 **客串观察模式**：您作为旁观者或次要角色参与。可以随时发言，但主线剧情不依赖您的行动。")
                
                st.caption("💡 您无需配置系统提示词或记忆，只需在舞台页面中自由发挥即可。")
    
    # 添加快捷操作按钮
    st.write("")
    action_col1, action_col2, action_col3 = st.columns([1, 1, 2])
    
    with action_col1:
        # === [NEW] Save Project Snapshot ===
        with st.popover("💾 保存工程快照", use_container_width=True):
            st.markdown("##### 保存当前所有进度")
            st.caption("将包含：剧本、世界观、所有演员人设、选角配置。下次可直接读取恢复。")
            save_name = st.text_input("存档名称", value=st.session_state.scenario_theme or "未命名项目")
            
            if st.button("确认保存", type="primary"):
                if not save_name:
                    st.warning("请输入存档名称")
                else:
                    # Bundle Data
                    snapshot = {
                        "theme": st.session_state.scenario_theme,
                        "stage_type": st.session_state.current_stage_type,
                        "world_bible": st.session_state.world_bible,
                        "casting_data": st.session_state.casting_data,
                        "actor_personas": st.session_state.actor_personas,
                        "scenario_df_json": st.session_state.scenario_df.to_json() if not st.session_state.scenario_df.empty else "{}"
                    }
                    state_manager.db.save_unique_preset("project_snapshot", save_name, snapshot)
                    st.success("✅ 工程快照已保存！")

        # Legacy Save (Optional, maybe remove if confusing? User asked for "Save Personas")
        # Let's keep a simplified version or just rely on Snapshot.
        # User said "why can't I save personas without creating performance?". Snapshot solves this.
        # But maybe they want to sync to DB for the *current* pending performance?
        # Actually initializing performance creates it. 
        # So "Save Personas" button is less useful if we use Snapshots & Auto-save on edit.
        # Let's keep it but rename/repurpose if needed, or just let Snapshot be the primary.
        # The user specifically asked to fix "can't save without performance".
        # Snapshot is the best answer.

    
    with action_col2:
        if st.button("📥 导出人设配置", use_container_width=True, help="导出为 JSON 文件"):
            import json
            export_data = {
                "theme": st.session_state.scenario_theme,
                "stage": st.session_state.current_stage_type,
                "world_bible": st.session_state.world_bible,
                "actors": {}
            }
            
            # 使用新数据结构导出
            for actor_id, persona_data in st.session_state.actor_personas.items():
                export_data["actors"][actor_id] = persona_data
            
            json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="下载 JSON",
                data=json_str,
                file_name=f"personas_{st.session_state.scenario_theme[:10]}.json",
                mime="application/json",
                use_container_width=True
            )
    
    st.divider()
    if st.button("🚀 确认并进入舞台 (Start Simulation)", type="primary", use_container_width=True):
        st.session_state.active_theater_tab = "🏟️ 舞台表演"
        st.rerun()
