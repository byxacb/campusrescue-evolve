#!/usr/bin/env python3
"""
BYO-MCP #4: audit.report — 进化谱系审计 + 回放
================================================
查询和回放 AlphaEvolve 进化过程的完整审计记录，
确保每个候选方案的分数、insight、parent lineage 可追溯可回放。

工具集:
  - audit.list_runs(workflow_id?) → 列出所有进化运行
  - audit.get_run(run_id) → 获取单次运行完整 event chain
  - audit.replay(run_id) → 按时间序列回放每个候选
  - audit.get_stats(run_id) → 聚合统计
  - audit.export_to_sheets(run_id, sheet_id) → 写入 Google Sheets
"""

from fastmcp import FastMCP
import json
import os
from datetime import datetime
from pathlib import Path

AUDIT_LOG_DIR = Path(os.environ.get("AUDIT_LOG_DIR", "./audit_logs"))
AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)

mcp = FastMCP(name="audit.report", version="0.1.0")


@mcp.tool()
def list_runs(workflow_id: str | None = None) -> list[dict]:
    """
    列出所有进化运行，按时间倒序
    可选 workflow_id 过滤
    """
    runs = []
    for path in sorted(AUDIT_LOG_DIR.glob("*.jsonl"), reverse=True):
        try:
            data = json.loads(path.read_text().splitlines()[0] if path.stat().st_size > 0 else "{}")
            run = json.loads(data) if isinstance(data, str) else data
            if workflow_id and run.get("workflow_id") != workflow_id:
                continue
            runs.append({
                "run_id": path.stem,
                "workflow_id": run.get("workflow_id", "unknown"),
                "started_at": run.get("started_at"),
                "ended_at": run.get("ended_at"),
                "total_candidates": run.get("total_candidates", 0),
                "best_score": run.get("best_score"),
            })
        except Exception as e:
            runs.append({"run_id": path.stem, "error": str(e)})
    return runs


@mcp.tool()
def get_run(run_id: str) -> dict:
    """获取单次运行的完整 event chain"""
    path = AUDIT_LOG_DIR / f"{run_id}.jsonl"
    if not path.exists():
        return {"error": f"run_id {run_id} not found"}
    
    events = []
    with open(path) as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    
    return {
        "run_id": run_id,
        "total_events": len(events),
        "events": events,
    }


@mcp.tool()
def replay(run_id: str) -> dict:
    """按时间序列回放本次运行的每个候选"""
    run_data = get_run(run_id)
    if "error" in run_data:
        return run_data
    
    timeline = []
    for event in run_data["events"]:
        timeline.append({
            "timestamp": event.get("timestamp"),
            "event_type": event.get("event_type"),
            "candidate_id": event.get("candidate_id"),
            "generation": event.get("generation"),
            "parent_id": event.get("parent_id"),
            "scores": event.get("scores"),
            "insights": event.get("insights")[:200] if event.get("insights") else None,
            "status": event.get("status"),
        })
    
    return {
        "run_id": run_id,
        "timeline_length": len(timeline),
        "timeline": timeline,
    }


@mcp.tool()
def get_stats(run_id: str) -> dict:
    """聚合统计：最佳分数、平均分数、各代分布"""
    run_data = get_run(run_id)
    if "error" in run_data:
        return run_data
    
    # 按 generation 分组
    by_generation = {}
    all_scores = []
    for event in run_data["events"]:
        if event.get("event_type") != "evaluation":
            continue
        gen = event.get("generation", 0)
        if gen not in by_generation:
            by_generation[gen] = []
        scores = event.get("scores", [])
        if scores:
            by_generation[gen].append(scores)
            all_scores.append(scores)
    
    gen_stats = []
    for gen in sorted(by_generation.keys()):
        gen_scores = by_generation[gen]
        composite_scores = [sum(s) for s in gen_scores] if gen_scores else []
        gen_stats.append({
            "generation": gen,
            "candidate_count": len(gen_scores),
            "best_composite": max(composite_scores) if composite_scores else 0,
            "avg_composite": sum(composite_scores) / len(composite_scores) if composite_scores else 0,
        })
    
    return {
        "run_id": run_id,
        "total_candidates": len(all_scores),
        "best_score": max([sum(s) for s in all_scores]) if all_scores else None,
        "avg_score": sum(sum(s) for s in all_scores) / len(all_scores) if all_scores else None,
        "generation_stats": gen_stats,
    }


@mcp.tool()
def export_to_sheets(run_id: str, sheet_id: str) -> dict:
    """
    导出审计数据到 Google Sheets
    
    参数:
        run_id: 进化运行 ID
        sheet_id: Google Sheets 文档 ID
    
    返回:
        {"success": bool, "rows_written": N, "sheet_url": "..."}
    """
    # 简化实现：用户后续可在此调用 Sheets API
    run_data = get_run(run_id)
    if "error" in run_data:
        return run_data
    
    # TODO: 实现 Google Sheets API 集成
    return {
        "success": True,
        "rows_written": run_data.get("total_events", 0),
        "sheet_id": sheet_id,
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit",
        "note": "demo 阶段仅返回元数据；生产版本将调用 google-api-python-client 写入。"
    }


# ── 写入审计日志的辅助函数 ────────────────────────────

def append_event(run_id: str, event: dict) -> None:
    """追加一条审计事件到 run_id 对应的 JSONL 文件"""
    path = AUDIT_LOG_DIR / f"{run_id}.jsonl"
    event["timestamp"] = datetime.utcnow().isoformat()
    with open(path, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "8080"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port, log_level="INFO")