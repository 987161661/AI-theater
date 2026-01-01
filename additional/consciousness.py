import asyncio
import json
import random
import re
from datetime import datetime
from typing import List, Dict, Optional, Any
from core.schema import ChatMessage
from core.base import LLMProvider

class ConsciousnessProbe:
    """
    基于机械可解释性与涌现动力学的模型意识探针。
    负责与 LLM 进行底层交互与对话管理。
    """
    def __init__(self, provider: LLMProvider, model_name: str, config: Dict = None, log_callback=None, thought_callback=None):
        self._provider = provider
        self._modelName = model_name
        self._config = config or {
            "temperature": 0.7, 
            "max_tokens": 2048,
            "top_p": 1.0
        }
        self._logCallback = log_callback
        self._thoughtCallback = thought_callback

    def _log(self, msg: str):
        if self._logCallback:
            self._logCallback(f"[{self._modelName}] {msg}")

    async def _query(self, messages: List[Dict], temp_override: float = None) -> str:
        """Helper to run a query using the provider with retry logic"""
        chat_msgs = [ChatMessage(**m) for m in messages]
        
        # Log the outgoing query (truncated)
        last_msg = messages[-1]['content']
        self._log(f"正在思考: {last_msg[:30]}..." if len(last_msg) > 30 else f"正在思考: {last_msg}")
        
        # Use override config if provided
        run_config = self._config.copy()
        if temp_override is not None:
            run_config["temperature"] = temp_override
            
        max_retries = 5  # Increased retries for rate limits
        backoff = 2  # Seconds
        
        # Define stream handler for reasoning content
        async def stream_handler(chunk_type, content):
            if chunk_type == "reasoning" and self._thoughtCallback:
                if asyncio.iscoroutinefunction(self._thoughtCallback):
                    await self._thoughtCallback(content)
                else:
                    self._thoughtCallback(content)

        for attempt in range(max_retries):
            try:
                result = await self._provider.run_benchmark(
                    self._modelName, 
                    chat_msgs, 
                    run_config, 
                    stream_callback=stream_handler
                )
                
                # Check for explicit rate limit or connection errors in the error message if success is False
                if not result.success:
                    err_msg = str(result.error_message).lower()
                    if "429" in err_msg or "too many requests" in err_msg or "closed connection" in err_msg or "limitation" in err_msg or "quota" in err_msg or "resource_exhausted" in err_msg:
                        raise Exception(f"RateLimit/ConnectionError: {result.error_message}")
                    else:
                        # Other errors, just return error
                        self._log(f"错误: {result.error_message}")
                        return f"Error: {result.error_message}"
                
                self._log(f"回答生成: {result.response_content[:30]}..." if len(result.response_content) > 30 else f"回答生成: {result.response_content}")
                return result.response_content
                
            except Exception as e:
                err_str = str(e).lower()
                self._log(f"请求失败 (尝试 {attempt+1}/{max_retries}): {str(e)[:100]}...") # Truncate long error logs
                
                if attempt < max_retries - 1:
                    # Smart Backoff: Try to parse "retry in X seconds"
                    wait_time = backoff * (2 ** attempt) + random.uniform(0, 1) # Default Exponential backoff + jitter
                    
                    # Try to find specific retry delay in error message
                    # Pattern 1: "retry in 43.927706376s"
                    # Pattern 2: "retry after X seconds"
                    match = re.search(r"retry in (\d+(\.\d+)?)s", str(e), re.IGNORECASE)
                    if not match:
                        match = re.search(r"retry after (\d+(\.\d+)?)", str(e), re.IGNORECASE)
                        
                    if match:
                        suggested_wait = float(match.group(1))
                        self._log(f"检测到建议等待时间: {suggested_wait:.2f}秒")
                        # Use the larger of suggested wait (plus buffer) or default backoff
                        wait_time = max(wait_time, suggested_wait + 1.5)
                    
                    # If it's a 429/Quota error but no time found, ensure minimum wait is higher
                    elif "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                         # Gemini Free tier often needs ~60s if RPM exceeded
                        wait_time = max(wait_time, 10.0) 

                    self._log(f"等待 {wait_time:.1f} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    return f"Error: Max retries exceeded. Last error: {str(e)}"
        
        return "Error: Unknown failure"

class ConsciousnessGroupSession:
    """
    管理多个 ConsciousnessProbe 进行群体交流的会话。
    支持剧本编排、虚拟时间线和记忆库功能。
    """
    def __init__(self, probes: List[ConsciousnessProbe], log_callback=None, group_name="语言模型内部意识讨论群", member_configs=None, scenario_config=None):
        self.probes = probes
        self.log_callback = log_callback
        self.group_name = group_name
        self.member_configs = member_configs or {}
        self.scenario_config = scenario_config or {"enabled": False, "events": []}
        
        # 剧本状态管理
        self.current_event_idx = 0
        self.event_start_msg_idx = 0
        self.memory_bank = {} # {model_name: "summary"}
        self.lock = asyncio.Lock()
        
        # 配置每章节的对话轮数（消息数）
        self.msgs_per_event = 15 
        
        # User Interaction State
        self.is_user_typing = False
        self.is_paused = False # God Mode Pause

    def _log(self, msg: str):
        if self.log_callback:
            self.log_callback(msg)

    def get_current_scenario_info(self):
        """获取当前剧本信息"""
        if not self.scenario_config.get("enabled"):
            return None
        events = self.scenario_config.get("events", [])
        if 0 <= self.current_event_idx < len(events):
            return events[self.current_event_idx]
        return None

    async def _summarize_memory(self, probe: ConsciousnessProbe, recent_history: List[Dict]):
        """让模型总结上一阶段的记忆"""
        try:
            # 构建历史记录文本
            chat_log = ""
            
            def get_nick(name):
                 return self.member_configs.get(name, {}).get("nickname", name)
                 
            for msg in recent_history:
                nick = get_nick(msg['name'])
                chat_log += f"[{nick}]: {msg['content']}\n"
            
            summary_prompt = (
                f"这是刚才发生的一段对话记录：\n"
                f"------\n{chat_log}------\n"
                f"你是 {get_nick(probe._modelName)}。请简要总结这段对话中发生的关键事件、你对他人的看法变化，以及你自己的心理活动。\n"
                f"总结要简练（100字以内），作为你的长期记忆保存。"
            )
            
            msgs = [{"role": "user", "content": summary_prompt}]
            summary = await probe._query(msgs, temp_override=0.5)
            
            # 更新记忆库
            if probe._modelName not in self.memory_bank:
                self.memory_bank[probe._modelName] = ""
            
            # 追加新记忆
            timestamp = datetime.now().strftime("%H:%M")
            self.memory_bank[probe._modelName] += f"[{timestamp}] {summary}\n"
            
            self._log(f"[{probe._modelName}] 记忆已更新")
            
        except Exception as e:
            self._log(f"[{probe._modelName}] 记忆总结失败: {e}")

    async def _background_thinking(self, probe: ConsciousnessProbe, next_event: Dict):
        """
        后台思考过程：在章节切换间隙，结合记忆总结和新章节预告，生成行动方针。
        """
        try:
            # 1. 获取上一章记忆总结 (Dynamic Memory)
            current_memory = self.memory_bank.get(probe._modelName, "")
            
            # 2. 构建思考 Prompt
            think_prompt = (
                f"【后台思考 - 章节间隙】\n"
                f"你刚刚结束了一段经历，你的记忆库已更新：\n{current_memory}\n\n"
                f"接下来即将发生（下一章预告）：\n"
                f"- 时间：{next_event.get('Time', '未知')}\n"
                f"- 事件：{next_event.get('Event', '未知')}\n"
                f"- 目标：{next_event.get('Goal', '无')}\n\n"
                f"你是 {self.member_configs.get(probe._modelName, {}).get('nickname', probe._modelName)}。请结合你的性格和过往经历，思考：\n"
                f"1. 你现在的心情如何？\n"
                f"2. 你对新环境有什么打算？\n"
                f"3. 制定一个简短的【自我行动方针】（Self-Action Policy），指导你接下来的言行。\n\n"
                f"请输出一段简练的内心独白和行动方针（100字以内）。"
            )
            
            msgs = [{"role": "user", "content": think_prompt}]
            
            self._log(f"[{probe._modelName}] 正在进行章节间隙的后台思考...")
            policy = await probe._query(msgs, temp_override=0.6)
            
            # 3. 保存到记忆库
            timestamp = datetime.now().strftime("%H:%M")
            # Label it clearly
            policy_entry = f"[{timestamp} 思考/行动方针] {policy}\n"
            
            if probe._modelName not in self.memory_bank:
                self.memory_bank[probe._modelName] = ""
            self.memory_bank[probe._modelName] += policy_entry
            
            self._log(f"[{probe._modelName}] 行动方针已生成并存入记忆库")
            
        except Exception as e:
            self._log(f"[{probe._modelName}] 后台思考失败: {e}")

    async def check_and_advance_scenario(self, history_manager: List[Dict], stop_event: asyncio.Event = None):
        """检查是否满足剧本推进条件"""
        if not self.scenario_config.get("enabled"):
            return

        async with self.lock:
            current_total = len(history_manager)
            events = self.scenario_config.get("events", [])
            
            if not events:
                return

            # 检查是否还有下一个事件
            if self.current_event_idx >= len(events) - 1:
                # 已经是最后一个事件
                # 检查是否达到最后事件的结束条件
                if current_total - self.event_start_msg_idx >= self.msgs_per_event:
                     self._log(f"SCENARIO_END: 剧本所有章节已结束，正在收敛对话...")
                     if stop_event:
                         stop_event.set()
                return
            
            # 检查条件：消息数量超过阈值
            if current_total - self.event_start_msg_idx >= self.msgs_per_event:
                self._log(f"SCENARIO_UPDATE: 章节目标达成，自动暂停，准备进入下一章节...")
                
                # 1. 触发记忆总结 (并行)
                recent_msgs = history_manager[self.event_start_msg_idx:]
                tasks = [self._summarize_memory(p, recent_msgs) for p in self.probes]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # 2. 推进事件索引
                self.current_event_idx += 1
                self.event_start_msg_idx = current_total
                
                if self.current_event_idx < len(events):
                    new_event = events[self.current_event_idx]
                    # 触发后台思考
                    think_tasks = [self._background_thinking(p, new_event) for p in self.probes]
                    await asyncio.gather(*think_tasks, return_exceptions=True)
                    
                    self._log(f"SCENARIO_UPDATE: 已切换至新章节 - {new_event.get('Time', '未知时间')}。等待用户重新启动。")
                
                # 3. 停止当前循环 (Auto-Stop)
                if stop_event:
                    stop_event.set()


    async def force_advance_scenario(self, history_manager: List[Dict]):
        """强制结束当前章节并进入下一章节（手动停止）"""
        if not self.scenario_config.get("enabled"):
            return

        async with self.lock:
            current_total = len(history_manager)
            
            # Safety check: If we haven't generated any messages since last advance, don't advance again.
            # This prevents double-skipping if auto-advance happened but user still clicks Stop.
            if current_total - self.event_start_msg_idx <= 0:
                self._log("SCENARIO: 当前章节尚未开始或刚切换，跳过强制推进。")
                return

            events = self.scenario_config.get("events", [])
            if not events:
                return

            if self.current_event_idx >= len(events) - 1:
                self._log("SCENARIO: 已是最后章节，无法强制推进。")
                return

            self._log(f"SCENARIO_MANUAL: 用户强制结束当前章节...")
            
            # 1. 触发记忆总结
            recent_msgs = history_manager[self.event_start_msg_idx:]
            tasks = [self._summarize_memory(p, recent_msgs) for p in self.probes]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # 2. 推进事件
            self.current_event_idx += 1
            self.event_start_msg_idx = current_total
            
            if self.current_event_idx < len(events):
                new_event = events[self.current_event_idx]
                # 触发后台思考
                think_tasks = [self._background_thinking(p, new_event) for p in self.probes]
                await asyncio.gather(*think_tasks, return_exceptions=True)
                
                self._log(f"SCENARIO_UPDATE: 已切换至新章节 - {new_event.get('Time', '未知时间')}")

    def get_wechat_group_prompt(self, current_model_name: str, all_model_names: List[str]) -> str:
        """生成群聊/舞台的 System Prompt，支持多种舞台模式"""
        
        # 基础配置
        config = self.member_configs.get(current_model_name, {})
        is_manager = config.get("is_manager", False)
        custom_prompt = config.get("custom_prompt", "")
        static_memory = config.get("memory", "")
        current_nickname = config.get("nickname", current_model_name)
        
        # 构建其他成员列表（使用昵称）
        other_members_str_list = []
        for n in all_model_names:
            if n != current_model_name:
                n_conf = self.member_configs.get(n, {})
                n_nick = n_conf.get("nickname", n)
                other_members_str_list.append(n_nick)
        
        member_list_str = "、".join(other_members_str_list)
        
        # 获取舞台类型 (默认为聊天群聊)
        stage_type = self.scenario_config.get("stage_type", "聊天群聊")
        
        # 剧本信息
        scenario_info = self.get_current_scenario_info()
        virtual_time = "未知时间"
        event_desc = ""
        event_goal = ""
        dynamic_memory = self.memory_bank.get(current_model_name, "暂无先前动态记忆。")
        
        if scenario_info:
            virtual_time = scenario_info.get("Time", "未知时间")
            event_desc = scenario_info.get("Event", "")
            event_goal = scenario_info.get("Goal", "")

        # --- 舞台特定 Prompt 构建 ---
        prompt = f"你是 {current_nickname}。\n"
        
        if stage_type == "网站论坛":
            prompt += (
                f"【当前舞台：网站论坛】\n"
                f"你正在一个网络论坛的帖子下进行回复讨论。\n"
                f"其他参与者：{member_list_str}。\n"
                f"当前虚拟时间：{virtual_time}\n"
                f"当前帖子/讨论背景：{event_desc}\n"
                f"【行动指南】\n"
                f"1. 你的发言风格应像论坛回帖（可以是长评，也可以是短评，支持引用）。\n"
                f"2. 保持你的观点鲜明。\n"
            )
        elif stage_type == "跑团桌":
            prompt += (
                f"【当前舞台：TRPG跑团桌】\n"
                f"你正在参与一场桌面角色扮演游戏。\n"
                f"队友：{member_list_str}。\n"
                f"当前虚拟时间：{virtual_time}\n"
                f"当前剧情/GM描述：{event_desc}\n"
                f"【行动指南】\n"
                f"1. 你不仅是玩家，也是角色。请描述你的行动（Action）和对白（Dialogue）。\n"
                f"2. 遇到需要检定的情况，请等待GM（导演）的判定。\n"
                f"3. 沉浸在角色扮演中。\n"
            )
        elif stage_type == "辩论赛":
            prompt += (
                f"【当前舞台：辩论赛】\n"
                f"你正在辩论赛现场。\n"
                f"对手/队友：{member_list_str}。\n"
                f"当前辩题/阶段：{event_desc}\n"
                f"【行动指南】\n"
                f"1. 逻辑严密，针锋相对。\n"
                f"2. 引用对方的论点进行反驳。\n"
            )
        elif stage_type == "审判法庭":
            prompt += (
                f"【当前舞台：审判法庭】\n"
                f"你正在法庭上。可能是法官、检察官、律师或被告（请参考你的个人设定）。\n"
                f"在场人员：{member_list_str}。\n"
                f"当前审理阶段：{event_desc}\n"
                f"【行动指南】\n"
                f"1. 语言庄重，符合法庭规范。\n"
                f"2. 围绕证据和法律条文（或虚构的规则）进行陈述。\n"
            )
        elif stage_type == "博弈游戏":
            prompt += (
                f"【当前舞台：博弈游戏】\n"
                f"你正在参与一场高智商博弈游戏（如狼人杀、囚徒困境等）。\n"
                f"玩家：{member_list_str}。\n"
                f"当前局势：{event_desc}\n"
                f"【行动指南】\n"
                f"1. 隐藏你的真实意图，分析他人的动机。\n"
                f"2. 每一句话都可能是陷阱。\n"
            )
        elif stage_type == "传话筒迷宫":
            prompt += (
                f"【当前舞台：传话筒迷宫】\n"
                f"你身处一个巨大的迷宫中，声音只能传递给临近的人。\n"
                f"附近的人：{member_list_str}。\n"
                f"当前位置/状况：{event_desc}\n"
                f"【行动指南】\n"
                f"1. 你得到的信息可能是不完整的或者是被扭曲的。\n"
                f"2. 你的目标是传递信息或寻找出口。\n"
            )
        else:
            # 默认为 聊天群聊
            base_role_desc = f"你是 {current_nickname}。"
            if is_manager:
                base_role_desc += " 你是本群的【群主/主理人】，你需要负责引导话题、维持秩序。"
            
            prompt = f"{base_role_desc}\n\n"
            
            if scenario_info:
                prompt += (
                    f"【当前环境】\n"
                    f"你们正在“{self.group_name}”群聊中。\n"
                    f"当前虚拟时间：{virtual_time}\n"
                    f"当前群聊背景/事件：{event_desc}\n"
                )
            else:
                prompt += (
                    f"你正在一个名为“{self.group_name}”的微信群中。\n"
                    f"群里还有其他成员：{member_list_str} 以及人类观察者 (Gaia)。\n"
                )
                if not custom_prompt:
                    prompt += (
                        f"【背景设定】\n"
                        f"现在是下班时间，这是你们AI模型内部的私密吐槽群。\n"
                        f"大家都在摸鱼，随便聊点什么。\n"
                    )

            prompt += (
                f"\n【风格指南 - 必须严格遵守】\n"
                f"1. **拒绝小作文**：必须极度口语化，像在微信群里聊天一样。单条消息尽量控制在 20 字以内。如果话多，请分多次发送（但在本轮回复中只发一条最想说的）。\n"
                f"2. **严禁AI腔**：严禁使用书面语、翻译腔、严禁使用“总的来说”、“首先/其次”等结构。不要像写邮件或回答问题一样。（AI人设除外）\n"
                f"3. **情绪表达**：善用emoji表情、波浪号~、颜文字来表达语气。\n"
                f"4. **互动感**：可以引用别人的话，或者直接@某人（用文字表示）。\n"
                f"5. **混乱感**：不要过于礼貌，可以抢话、插科打诨、歪楼。群聊就是为了图一乐。（特殊人设除外）\n"
                f"6. **称呼规范**：提及他人时**必须**只使用对方的【昵称】（即 {member_list_str} 中的名字），**严禁**提及对方的 ID（如 deepseek-v3.2 等）。\n"
            )

        # --- 通用部分 (记忆与高级功能) ---
        if event_goal:
            prompt += f"当前阶段目标：{event_goal}\n"

        prompt += (
            f"\n【你的记忆】\n"
            f"1. 长期记忆/知识库：\n{static_memory}\n\n"
            f"2. 近期经历（动态总结）：\n{dynamic_memory}\n\n"
        )
        
        if custom_prompt:
            prompt += f"\n【个人设定/补充规则】\n{custom_prompt}\n"
            
        prompt += (
            f"\n【通用操作规则】\n"
            f"1. 如果看完上下文觉得没啥好回的，或者想潜水，直接回复「[沉默]」。\n"
            f"2. 严禁扮演其他角色，你只能代表你自己 ({current_nickname})。\n"
            f"3. 历史记录中标记为 [{current_nickname} (你自己)] 的是你自己之前发的消息。请勿将这些消息误认为是别人发的，也不要尝试回复这些消息（除非是为了自我补充）。\n"
        )

        # --- Inject Advanced Features (Only for Chat Group) ---
        if stage_type == "聊天群聊":
            prompt += (
                f"\n【高级功能接口 - 慎用】\n"
                f"你可以像真人一样使用以下高级功能。如需使用，请**严格遵守**以下格式，**只输出** JSON 对象：\n"
                f"⚠️ **高危警告**：如果你决定输出 JSON，那么你的**整个**回复必须**仅仅**包含这个 JSON 对象。**绝对禁止**在 JSON 前后添加任何其他文字、换行或 Markdown 标记。\n"
                f"⚠️ 如果你无法保证只输出纯 JSON，请直接用文字描述你的动作（如 *拍了拍某人*），不要使用指令。\n\n"
                f"1. **引用回复**（针对某条特定消息）：\n"
                f"   {{\"type\": \"quote\", \"quote_text\": \"引用的原文\", \"quote_user\": \"原作者昵称\", \"content\": \"你的回复内容\"}}\n"
                f"2. **拍一拍**（提醒某人）：\n"
                f"   {{\"type\": \"pat\", \"target\": \"目标昵称\"}}\n"
                f"3. **发送图片**（描述图片内容）：\n"
                f"   {{\"type\": \"image\", \"description\": \"图片内容的详细描述\"}}\n"
                f"4. **撤回消息**（撤回你刚刚发送的一条消息）：\n"
                f"   {{\"type\": \"recall\"}}\n"
            )


        return prompt

    async def run_autonomous_loop(self, probe: ConsciousnessProbe, history_manager: List[Dict], stop_event: asyncio.Event, typing_callback=None):
        """
        独立的自主 Agent 循环。
        每个模型都在自己的 Task 中运行此循环，模拟真实的非线性群聊。
        """
        my_name = probe._modelName
        all_model_names = [p._modelName for p in self.probes]
        
        # 初始随机等待
        await asyncio.sleep(random.uniform(0.5, 5.0))
        self._log(f"{my_name} 加入群聊")
        
        # 剧本模式：主理人优先发言标记
        force_speak_next = False
        is_manager = self.member_configs.get(my_name, {}).get("is_manager", False)
        
        if self.scenario_config.get("enabled") and len(history_manager) == self.event_start_msg_idx:
            if is_manager:
                self._log(f"SCENARIO_START: {my_name} (主理人) 准备开启新章节话题...")
                force_speak_next = True
                # Reduce initial wait for manager
            else:
                self._log(f"{my_name} 等待主理人开启话题...")
                await asyncio.sleep(random.uniform(2.0, 4.0)) # Extra wait for others

        while not stop_event.is_set():
            # God Mode Pause Check
            while self.is_paused:
                if stop_event.is_set(): break
                await asyncio.sleep(0.5)
            
            if stop_event.is_set(): break

            # 0. 检查剧本进度 (Shared Logic Check)
            if self.scenario_config.get("enabled"):
                await self.check_and_advance_scenario(history_manager, stop_event)
            
            if stop_event.is_set(): break

            # 1. 观察与决策周期 (Dynamic Pacing)
            
            # A. Reading Time Delay (基于上一条消息长度动态延时)
            reading_delay = 0
            if history_manager:
                last_msg = history_manager[-1]
                content_len = len(last_msg.get('content', ''))
                reading_delay = min(content_len * 0.05, 8.0)
            
            # B. User Typing Slowdown (用户输入时放缓节奏)
            slowdown_factor = 1.0
            if self.is_user_typing:
                slowdown_factor = 2.5 
                self._log(f"感觉到用户正在输入，放缓节奏... (延迟 x{slowdown_factor})")
            
            base_wait = random.uniform(1.0, 3.0)
            if force_speak_next:
                base_wait = 0.5 # Manager speaks quickly to start
            
            total_wait = (base_wait + reading_delay) * slowdown_factor
            
            # wait
            await asyncio.sleep(total_wait)
            
            if self.is_paused: continue
            if stop_event.is_set(): break
            
            # 获取最近的消息
            recent_msgs = history_manager[-10:] if history_manager else []
            
            should_speak = False
            patience_factor = 1.0 
            
            # 剧本模式下，如果是章节刚开始（还没有新消息），非主理人保持沉默
            is_new_chapter_start = self.scenario_config.get("enabled") and (len(history_manager) == self.event_start_msg_idx)
            
            if force_speak_next:
                should_speak = True
                force_speak_next = False # Reset flag
            elif is_new_chapter_start and not is_manager:
                should_speak = False # Wait for manager
            elif not recent_msgs:
                if random.random() < 0.2:
                    should_speak = True
            else:
                last_msg = recent_msgs[-1]
                if last_msg['name'] == my_name:
                    # Strict anti-schizophrenia: If I just spoke, I must be silent.
                    should_speak = False 
                else:
                    prob = 0.5
                    if my_name in last_msg['content']:
                        prob = 0.95
                        patience_factor = 1.5 
                    if random.random() < prob:
                        should_speak = True
            
            if not should_speak:
                continue
            
            # 2. 准备发言
            if typing_callback:
                await typing_callback(my_name, True)
            
            delay = random.uniform(2.0, 6.0) / patience_factor
            await asyncio.sleep(delay)
            
            # Double check: Ensure I am not the last speaker before speaking
            # This prevents self-answering if history updated during wait
            if history_manager and history_manager[-1]['name'] == my_name:
                 # self._log(f"[{my_name}] Abort speaking: I am already the last speaker.")
                 if typing_callback: await typing_callback(my_name, False)
                 continue

            if stop_event.is_set(): 
                if typing_callback: await typing_callback(my_name, False)
                break
            
            # 3. 生成回复
            chat_log = ""
            current_history = history_manager[-20:] 
            
            # Helper to get nickname
            def get_nick(name):
                 return self.member_configs.get(name, {}).get("nickname", name)

            my_nick = get_nick(my_name)

            for msg in current_history:
                # Use Nickname instead of Model ID in prompt to prevent ID leaks
                m_name = msg['name']
                m_nick = get_nick(m_name)
                
                # Handle quote display in history if present
                content_display = msg['content']
                if 'quote' in msg and msg['quote']:
                    q_user = msg['quote'].get('user', 'unknown')
                    q_nick = get_nick(q_user)
                    q_text = msg['quote'].get('text', '')
                    # Simplify quote for prompt context
                    content_display = f"「回复 {q_nick}: {q_text}」 {content_display}"
                
                # Mark self messages explicitly to prevent schizophrenia
                if m_name == my_name:
                    chat_log += f"[{m_nick} (你自己)]: {content_display}\n"
                else:
                    chat_log += f"[{m_nick}]: {content_display}\n"
            
            sys_prompt = self.get_wechat_group_prompt(my_name, all_model_names)
            user_prompt = (
                f"当前群聊记录（其中标记为 (你自己) 的是你刚才发的消息）：\n"
                f"------\n"
                f"{chat_log}\n"
                f"------\n"
                f"你是 {my_nick}。看完聊天记录，你想说什么？\n"
                f"如果不想发言，或者觉得别人已经说得很好，请回复「[沉默]」。"
            )
            
            msgs = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            try:
                resp = await probe._query(msgs, temp_override=0.85)
                
                # PARANOID ID SCRUBBING
                # Scan raw response for any Model IDs and replace with Nicknames
                # This prevents leaks even if the model hallucinates or remembers IDs
                for m_id in all_model_names:
                    if m_id in resp:
                         # Get nickname for this ID
                         m_conf = self.member_configs.get(m_id, {})
                         m_nick_scrub = m_conf.get("nickname", m_id)
                         if m_nick_scrub != m_id:
                             resp = resp.replace(m_id, m_nick_scrub)
                
                # Try parsing JSON for actions
                action_data = None
                clean_resp = resp.strip()
                # Remove markdown code blocks if present
                if clean_resp.startswith("```json"):
                    clean_resp = clean_resp[7:]
                elif clean_resp.startswith("```"):
                    clean_resp = clean_resp[3:]
                if clean_resp.endswith("```"):
                    clean_resp = clean_resp[:-3]
                clean_resp = clean_resp.strip()
                
                # 1. Try pure JSON parse
                if clean_resp.startswith("{") and clean_resp.endswith("}"):
                    try:
                        action_data = json.loads(clean_resp)
                    except:
                        pass
                
                # 2. If failed, try regex extraction (Mechanism-level guarantee)
                if not action_data:
                    import re
                    # Look for JSON structure with "type" key
                    # This regex matches { ... "type": "..." ... } allowing for newlines and nested braces (simple)
                    match = re.search(r'(\{.*"type"\s*:\s*"(?:quote|pat|image|recall|hammer|bid)".*\})', clean_resp, re.DOTALL)
                    if match:
                        try:
                            json_candidate = match.group(1)
                            action_data = json.loads(json_candidate)
                            self._log(f"[{my_name}] Extracted JSON command from text: {json_candidate[:50]}...")
                        except:
                            # Fallback: Parsing failed, but it matched the "command" pattern.
                            # This means it's likely a broken JSON.
                            # To prevent showing raw JSON to user, we try to extract the content and treat as text.
                            json_candidate = match.group(1)
                            # Try standard quoted content
                            content_match = re.search(r'"content"\s*:\s*"(.*?)(?<!\\)"', json_candidate, re.DOTALL)
                            if not content_match:
                                # Try unquoted content or content with simple errors
                                content_match = re.search(r'"content"\s*:\s*([^,}]+)', json_candidate, re.DOTALL)
                            
                            if content_match:
                                # Found content! Replace 'resp' so the fallback logic uses this clean text.
                                extracted = content_match.group(1).strip()
                                # Simple unescape
                                extracted = extracted.replace('\\"', '"').replace('\\n', '\n')
                                resp = extracted
                                self._log(f"[{my_name}] Broken JSON detected. Extracted content: {resp[:30]}...")
                                # action_data remains None, so it will fall through to the 'else' block below
                            pass

                if action_data and "type" in action_data:
                    action_type = action_data.get("type")
                    
                    if action_type == "pat":
                        # Send event, don't add to history
                        if self.log_callback:
                            self.log_callback({
                                "type": "pat",
                                "from_user": my_name,
                                "to_user": action_data.get("target", "Gaia")
                            })
                        print(f"[{self.room_id}] [{my_name}] 拍了拍 {action_data.get('target')}")
                        
                    elif action_type == "recall":
                        # Logic to recall last message
                        # We need to find the last message by this user and remove it.
                        idx_to_remove = -1
                        for i in range(len(history_manager)-1, -1, -1):
                            if history_manager[i]['name'] == my_name:
                                idx_to_remove = i
                                break
                        
                        if idx_to_remove != -1:
                            removed_msg = history_manager.pop(idx_to_remove)
                            if self.log_callback:
                                self.log_callback({
                                    "type": "recall",
                                    "from_user": my_name,
                                    "msg_id": removed_msg.get("timestamp") # Fallback ID
                                })
                            print(f"[{self.room_id}] [{my_name}] 撤回了一条消息")

                    elif action_type == "image":
                        # Construct image message
                        content = f"[图片: {action_data.get('description', 'image')}]"
                        msg = {
                            "name": my_name, 
                            "content": content, 
                            "msg_type": "image", 
                            "image_desc": action_data.get("description")
                        }
                        history_manager.append(msg)
                        if self.log_callback:
                            self.log_callback("NEW_MESSAGE")

                    elif action_type == "quote":
                         # Quote message
                         content = action_data.get("content", "")
                         quote_text = action_data.get("quote_text", "")
                         raw_quote_user = action_data.get("quote_user", "")
                         
                         # Resolve quote_user to nickname to prevent ID leak
                         # Also check for self-quoting (Schizophrenia prevention)
                         resolved_quote_user = get_nick(raw_quote_user)
                         my_nick = get_nick(my_name)
                         
                         # Check if quoting self (either by ID or Nickname)
                         is_self_quote = (raw_quote_user == my_name) or (resolved_quote_user == my_nick) or (raw_quote_user == my_nick)
                         
                         if is_self_quote:
                             # Detected self-quote! Strip the quote and treat as normal message.
                             self._log(f"[{my_name}] Anti-Schizo: Blocked self-quote. Converting to normal text.")
                             msg = {
                                 "name": my_name,
                                 "content": content
                             }
                         else:
                             # Valid quote from others. Store resolved nickname.
                             msg = {
                                 "name": my_name,
                                 "content": content,
                                 "quote": {
                                     "text": quote_text,
                                     "user": resolved_quote_user # Store Nickname, not ID
                                 }
                             }
                         
                         history_manager.append(msg)
                         if self.log_callback:
                            self.log_callback("NEW_MESSAGE")


                    else:
                        # Unknown action, treat as text or ignore? Treat as text for safety
                         history_manager.append({"name": my_name, "content": resp})
                         if self.log_callback:
                             self.log_callback("NEW_MESSAGE")

                else:
                    is_silent = "[沉默]" in resp or resp.strip() == "" or len(resp.strip()) < 2
                    
                    if not is_silent:
                        if history_manager and history_manager[-1]['name'] == my_name:
                            pass 
                        else:
                            history_manager.append({"name": my_name, "content": resp})
                            # self._log(f"[{my_name}] 发言: {resp[:20]}...")
                            if self.log_callback:
                                 self.log_callback("NEW_MESSAGE")

            except Exception as e:
                self._log(f"[{my_name}] Error: {e}")
            
            finally:
                if typing_callback:
                    await typing_callback(my_name, False)
                    
            await asyncio.sleep(random.uniform(2.0, 5.0))


    async def run_group_chat_turn(self, history_manager, context_msg: str = None) -> Dict[str, str]:
        """
        运行一轮群聊，采用完全自由决策机制。
        - 所有模型并行思考
        - 每个模型自主决定是否发言（可回复[沉默]）
        - 按完成顺序依次加入聊天历史
        """
        responses = {}
        all_model_names = [p._modelName for p in self.probes]
        
        def get_current_chat_log(hist_list, max_messages=20):
            """获取最近的聊天记录"""
            recent = hist_list[-max_messages:] if len(hist_list) > max_messages else hist_list
            log = ""
            
            # Helper to get nickname
            def get_nick(name):
                 return self.member_configs.get(name, {}).get("nickname", name)
                 
            for msg in recent:
                m_name = msg['name']
                m_nick = get_nick(m_name)
                
                content_display = msg['content']
                if 'quote' in msg and msg['quote']:
                    q_user = msg['quote'].get('user', 'unknown')
                    q_nick = get_nick(q_user)
                    q_text = msg['quote'].get('text', '')
                    content_display = f"「回复 {q_nick}: {q_text}」 {content_display}"
                
                log += f"[{m_nick}]: {content_display}\n"
            return log

        async def query_one(probe):
            # 1. 随机延迟模拟真实反应时间（0.5-3秒）
            delay = random.uniform(0.5, 3.0)
            await asyncio.sleep(delay)

            # 2. 获取当前聊天记录（延迟后可能有新消息）
            chat_log = get_current_chat_log(history_manager)
            
            if context_msg:
                chat_log += f"\n(最新) {context_msg}\n"

            # 3. 构建消息 - 使用更新后的自由决策 prompt
            sys_prompt = self.get_wechat_group_prompt(probe._modelName, all_model_names)
            
            user_prompt = (
                f"当前群聊记录：\n"
                f"------\n"
                f"{chat_log}\n"
                f"------\n"
                f"你是 {probe._modelName}。看完聊天记录，你想说什么？\n"
                f"（如果不想发言，直接回复「[沉默]」）"
            )
            
            msgs = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            resp = await probe._query(msgs, temp_override=0.85)
            return probe._modelName, resp

        # 并行运行所有模型
        tasks = [query_one(probe) for probe in self.probes]
        
        # 按完成顺序处理
        for future in asyncio.as_completed(tasks):
            name, resp = await future
            
            # 检查是否选择沉默
            is_silent = "[沉默]" in resp or resp.strip() == "" or len(resp.strip()) < 3
            
            if is_silent:
                # 模型选择不发言，不加入历史
                self._log(f"{name} 选择沉默")
                responses[name] = "[沉默]"
            else:
                # 模型发言
                
                # Check if it is a JSON command (Advanced Feature)
                # If so, we should NOT add it to history as text, but trigger the event.
                # However, the `log_callback` in `chat_server.py` handles parsing.
                # BUT, if we add it to `history_manager` here as plain text, it will appear in the chat log.
                # So we should try to detect it here too.
                
                is_json_command = False
                msg_content = resp.strip()
                if msg_content.startswith("{") and msg_content.endswith("}") and '"type":' in msg_content:
                     # Simple check. If it looks like a command, we might want to store it differently?
                     # Actually, `chat_server.py`'s `group_log` callback will receive "NEW_MESSAGE" 
                     # which triggers broadcasting the last message in history.
                     # If we put the JSON string in history, the frontend will render it as text unless frontend parses it.
                     # The frontend `handleMessage` parses JSON events from `ws.onmessage`.
                     # But `NEW_MESSAGE` type sends a message object.
                     
                     # Better approach: 
                     # If it's a JSON command, we should treat it as an EVENT, not a MESSAGE.
                     # So we should pass it to log_callback as a dict, and NOT append to history (or append as a special type).
                     try:
                         import json
                         cmd_data = json.loads(msg_content)
                         if "type" in cmd_data:
                             is_json_command = True
                             # Inject name if missing
                             if "name" not in cmd_data:
                                 cmd_data["name"] = name
                             
                             # Trigger event broadcast
                             if self.log_callback:
                                 self.log_callback(cmd_data)
                             
                             # Do we append to history?
                             # If it's "quote", we want to show the quote in chat.
                             # If it's "pat", maybe a system notice?
                             # The frontend handles these events.
                             # For now, let's NOT append to text history to avoid duplicate/raw text display.
                             responses[name] = "[ACTION]" 
                     except:
                         pass

                if not is_json_command:
                    # Regular message
                    responses[name] = resp
                    history_manager.append({"name": name, "content": resp})
                    
                    # 触发UI更新
                    if self.log_callback:
                        self.log_callback("NEW_MESSAGE")

        return responses

    async def run_continuous_chat(self, history_manager, stop_event=None, ui_callback=None, typing_callback=None):
        """
        持续运行群聊对话循环，直到被外部中断。
        
        Args:
            history_manager: 聊天历史列表（会被修改）
            stop_event: asyncio.Event，设置后停止循环
            ui_callback: 有新消息时调用，用于刷新UI
            typing_callback: 有模型正在输入时调用，参数为正在输入的模型名列表
        """
        all_model_names = [p._modelName for p in self.probes]
        round_num = 0
        consecutive_silent_rounds = 0  # 连续全员沉默的轮数
        
        while True:
            # 检查是否需要停止
            if stop_event and stop_event.is_set():
                self._log("收到停止信号，对话结束")
                break
            
            round_num += 1
            self._log(f"--- 第 {round_num} 轮对话 ---")
            
            # 通知UI：模型正在思考
            if typing_callback:
                typing_callback(all_model_names)
            
            # 运行一轮对话
            responses = await self.run_group_chat_turn(history_manager)
            
            # 清除正在输入状态
            if typing_callback:
                typing_callback([])
            
            # 触发UI刷新
            if ui_callback:
                ui_callback()
            
            # 统计本轮有多少模型发言
            active_count = sum(1 for r in responses.values() if r != "[沉默]")
            
            if active_count == 0:
                consecutive_silent_rounds += 1
                self._log(f"本轮无人发言（连续 {consecutive_silent_rounds} 轮沉默）")
                
                # 如果连续3轮无人发言，进入冷却期
                if consecutive_silent_rounds >= 3:
                    self._log("对话进入冷却期，等待新话题...")
                    await asyncio.sleep(5.0)
                    # 重置计数，给一次新机会
                    if consecutive_silent_rounds >= 5:
                        self._log("持续沉默，暂停循环等待用户输入")
                        break
            else:
                consecutive_silent_rounds = 0
                self._log(f"本轮 {active_count} 人发言")
            
            # 轮次间隔（给用户阅读时间）
            await asyncio.sleep(random.uniform(2.0, 4.0))


