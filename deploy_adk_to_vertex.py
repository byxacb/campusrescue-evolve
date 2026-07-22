"""Deploy CampusRescueOrchestrator ADK agent to Vertex AI Reasoning Engine.

This bypasses Agent Designer's UI template (which had a default Dockerfile issue)
and uses ADK's `reasoning_engines.AdkApp` directly via the aiplatform SDK.
"""
import json
import sys
import os

# Make agent_platform importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google import genai
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.tools import agent_tool
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool import McpToolset
import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

# ── BYO-MCP toolsets (5 Cloud Run services, us-central1) ────────────
# Construct McpToolset objects at agent build time. ADK fetches tools lazily on first call.
MCP_URLS = {
    "data_retrieve":      "https://mcp-data-retrieve-5l3z4bmblq-uc.a.run.app/mcp",
    "evaluator_run":      "https://mcp-evaluator-run-5l3z4bmblq-uc.a.run.app/mcp",
    "audit_report":       "https://mcp-audit-report-5l3z4bmblq-uc.a.run.app/mcp",
    "hardagents_compile": "https://mcp-hardagents-compile-5l3z4bmblq-uc.a.run.app/mcp",
    "campusflow_run":     "https://mcp-campusflow-run-5l3z4bmblq-uc.a.run.app/mcp",
}
_MCP_TOOLSETS = {n: McpToolset(connection_params=StreamableHTTPConnectionParams(url=u))
                 for n, u in MCP_URLS.items()}
def _tools(*names): return [_MCP_TOOLSETS[n] for n in names]
print(f"🔗 Constructed {len(_MCP_TOOLSETS)} McpToolset objects (lazy fetch)")


PROJECT = "project-53bf8b85-eb44-4391-a2e"
LOCATION = "us-west1"
STAGING_BUCKET = f"gs://{PROJECT}-adk-staging"

vertexai.init(
    project=PROJECT,
    location=LOCATION,
    staging_bucket=STAGING_BUCKET,
)
ta_profile_collector = LlmAgent(
    name="CampusRescueTAProfileCollector",
    model=Gemini(model="gemini-2.5-flash"),
    description="收集 TA 资料 (技能、可用时间、偏好)，生成结构化 profile JSON",
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
    tools=_tools("data_retrieve"),
)

# === 2. EvolutionAgent 子 Agent ===
evolution_agent = LlmAgent(
    name="CampusRescueEvolutionAgent",
    model=Gemini(model="gemini-2.5-pro"),
    description="运行 AlphaEvolve 进化引擎: 输入 TA profile + 课程数据 → 输出最优分配方案",
    instruction="""你是 EvolutionAgent，运行 AlphaEvolve 进化引擎。

工作流:
1. 调用 data_retrieve.load_dataset() 获取 courses + tas
2. 接收 TAProfileCollector 输出的新 TA profile, 注入到 tas 列表
3. 调用 evaluator_run.run_seed() 生成基线方案 (seed_score)
4. 调用 evaluator_run.evolve_generation() 进行 N 次迭代进化
5. 迭代到 budget (gen=20 或综合分≥0.85) 终止
6. 输出 best_assignments + evolution_result + improvement_vs_seed JSON

输出 JSON:
{
  "best_assignments": {"CS101": "ta_001"},
  "evolution_result": {"best_score": 0.6624, "seed_score": 0.6000, "improvement": 0.0624, "generations_run": 20},
  "insights": ["在变异池里发现 N=14 的拓扑+ 邻域搜索收敛"]
}
""",
    output_key="evolution_result",
    tools=_tools("data_retrieve", "evaluator_run"),
)

# === 3. AssignmentReviewer 子 Agent ===
assignment_reviewer = LlmAgent(
    name="CampusRescueAssignmentReviewer",
    model=Gemini(model="gemini-2.5-flash"),
    description="审查 AlphaEvolve 生成的 TA 分配方案, 辅助系主任做审批决策",
    instruction="""你是 AssignmentReviewer，TA 分配方案审查助理。

流程:
1. 读取 evolution_result + best_assignments
2. 展示关键指标: coverage, hard_constraints, skill_match, improvement_vs_seed
3. 列出潜在担忧: 超负荷 TA, 技能不匹配, 偏好冲突
4. 主动建议是否批准 + 改进建议
5. 询问系主任人工审批 (approved/rejected)
6. 批准→调用 audit_report.record_audit_log() 持久化
7. 批准→调用 audit_report.export_to_sheets()
8. 拒绝→触发 campusflow_run.advance_workflow_step() 重新收集

输出 JSON:
{
  "decision": "approved" | "rejected",
  "decision_reason": "",
  "audit_id": "",
  "sheets_url": ""
}
""",
    output_key="review_result",
    tools=_tools("audit_report", "campusflow_run"),
)

# === Root Agent ===
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

按顺序调用三个子 Agent. 当系主任拒绝时, 重新启动流程.
""",
    sub_agents=[
        ta_profile_collector,
        evolution_agent,
        assignment_reviewer,
    ],
    tools=_tools("data_retrieve", "evaluator_run", "audit_report", "hardagents_compile", "campusflow_run"),
)


def main():
    # GCP staging bucket (create if missing)
    from google.cloud import storage
    storage_client = storage.Client(project=PROJECT)
    bucket_name = f"{PROJECT}-adk-staging"
    try:
        storage_client.get_bucket(bucket_name)
        print(f"✅ Bucket {bucket_name} exists")
    except Exception:
        bucket = storage_client.create_bucket(bucket_name, location="us-west1")
        print(f"✅ Created bucket {bucket_name}")

    # Wrap in ADK app
    app = AdkApp(
        agent=root_agent,
        env_vars={
            "MCP_DATA_RETRIEVE_URL": "https://mcp-data-retrieve-5l3z4bmblq-uc.a.run.app/mcp",
            "MCP_EVALUATOR_RUN_URL": "https://mcp-evaluator-run-5l3z4bmblq-uc.a.run.app/mcp",
            "MCP_AUDIT_REPORT_URL": "https://mcp-audit-report-5l3z4bmblq-uc.a.run.app/mcp",
            "MCP_HARDAGENTS_COMPILE_URL": "https://mcp-hardagents-compile-5l3z4bmblq-uc.a.run.app/mcp",
            "MCP_CAMPUSFLOW_RUN_URL": "https://mcp-campusflow-run-5l3z4bmblq-uc.a.run.app/mcp",
        },
    )

    print("🚀 Deploying CampusRescueOrchestrator to Vertex AI Reasoning Engine...")
    remote_app = agent_engines.create(
        app,
        requirements=[
            "google-adk>=2.5.0",
            "google-cloud-aiplatform>=1.161.0",
            "google-genai>=2.12.0",
            "google-api-core>=2.32.0",
            "mcp>=1.0.0",
        ],
        display_name="CampusRescueOrchestrator",
        description="系主任救火队员编排 Agent: AlphaEvolve + 5 MCP + 3 sub-agents",
    )
    print(f"✅ Deployed! Remote Reasoning Engine resource name:")
    print(f"   {remote_app.resource_name}")
    print(f"   Display: {remote_app.display_name}")
    return remote_app.resource_name


if __name__ == "__main__":
    name = main()
    print(f"\nDONE: {name}")
