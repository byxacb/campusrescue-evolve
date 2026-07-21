#!/usr/bin/env python3
"""
BYO-MCP #5: campusflow.run — 工作流执行引擎
============================================
驱动编译通过的工作流按确定性流程执行。
管理状态迁移、重试、人工审批、补偿、审计事件。

工具集:
  - run.start(workflow_spec_json, config) → run_id
  - run.status(run_id) → 当前状态
  - run.get_result(run_id) → 最终结果
  - run.list_runs(limit) → 历史执行
  - run.human_decision(run_id, approved, comment) → 人审
"""

from fastmcp import FastMCP
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(os.environ.get("CAMPUSFLOW_DATA_DIR", "./run_state"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

mcp = FastMCP(name="campusflow.run", version="0.1.0")


# ── 运行状态管理 ──────────────────────────────────────

def _load_run(run_id: str) -> dict | None:
    path = DATA_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _save_run(run: dict) -> None:
    path = DATA_DIR / f"{run['run_id']}.json"
    with open(path, "w") as f:
        json.dump(run, f, indent=2, ensure_ascii=False)


def _next_node(nodes: list, edges: list, current_id: str) -> str | None:
    """按边找下一节点"""
    for e in edges:
        if e.get("source") == current_id:
            return e.get("target")
    return None


# ── MCP 工具 ──────────────────────────────────────────

@mcp.tool()
def start(workflow_spec_json: str, config: Optional[dict] = None) -> dict:
    """
    启动一次工作流执行。
    
    参数:
        workflow_spec_json: WorkflowSpec JSON string
        config: 可选配置 {data_dir, max_retries, ...}
    
    返回:
        {"run_id": "...", "status": "...", "current_node": "..."}
    """
    try:
        spec = json.loads(workflow_spec_json)
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析错误: {e}"}
    
    run_id = f"flow-{uuid.uuid4().hex[:12]}"
    
    run = {
        "run_id": run_id,
        "workflow_spec": spec,
        "config": config or {},
        "status": "running",
        "current_node": "start",
        "nodes_completed": [],
        "nodes_failed": [],
        "human_approvals": {},
        "audit_events": [],
        "started_at": datetime.utcnow().isoformat(),
        "ended_at": None,
    }
    
    # 记录启动事件
    run["audit_events"].append({
        "timestamp": run["started_at"],
        "event_type": "workflow_started",
        "node": "start",
        "payload": {"spec_name": spec.get("spec_name", "")},
    })
    
    _save_run(run)
    
    return {
        "run_id": run_id,
        "status": "running",
        "current_node": "start",
        "message": "工作流已启动",
    }


@mcp.tool()
def status(run_id: str) -> dict:
    """查询工作流执行状态"""
    run = _load_run(run_id)
    if not run:
        return {"error": f"run_id {run_id} 不存在"}
    
    return {
        "run_id": run["run_id"],
        "status": run["status"],
        "current_node": run["current_node"],
        "nodes_completed": run["nodes_completed"],
        "nodes_failed": run["nodes_failed"],
        "human_approvals": run["human_approvals"],
        "progress": f"{len(run['nodes_completed'])}/{len(run['workflow_spec'].get('nodes', []))}"
            if run["workflow_spec"].get("nodes") else "N/A",
        "started_at": run["started_at"],
        "ended_at": run["ended_at"],
    }


@mcp.tool()
def advance(run_id: str, node_result: Optional[dict] = None) -> dict:
    """
    推进工作流到下一节点。
    通常由 ADK Agent 执行完当前任务后调用。
    
    参数:
        run_id: 运行 ID
        node_result: 当前节点的执行结果 {outputs, score, error?}
    
    返回:
        {"status": "..."/ "blocked" / "completed", "next_node": "..."}
    """
    run = _load_run(run_id)
    if not run:
        return {"error": f"run_id {run_id} 不存在"}
    
    if run["status"] != "running":
        return {"error": f"工作流已 {run['status']}"}
    
    current = run["current_node"]
    nodes = run["workflow_spec"].get("nodes", [])
    edges = run["workflow_spec"].get("edges", [])
    
    # 查找当前节点定义
    current_node_def = next((n for n in nodes if n["id"] == current), None)
    
    # 记录完成
    if current != "start":
        run["nodes_completed"].append(current)
        run["audit_events"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "node_completed",
            "node": current,
            "result": node_result or {},
        })
    
    # 检查是否是 human review 节点 → 旧逻辑 (移除, 因为已在进入下一节点时检查)
    
    # 推进到下一节点
    next_node = _next_node(nodes, edges, current)
    next_node_def = next((n for n in nodes if n["id"] == next_node), None)
    
    # 如果下一节点是 human review 且未审批 → 阻塞
    if next_node_def and next_node_def.get("type") == "human":
        if next_node not in run["human_approvals"]:
            run["current_node"] = next_node
            run["status"] = "blocked_human"
            run["audit_events"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": "node_started",
                "node": next_node,
            })
            _save_run(run)
            return {
                "status": "blocked",
                "reason": "awaiting_human_approval",
                "current_node": next_node,
                "message": f"节点 '{next_node}' 等待人工审批",
            }

    
    if next_node is None or next_node == "end":
        run["current_node"] = "end"
        run["status"] = "completed"
        run["ended_at"] = datetime.utcnow().isoformat()
        run["nodes_completed"].append("end")
        run["audit_events"].append({
            "timestamp": run["ended_at"],
            "event_type": "workflow_completed",
            "node": "end",
        })
        _save_run(run)
        return {
            "status": "completed",
            "next_node": None,
            "message": "工作流执行完成",
        }
    
    run["current_node"] = next_node
    run["audit_events"].append({
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": "node_started",
        "node": next_node,
    })
    _save_run(run)
    
    return {
        "status": "running",
        "next_node": next_node,
        "previous_node": current,
        "nodes_completed": run["nodes_completed"],
    }


