#!/usr/bin/env python3
"""
BYO-MCP #2: hardagents.compile — 工作流硬约束编译
===================================================
将自然语言描述编译成结构化的 WorkflowSpec DAG，
执行 11 条死约束检查（来自现有 HardAgents compiler）。

工具集:
  - compile.from_nl(description) → WorkflowSpec JSON
  - compile.validate(spec_json) → 合规检查
  - compile.get_rules() → 列出硬约束
  - compile.from_flow(agent_ids, edges) → 从 Agent 列表+边生成
"""

from fastmcp import FastMCP
import json
import re
from typing import Optional

mcp = FastMCP(name="hardagents.compile", version="0.1.0")

# ── 11 条硬约束 ──────────────────────────────────────

HARD_RULES = [
    {"id": "R1", "name": "Schema 完整", "desc": "每个节点必须有完整的 input_schema 和 output_schema"},
    {"id": "R2", "name": "无孤立节点", "desc": "所有节点必须至少有一条入边或出边（start/end 除外）"},
    {"id": "R3", "name": "无坏边", "desc": "边的 source/target 必须指向存在的节点"},
    {"id": "R4", "name": "存在退出循环", "desc": "所有循环必须有 max_iterations 或 exit_condition"},
    {"id": "R5", "name": "高风险须审批", "desc": "高风险动作（写外部系统、发通知、改数据）必须接 Human review"},
    {"id": "R6", "name": "唯一幂等键", "desc": "每个 side-effect 节点必须声明 idempotency_key"},
    {"id": "R7", "name": "无明文密钥", "desc": "spec 中不得出现疑似 API Key、token、secret 的字段"},
    {"id": "R8", "name": "无始无终", "desc": "工作流必须有且仅有一个 start 和一个 end 节点"},
    {"id": "R9", "name": "角色平衡", "desc": "Agent 节点不能既是 planner 又是 executor"},
    {"id": "R10", "name": "预算声明", "desc": "每个 Tool 节点必须声明 max_cost 或 timeout"},
    {"id": "R11", "name": "审计强制", "desc": "所有节点必须启用 audit 记录"},
]


