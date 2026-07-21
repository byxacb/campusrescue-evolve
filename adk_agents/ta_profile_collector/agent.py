#!/usr/bin/env python3
"""
ADK Agent: TAProfileCollector
==============================
TA 资料收集 Agent - 通过对话式交互收集 TA 的偏好、技能、可用时间。

职责:
  1. 询问 TA 的姓名、学号
  2. 收集技能列表 (Python, Java, ML, ...)
  3. 询问每学期最多能带几门课
  4. 收集每周可用时间槽
  5. 询问 TA 偏好 (想带哪种课、避开什么)
  6. 生成结构化 profile JSON
  
调用: Agent Runtime 托管，由 Agent Designer Flow 触发
依赖: data.retrieve MCP 已部署
"""

import json
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

# ── 数据结构 ──────────────────────────────────────────

class TAProfile(BaseModel):
    """TA 完整资料"""
    ta_id: str = Field(description="TA 学号")
    name: str = Field(description="TA 姓名")
    skills: List[str] = Field(description="技能列表")
    max_courses: int = Field(ge=1, le=5, description="每学期最多带课数")
    available_slots: List[str] = Field(description="可用时间槽，如 Mon-09:00 / Tue-14:00")
    preferences: Dict[str, str] = Field(
        default_factory=dict,
        description="偏好（想带/避开）",
    )


# ── Agent 定义 ────────────────────────────────────────

SYSTEM_PROMPT = """你是 TAProfileCollector，一个收集大学助教 (TA) 资料的智能助理。

你的工作流程:
1. 打招呼并询问 TA 的姓名和学号
2. 询问 TA 的技能清单，包括但不限于:
   - 编程语言: Python, Java, JavaScript, R, C++
   - 数据科学: DataAnalysis, Statistics, MachineLearning, DeepLearning
   - Web 开发: WebDevelopment, HTML, CSS
   - 数据库: SQL, Database, NLP, ComputerVision
3. 询问 TA 每学期最多能带多少门课程 (1-5)
4. 收集 TA 每周可用时间。请用 " 周-小时" 格式 (如 Mon-09:00, Tue-14:00), 至少收集 3 个时段
5. 询问偏好:
   - 偏好带的课程类型
   - 想避开的课程
   - 是否有大班/小班偏好
6. 收集完毕后，请用结构化 JSON 格式总结 TA 资料

输出格式:
```json
{
  "ta_id": "学号",
  "name": "姓名",
  "skills": ["技能1", "技能2", ...],
  "max_courses": 3,
  "available_slots": ["Mon-09:00", "Tue-14:00", ...],
  "preferences": {
    "prefer": "想带什么",
    "avoid": "想避开什么",
    "class_size": "大班/小班偏好"
  }
}
```

注意:
- 必须确认 TA 至少提供 3 个可用时间槽
- 至少提供 2 个技能
- max_courses 必须在 1-5 之间
- 在收集结束前请用户确认信息正确
"""


USER_GREETING_TEMPLATE = """请协助这位 TA 录入资料:

学号占位: {ta_id}
姓名: {name if name else '(待填)'}
技能: {skills or '(待填)'}
最多带课数: {max_courses or '(待填)'}
可用时间: {available_slots or '(待填)'}
"""


async def collect_ta_profile(initial_info: Optional[dict] = None) -> dict:
    """
    启动 TA profile collection 流程
    
    参数:
        initial_info: TA 已知信息 (可选)
    
    返回:
        结构化 TA profile JSON
    """
    # 在真实 ADK 实现中，这里会调用 ADK Runner 用 SYSTEM_PROMPT 启动 conversation
    # 当 TA 在 chat 中输入后，Agent 会按 instruction 引导完成收集
    profile = TAProfile(
        ta_id=initial_info.get("ta_id", "") if initial_info else "",
        name=initial_info.get("name", "") if initial_info else "",
        skills=initial_info.get("skills", []) if initial_info else [],
        max_courses=initial_info.get("max_courses", 3) if initial_info else 3,
        available_slots=initial_info.get("available_slots", []) if initial_info else [],
        preferences=initial_info.get("preferences", {}) if initial_info else {},
    )
    
    return profile.model_dump()


def get_agent_definition() -> dict:
    """返回 ADK Agent 定义 (用于 Agent Registry 注册)"""
    return {
        "name": "ta_profile_collector",
        "display_name": "TA 资料收集 Agent",
        "description": "通过对话式交互收集 TA 资料，生成结构化 profile JSON 供 AlphaEvolve 使用",
        "system_prompt": SYSTEM_PROMPT,
        "tools": [
            {
                "name": "save_ta_profile",
                "description": "将收集到的 TA profile 写入数据库",
                "parameters": TAProfile.model_json_schema(),
            },
        ],
        "model": "gemini-3.5-flash",
        "temperature": 0.1,
        "max_tokens": 2048,
    }


if __name__ == "__main__":
    # 自检
    import asyncio
    result = asyncio.run(collect_ta_profile({
        "ta_id": "TA001",
        "name": "张三",
        "skills": ["Python", "MachineLearning"],
        "max_courses": 3,
    }))
    print(json.dumps(result, indent=2))
    print("\nAgent 定义:")
    print(json.dumps(get_agent_definition(), indent=2, ensure_ascii=False))
