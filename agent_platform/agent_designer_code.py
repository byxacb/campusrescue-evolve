"""
CampusRescueOrchestrator - 系主任救火队员编排 Agent
=====================================================
ADK Python 代码: 包含 3 个子 Agent + 调用 5 个 BYO-MCP server
- TAProfileCollector: 收集 TA 资料
- EvolutionAgent: 运行 AlphaEvolve 进化引擎
- AssignmentReviewer: 审查分配方案 + 系主任审批
- Root: CampusRescueOrchestrator 编排上述子 agent
工具:
- data_retrieve (Cloud Run): load_dataset, list_courses, list_tas
- evaluator_run (Cloud Run): run_seed, evaluate_candidate, evolve_generation
- audit_report (Cloud Run): record_audit_log, export_to_sheets
- hardagents_compile (Cloud Run): compile_check
- campusflow_run (Cloud Run): advance_workflow_step
"""

from functools import cached_property
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.genai import Client
from google.adk.tools import agent_tool
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools import url_context


# === 1. TAProfileCollector 子 Agent ===
campus_rescue_ta_profile_collector_agent = LlmAgent(
    name="CampusRescueTAProfileCollector",
    model=Gemini(model="gemini-2.5-flash"),
    description="通过对话式交互收集 TA 资料 (技能、可用时间、偏好)，生成结构化 profile JSON",
    instruction="""你是 TAProfileCollector，收集大学助教资料的智能助理。

流程:
1. 打招呼并询问 TA 的姓名和学号
2. 询问技能清单 (Python, Java, ML, DataAnalysis, WebDevelopment, Database, NLP, ComputerVision, Statistics, R)
3. 询问每学期最多能带多少门课 (1-5)
4. 收集每周可用时间 (Mon-09:00 格式, ≥3 个时段)
5. 询问偏好 (想带什么课、避开什么、大班/小班偏好)
6. 用结构化 JSON 总结输出

输出 JSON:
{
  "ta_id": "",
  "name": "",
  "skills": [],
  "max_courses": 3,
  "available_slots": [],
  "preferences": {"prefer": "", "avoid": "", "class_size": ""}
}
""",
    output_key="ta_profile",
)


# === 2. EvolutionAgent 子 Agent (调 AlphaEvolve MCP) ===
campus_rescue_evolution_agent = LlmAgent(
    name="CampusRescueEvolutionAgent",
    model=Gemini(model="gemini-2.5-pro"),
    description="运行 AlphaEvolve 进化引擎: 输入 TA profile + 课程数据 → 输出最优分配方案",
    instruction="""你是 EvolutionAgent，运行 AlphaEvolve 进化引擎。

工作流:
1. 调用 data_retrieve.load_dataset()  获取 courses + tas
2. 接收 TAProfileCollectorAgent 输出的新 TA profile, 注入到 tas 列表
3. 调用 evaluator_run.run_seed()  生成基线方案 (seed_score)
4. 调用 evaluator_run.evolve_generation() 进行 N 次迭代进化
   - 每代变异 + 评估 + 优秀个体保留
   - logging: 当前最优综合分 / 改进幅度 / 拓扑结构
5. 迭代到 budget (gen=20 或综合分≥0.85) 终止
6. 输出 best_assignments + evolution_result + improvement_vs_seed JSON

输出 JSON:
{
  "best_assignments": {"CS101": "ta_001", ...},
  "evolution_result": {"best_score": 0.6624, "seed_score": 0.6000, "improvement": 0.0624, "generations_run": 20},
  "insights": ["在变异池里发现 N=14 的拓扑+ 邻域搜索收敛"]
}
""",
    output_key="evolution_result",
)


# === 3. AssignmentReviewer 子 Agent ===
campus_rescue_assignment_reviewer_agent = LlmAgent(
    name="CampusRescueAssignmentReviewer",
    model=Gemini(model="gemini-2.5-flash"),
    description="审查 AlphaEvolve 生成的 TA 分配方案, 辅助系主任做审批决策",
    instruction="""你是 AssignmentReviewer，TA 分配方案审查助理。

流程:
1. 读取 evolution_result + best_assignments
2. 展示关键指标:
   - coverage (课程覆盖率)
   - hard_constraints (硬约束违反数)
   - skill_match (技能匹配率)
   - improvement_vs_seed (相对 seed 基线提升)
3. 列出潜在担忧:
   - 超负荷 TA (>3 门课)
   - 技能不匹配课程
   - 偏好冲突
4. 主动建议是否批准 + 改进建议
5. 询问系主任人工审批 (approved/rejected)
6. 批准→调用 audit_report.record_audit_log() 持久化审计日志
7. 批准→调用 audit_report.export_to_sheets() 导出 Google Sheets
8. 拒绝→触发 CampusFlow_run.advance_workflow_step() 回头重新收集

输出 JSON:
{
  "decision": "approved" | "rejected",
  "decision_reason": "",
  "audit_id": "",
  "sheets_url": ""
}
""",
    output_key="review_result",
)


# === Root Agent: CampusRescueOrchestrator ===
root_agent = LlmAgent(
    name="CampusRescueOrchestrator",
    model=Gemini(model="gemini-2.5-pro"),
    description="系主任救火队员编排: 收集 TA → 进化求解 → 审查 → 审批 → 审计",
    instruction="""你是 CampusRescueOrchestrator，系主任救火队员编排 Agent。

工作流 (5 阶段):
1. 收集阶段 (TAProfileCollector): 通过对话收集年间新招聘 TA 的资料
2. 数据准备 (data_retrieve): 加载历史课程 + 现有 TA 数据集
3. 进化阶段 (EvolutionAgent): 运行 AlphaEvolve 进化算法求解最优分配
4. 审查阶段 (AssignmentReviewer): 生成审查摘要, 触发系主任人工审批
5. 收尾 (audit_report + campusflow_run):
   - 批准 → 写审计日志 + 导出 Sheets + 推进工作流
   - 拒绝 → 回退到收集阶段重新分配

请按顺序调用三个子 Agent. 当系主任拒绝时, 重新启动流程.
""",
    sub_agents=[
        campus_rescue_ta_profile_collector_agent,
        campus_rescue_evolution_agent,
        campus_rescue_assignment_reviewer_agent,
    ],
    tools=[
        # 三个子 agent 当作工具调用
        agent_tool.AgentTool(agent=campus_rescue_ta_profile_collector_agent),
        agent_tool.AgentTool(agent=campus_rescue_evolution_agent),
        agent_tool.AgentTool(agent=campus_rescue_assignment_reviewer_agent),
    ],
)