@mcp.tool()
def human_decision(run_id: str, approved: bool, comment: str = "") -> dict:
    """
    人工审批决策。当工作流阻塞在 human 节点时调用。
    
    参数:
        run_id: 运行 ID
        approved: True=批准继续, False=驳回
        comment: 审批意见
    
    返回:
        继续执行或驳回
    """
    run = _load_run(run_id)
    if not run:
        return {"error": f"run_id {run_id} 不存在"}
    
    if run["status"] != "blocked_human":
        return {"error": f"工作流未阻塞在 human 节点(当前状态: {run['status']})"}
    
    current = run["current_node"]
    run["human_approvals"][current] = {
        "approved": approved,
        "comment": comment,
        "timestamp": datetime.utcnow().isoformat(),
    }
    run["audit_events"].append({
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": "human_decision",
        "node": current,
        "decision": "approved" if approved else "rejected",
        "comment": comment,
    })
    
    if approved:
        run["status"] = "running"
        _save_run(run)
        adv = advance(run_id, node_result={"human_approved": True, "comment": comment})
        return {
            "status": "running",
            "message": f"人工审批通过: {comment}",
            "next_node": adv.get("next_node") if isinstance(adv, dict) else None,
        }
    else:
        run["status"] = "rejected"
        run["ended_at"] = datetime.utcnow().isoformat()
        _save_run(run)
        return {
            "status": "rejected",
            "message": f"人工驳回了节点 {current}",
            "comment": comment,
        }


@mcp.tool()
def get_result(run_id: str) -> dict:
    """获取工作流执行最终结果"""
    run = _load_run(run_id)
    if not run:
        return {"error": f"run_id {run_id} 不存在"}
    
    if run["status"] not in ("completed", "rejected"):
        return {
            "error": f"工作流尚未结束(当前状态: {run['status']})",
            "status": run["status"],
        }
    
    return {
        "run_id": run["run_id"],
        "status": run["status"],
        "nodes_completed": run["nodes_completed"],
        "nodes_failed": run["nodes_failed"],
        "total_nodes": len(run["workflow_spec"].get("nodes", [])),
        "duration": f"{run['ended_at']} - {run['started_at']}" if run.get("ended_at") else None,
        "started_at": run.get("started_at"),
        "ended_at": run.get("ended_at"),
        "human_approvals": run["human_approvals"],
        "audit_events": run["audit_events"],
    }


@mcp.tool()
def list_runs(limit: int = 10) -> list[dict]:
    """列出最近的工作流执行"""
    runs = []
    for path in sorted(DATA_DIR.glob("*.json"), reverse=True):
        if len(runs) >= limit:
            break
        try:
            run = json.loads(path.read_text())
            runs.append({
                "run_id": run.get("run_id"),
                "status": run.get("status"),
                "current_node": run.get("current_node"),
                "nodes_completed": len(run.get("nodes_completed", [])),
                "started_at": run.get("started_at"),
                "ended_at": run.get("ended_at"),
            })
        except Exception:
            continue
    return runs


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "8080"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port, log_level="INFO")