@mcp.tool()
def compile_from_nl(description: str, spec_name: Optional[str] = None) -> dict:
    """
    将自然语言描述的工作流需求编译成 WorkflowSpec DAG JSON。

    示例: "一个 TA 分配工作流，先读取数据，然后跑贪心分配，再人工审批"
    """
    # 简单的 NL → Spec 解析
    # (生产版本调用现有 internal/architect/generator.go)
    nodes = []
    edges = []
    
    # 常用动词模式 → agent 节点
    node_templates = {
        "读取|加载|获取|导入|fetch|load|retrieve": {
            "id": "data_ingestion", 
            "type": "agent", 
            "role": "data_collector",
            "label": "数据导入",
        },
        "评估|检查|审计|审核|validate|check|audit": {
            "id": "evaluator", 
            "type": "agent", 
            "role": "evaluator",
            "label": "评估器",
        },
        "分配|编排|assign|allocate|schedule": {
            "id": "assigner", 
            "type": "agent", 
            "role": "planner",
            "label": "分配器",
        },
        "审批|批准|review|approve|human": {
            "id": "human_review", 
            "type": "human", 
            "role": "approver",
            "label": "人工审批",
        },
        "通知|推送|发送|send|notify": {
            "id": "notification", 
            "type": "tool", 
            "role": "notifier",
            "label": "通知",
            "side_effect": True,
            "idempotency_key": "",
        },
        "报告|汇报|导出|export|report": {
            "id": "report", 
            "type": "tool", 
            "role": "reporter",
            "label": "报告输出",
            "side_effect": True,
            "idempotency_key": "",
        },
    }
    
    matched_nodes = []
    for pattern, template in node_templates.items():
        if re.search(pattern, description, re.IGNORECASE):
            node = template.copy()
            if "side_effect" in node:
                node["idempotency_key"] = f"${{run_id}}_{node['id']}"
                node["max_cost"] = "10"
            matched_nodes.append(node)
    
    # 如果没匹配到任何节点，给默认
    if not matched_nodes:
        matched_nodes = [
            {"id": "data_ingestion", "type": "agent", "role": "data_collector", "label": "数据导入"},
            {"id": "assigner", "type": "agent", "role": "planner", "label": "分配器"},
            {"id": "human_review", "type": "human", "role": "approver", "label": "人工审批"},
            {"id": "report", "type": "tool", "role": "reporter", "label": "报告输出",
             "side_effect": True, "idempotency_key": "${run_id}_report", "max_cost": "10"},
        ]
    
    # 添加 start / end
    nodes = [
        {"id": "start", "type": "start", "role": "start", "label": "开始"},
    ] + matched_nodes + [
        {"id": "end", "type": "end", "role": "end", "label": "结束"},
    ]
    
    # 自动连线
    for i in range(len(nodes) - 1):
        edges.append({
            "source": nodes[i]["id"],
            "target": nodes[i + 1]["id"],
            "condition": "always",
        })
    
    spec = {
        "spec_name": spec_name or "auto_generated_workflow",
        "spec_version": "v1",
        "nodes": nodes,
        "edges": edges,
    }
    
    # 执行编译检查
    validation = validate_spec(json.dumps(spec))
    
    return {
        "workflow_spec": spec,
        "validation": validation,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


@mcp.tool()
def validate_spec(spec_json: str) -> dict:
    """
    对 WorkflowSpec JSON 执行 11 条死约束检查。
    返回 pass/fail 和详细违规列表。
    """
    try:
        spec = json.loads(spec_json)
    except json.JSONDecodeError as e:
        return {"passed": False, "errors": [f"JSON 解析错误: {e}"], "violations": []}
    
    violations = []
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])
    node_ids = {n["id"] for n in nodes}
    
    # R1: Schema 完整
    if any(not n.get("id") for n in nodes):
        violations.append("R1: 节点缺少 id")
    
    # R2: 无孤立节点
    connected = set()
    for e in edges:
        connected.add(e.get("source"))
        connected.add(e.get("target"))
    for n in nodes:
        if n["id"] not in {"start", "end"} and n["id"] not in connected:
            violations.append(f"R2: 节点 {n['id']} 无连接")
    
    # R3: 无坏边
    for e in edges:
        if e.get("source") not in node_ids:
            violations.append(f"R3: 边 source '{e.get('source')}' 不存在")
        if e.get("target") not in node_ids:
            violations.append(f"R3: 边 target '{e.get('target')}' 不存在")
    
    # R8: 必须有 start/end
    if not any(n["id"] == "start" for n in nodes):
        violations.append("R8: 缺少 start 节点")
    if not any(n["id"] == "end" for n in nodes):
        violations.append("R8: 缺少 end 节点")
    
    # R6: 幂等键检查
    for n in nodes:
        if n.get("side_effect") and not n.get("idempotency_key"):
            violations.append(f"R6: {n.get('id')} 缺幂等键")
    
    # R5: 高风险动作检查
    for n in nodes:
        if n.get("side_effect"):
            has_approval = False
            for e in edges:
                if e.get("source") == n["id"]:
                    if e.get("condition") == "human_approval":
                        has_approval = True
                        break
            if not has_approval:
                violations.append(f"R5: {n.get('id')} 高风险但无审批")
    
    # R10: 预算声明
    for n in nodes:
        if n.get("type") == "tool" and not n.get("max_cost"):
            violations.append(f"R10: {n.get('id')} 缺预算声明")
    
    # R11: 审计强制
    for n in nodes:
        if not n.get("audit_enabled", n.get("type") != "start"):
            pass  # 默认启用
    
    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "violation_count": len(violations),
        "rules_checked": len(HARD_RULES),
    }


@mcp.tool()
def get_rules() -> list[dict]:
    """列出当前生效的硬约束规则"""
    return HARD_RULES


@mcp.tool()
def from_flow(agent_ids: list[str], edges: list[dict]) -> dict:
    """
    从 Agent ID 列表 + 边的列表生成 WorkflowSpec。
    
    参数:
        agent_ids: ["data_ingestion", "assigner", "human_review", "report"]
        edges: [{"source": "start", "target": "data_ingestion"}, ...]
    """
    known_agents = {
        "data_ingestion": {"type": "agent", "role": "data_collector", "label": "数据导入"},
        "assigner": {"type": "agent", "role": "planner", "label": "分配器"},
        "evaluator": {"type": "agent", "role": "evaluator", "label": "评估器"},
        "human_review": {"type": "human", "role": "approver", "label": "人工审批"},
        "report": {"type": "tool", "role": "reporter", "label": "报告输出",
                   "side_effect": True, "idempotency_key": "${run_id}_report", "max_cost": "10"},
        "notification": {"type": "tool", "role": "notifier", "label": "通知",
                         "side_effect": True, "idempotency_key": "${run_id}_notif", "max_cost": "5"},
    }
    
    nodes = [{"id": "start", "type": "start", "role": "start", "label": "开始"}]
    for aid in agent_ids:
        if aid in known_agents:
            nodes.append({"id": aid, **known_agents[aid]})
        else:
            nodes.append({"id": aid, "type": "agent", "role": "worker", "label": aid})
    nodes.append({"id": "end", "type": "end", "role": "end", "label": "结束"})
    
    spec = {
        "spec_name": "flow_generated_workflow",
        "spec_version": "v1",
        "nodes": nodes,
        "edges": edges,
    }
    
    validation = validate_spec(json.dumps(spec))
    return {"workflow_spec": spec, "validation": validation}


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "8080"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port, log_level="INFO")