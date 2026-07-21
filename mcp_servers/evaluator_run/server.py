#!/usr/bin/env python3
"""
BYO-MCP #3: evaluator.run — AlphaEvolve 候选评估执行器
========================================================
执行 TA 分配候选方案的评估，返回 scores + insights。

工具集:
  - evaluate_assignment(assignments_json, data_dir) → scores, insights
  - evaluate_from_seed(input_dir) → 执行 seed 并评估
"""

from fastmcp import FastMCP
import json
import os
import sys
from pathlib import Path

# 复用评估器代码
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "alphaevolve" / "evaluator"))
from evaluate import evaluate, _load_tas, _load_courses  # noqa

DATA_DIR = Path(os.environ.get("DATA_DIR", "./fixtures"))
SEED_DIR = Path(__file__).parent.parent.parent / "alphaevolve" / "seed"

mcp = FastMCP(name="evaluator.run", version="0.1.0")


@mcp.tool()
def evaluate_assignment(assignments_json: str, data_dir: str | None = None) -> dict:
    """
    评估一组 TA 分配方案。
    
    参数:
        assignments_json: 分配方案的 JSON 字符串 {"course_id": "ta_id", ...}
        data_dir: 数据目录路径 (默认 fixtures/)
    
    返回:
        {"scores": [...], "insights": "...", "summary": {...}}
    """
    assignments = json.loads(assignments_json)
    actual_data_dir = data_dir or str(DATA_DIR)
    
    # 把 assignments 写为临时文件供 evaluate() 读取
    tmp_path = "/tmp/_eval_assignments.json"
    with open(tmp_path, "w") as f:
        json.dump({"assignments": assignments}, f)
    
    scores, insights = evaluate(tmp_path, actual_data_dir)
    
    # 清理
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    
    return {
        "scores": {
            "hard_satisfaction_ratio": scores[0],
            "skill_match_coverage": scores[1],
            "workload_balance": scores[2],
            "coverage": scores[3],
        },
        "insights": insights,
        "summary": {
            "assigned_courses": len(assignments),
            "total_courses": len(_load_courses(f"{actual_data_dir}/courses.csv")),
            "composite_score": round(
                0.50 * scores[0] + 0.25 * scores[1] +
                0.15 * scores[2] + 0.10 * scores[3], 4
            ),
        },
    }


@mcp.tool()
def run_seed(data_dir: str | None = None) -> dict:
    """运行 seed 算法生成基线分配，并返回评估结果"""
    actual_data_dir = data_dir or str(DATA_DIR)
    
    # 导入 seed 并运行
    sys.path.insert(0, str(SEED_DIR))
    from greedy_assign import greedy_assign, _load_tas, _load_courses
    
    tas = _load_tas(f"{actual_data_dir}/tas.csv")
    courses = _load_courses(f"{actual_data_dir}/courses.csv")
    assignments = greedy_assign(tas, courses)
    
    # 评估
    return evaluate_assignment(json.dumps(assignments), actual_data_dir)


@mcp.tool()
def list_metrics() -> dict:
    """列出 evaluator 使用的评分指标说明"""
    return {
        "metrics": [
            {
                "id": "hard_satisfaction_ratio",
                "name": "硬约束满足率",
                "description": "硬约束（时间冲突、负载上限、TA 存在）的满足比例",
                "range": "[0, 1]",
                "weight": 0.50,
                "direction": "越大越好"
            },
            {
                "id": "skill_match_coverage",
                "name": "技能匹配覆盖率",
                "description": "已分配 TA 的技能与课程需求匹配程度",
                "range": "[0, 1]",
                "weight": 0.25,
                "direction": "越大越好"
            },
            {
                "id": "workload_balance",
                "name": "工作负载均衡度",
                "description": "TA 之间分配课程数的均衡程度 (1-CV)",
                "range": "[0, 1]",
                "weight": 0.15,
                "direction": "越大越好"
            },
            {
                "id": "coverage",
                "name": "分配覆盖率",
                "description": "已分配 TA 的课程占总课程比例",
                "range": "[0, 1]",
                "weight": 0.10,
                "direction": "越大越好"
            },
        ],
        "evaluator_version": "0.1.0",
    }


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "8080"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port, log_level="INFO")