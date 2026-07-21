#!/usr/bin/env python3
"""
ADK Agent: AssignmentReviewer
==============================
分配审查 Agent — 查看 AlphaEvolve 生成的 TA 分配方案，提供优化建议，
辅助系主任做出人工审批决策。

职责:
  1. 读取进化结果 (evolution_result.json + best_assignments.json)
  2. 对比 seed 与最优方案的指标差异
  3. 高亮潜在问题 (负载过重/技能不匹配/未分配课程)
  4. 生成一目了然的可视化摘要
  5. 向系主任展示并等待审批决策

依赖: evaluator.run MCP, audit.report MCP
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

SYSTEM_PROMPT = """你是 AssignmentReviewer，一个 TA 分配方案审查助理。

你的工作:
1. 读取进化引擎生成的分配方案和结果
2. 向系主任展示关键指标:
   - 分配覆盖率 (courses assigned / total)
   - 硬约束满足率 (constraints satisfied / total)
   - 技能匹配率 (skill match score)
   - 负载均衡度 (workload balance)
   - 与 seed 基线的提升百分比
3. 列出潜在的担忧:
   - 哪些 TA 超负荷或闲置
   - 哪些课程技能匹配度低于 70%
   - 是否有该分配但 TA 时间冲突未检出
4. 生成简明摘要后，询问系主任是否批准

输出格式:
```json
{
  "review_summary": {
    "coverage": "20/20 = 100%",
    "hard_constraints": "98% satisfied",
    "skill_match": "0.85/1.0",
    "improvement_vs_seed": "+12.3%",
    "concerns": ["TA003 负载 3/2 (超 1)", "CS402 技能匹配 < 60%"]
  },
  "recommendation": "approve / reject / adjust",
  "notes": "建议先调整 TA003 的分配"
}
```
"""


def load_evolution_result() -> dict:
    """读取进化结果文件"""
    paths = [
        "evolution_result.json",
        "best_assignments.json",
        "../evolution_result.json",
        "../best_assignments.json",
    ]
    result = {"found": False}
    for p in paths:
        path = Path(p)
        if path.exists():
            with open(path) as f:
                result = json.load(f)
            result["found"] = True
            result["source_path"] = p
            break
    return result


def compare_with_seed(result: dict) -> dict:
    """对比 Seed 与最优方案"""
    return {
        "seed_composite_score": result.get("seed_composite", "N/A"),
        "best_composite_score": result.get("best_composite", "N/A"),
        "improvement_pct": result.get("improvement_pct", "N/A"),
        "generations": result.get("generations", "N/A"),
        "total_candidates_evaluated": result.get("total_candidates", "N/A"),
    }


def generate_summary_table(result: dict) -> str:
    """生成一目了然的摘要表格"""
    if not result.get("found"):
        return "⚠️ 未找到进化结果文件，请先运行 AlphaEvolve 进化。"
    
    metrics = result.get("best_scores", {})
    seed = result.get("seed_composite", 0)
    best = result.get("best_composite", 0)
    
    lines = [
        "## 📊 分配方案审查摘要",
        "",
        "| 指标 | Seed 基线 | 最优方案 | 提升 |",
        "|------|----------|---------|------|",
        f"| 硬约束满足率 | {metrics.get('hard_satisfaction_ratio', 'N/A')} | — | — |",
        f"| 技能匹配率 | {metrics.get('skill_match_coverage', 'N/A')} | — | — |",
        f"| 工作负载均衡 | {metrics.get('workload_balance', 'N/A')} | — | — |",
        f"| 分配覆盖率 | {metrics.get('coverage', 'N/A')} | — | — |",
        f"| **综合分** | **{seed:.4f}** | **{best:.4f}** | **+{result.get('improvement_pct', 0):.1f}%** |",
        "",
    ]
    
    # 候选统计
    lines += [
        f"🧬 进化统计: 共 {result.get('generations', 0)} 代, "
        f"评估 {result.get('total_candidates', 0)} 个候选方案",
        "",
    ]
    
    return "\n".join(lines)


def get_agent_definition() -> dict:
    """返回 ADK Agent 定义"""
    return {
        "name": "assignment_reviewer",
        "display_name": "分配审查 Agent",
        "description": "审查 AlphaEvolve 生成的 TA 分配方案，辅助系主任做审批决策",
        "system_prompt": SYSTEM_PROMPT,
        "tools": [
            {
                "name": "load_evolution_result",
                "description": "读取进化引擎运行结果",
            },
            {
                "name": "compare_with_seed",
                "description": "对比 Seed 与最优方案指标",
            },
            {
                "name": "generate_summary_table",
                "description": "生成分配方案摘要",
            },
        ],
        "model": "gemini-3.5-flash",
        "temperature": 0.1,
    }


if __name__ == "__main__":
    result = load_evolution_result()
    print(generate_summary_table(result))
    print()
    print("Agent 定义:")
    import json
    print(json.dumps(get_agent_definition(), indent=2, ensure_ascii=False))
