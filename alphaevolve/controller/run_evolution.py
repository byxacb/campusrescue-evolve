#!/usr/bin/env python3
"""
CampusRescue Evolve — AlphaEvolve Controller
=============================================
控制循环: 连接 Discovery Engine API，管理 AlphaEvolve 进化实验。
在 AlphaEvolve 服务可用时运行。

用法:
  python3 run_evolution.py --data-dir fixtures/ --programs 100
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_servers" / "evaluator_run"))
import importlib.util

# 用 importlib 加载 server.py 中的函数
_eval_server_path = Path(__file__).parent.parent.parent / "mcp_servers" / "evaluator_run" / "server.py"
_spec = importlib.util.spec_from_file_location("eval_server", _eval_server_path)
_eval_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_module)
evaluate_assignment = _eval_module.evaluate_assignment
run_seed = _eval_module.run_seed

# ── 配置 ──────────────────────────────────────────────

DEFAULT_CONFIG = {
    "project_id": os.environ.get("PROJECT_ID", "project-53bf8b85-eb44-4391-a2e"),
    "location": "global",         # AlphaEvolve 推荐用 global
    "collection": "default_collection",
    "engine_id": os.environ.get("ENGINE_ID", ""),
    "assistant": "default_assistant",
    
    # 进化预算
    "max_programs": 100,          # 总候选数（含 seed）
    "concurrency": 5,             # 并行 candidate 数
    "max_generations": 50,        # 最大代数
    "idle_timeout_seconds": 300,  # 无新候选时等待
}


# ── 种子运行器 ────────────────────────────────────────

def run_seed_and_evaluate(data_dir: str) -> dict:
    """先运行 seed，返回基线分数"""
    print(f"[{datetime.now().isoformat()}] 🏃 运行 seed 算法...")
    
    # 直接调用 evaluator.run MCP 的 run_seed 函数
    seed_data_dir = str(Path(__file__).parent.parent.parent / data_dir)
    result = run_seed(seed_data_dir)
    
    print(f"  ✅ Seed 分配: {result['summary']['assigned_courses']}/{result['summary']['total_courses']} 门课程")
    print(f"  📊 基线分数: {result['scores']}")
    print(f"  💡 综合分: {result['summary']['composite_score']}")
    
    return result


# ── 本地进化模拟 ──────────────────────────────────────

def run_local_evolution(data_dir: str, config: dict) -> dict:
    """
    当 AlphaEvolve 服务不可用时，在本地运行简单的进化模拟。
    模拟 mutation + selection + crossover 的基本循环。
    """
    from copy import deepcopy
    import random
    random.seed(42)
    
    seed_path = Path(__file__).parent / "seed" / "greedy_assign.py"
    data_path = Path(__file__).parent.parent / data_dir
    
    # 运行 seed 获取基线
    baseline = run_seed_and_evaluate(data_dir)
    best_scores = baseline["scores"]
    best_composite = baseline["summary"]["composite_score"]
    
    print(f"\n[{datetime.now().isoformat()}] 🧬 开始进化模拟 (max {config['max_programs']} programs)")
    
    generation = 0
    candidates_generated = 1  # seed 算第一个
    best_assignments = None
    all_candidates = []
    
    # 用 eval 导入 seed 模块并做简单变异
    sys.path.insert(0, str(seed_path.parent))
    from greedy_assign import greedy_assign, _load_tas as seed_load_tas, _load_courses as seed_load_courses
    
    absolute_data_path = Path(__file__).parent.parent.parent / data_dir
    tas = seed_load_tas(str(absolute_data_path / "tas.csv"))
    courses = seed_load_courses(str(absolute_data_path / "courses.csv"))
    str_data_dir = str(absolute_data_path)  # 用于传递给 evaluator
    
    while candidates_generated < config["max_programs"] and generation < config["max_generations"]:
        generation += 1
        gen_candidates = 0
        
        for _ in range(min(config["concurrency"], config["max_programs"] - candidates_generated)):
            # 简单变异: 随机调整分配策略
            try:
                # 复制并变异 seed 参数
                modified_tas = deepcopy(tas)
                random.shuffle(modified_tas)  # 改变 TA 顺序
                
                assignments = greedy_assign(modified_tas, courses)
                candidates_generated += 1
                gen_candidates += 1
                
                # 评估
                assignments_json = json.dumps(assignments)
                result = evaluate_assignment(assignments_json, str_data_dir)
                
                composite = result["summary"]["composite_score"]
                all_candidates.append({
                    "generation": generation,
                    "candidate_id": candidates_generated,
                    "composite_score": composite,
                    "scores": result["scores"],
                    "assigned_count": result["summary"]["assigned_courses"],
                })
                
                if composite > best_composite:
                    best_composite = composite
                    best_scores = result["scores"]
                    best_assignments = assignments
                    print(f"  ✨ 第 {generation} 代/{candidates_generated}: 新最优! 综合分 {composite:.4f}")
                
            except Exception as e:
                print(f"  ⚠️ 候选 {candidates_generated} 失败: {e}")
                continue
        
        if gen_candidates == 0:
            print(f"  ⏸️ 第 {generation} 代无有效候选，停止")
            break
    
    # 输出最终结果
    result = {
        "seed_composite": baseline["summary"]["composite_score"],
        "best_composite": best_composite,
        "improvement": round(best_composite - baseline["summary"]["composite_score"], 4),
        "improvement_pct": round(
            (best_composite - baseline["summary"]["composite_score"]) / max(baseline["summary"]["composite_score"], 0.001) * 100, 2
        ),
        "generations": generation,
        "total_candidates": candidates_generated,
        "best_scores": best_scores,
        "best_assignments": best_assignments,
        "all_candidates": all_candidates,
    }
    
    print(f"\n{'='*50}")
    print(f"🏆 进化完成!")
    print(f"  Seed 综合分: {result['seed_composite']:.4f}")
    print(f"  最优综合分:  {result['best_composite']:.4f}")
    print(f"  提升:         +{result['improvement_pct']}%")
    print(f"  代数:         {generation}")
    print(f"  候选总数:     {candidates_generated}")
    print(f"{'='*50}")
    
    # 写结果
    output_path = Path("evolution_result.json")
    with open(output_path, "w") as f:
        json.dump({k: v for k, v in result.items() if k != "best_assignments"}, f, indent=2)
    
    if best_assignments:
        with open("best_assignments.json", "w") as f:
            json.dump(best_assignments, f, indent=2)
        print(f"  最优方案写入: best_assignments.json")
    
    return result


# ── 主函数 ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CampusRescue Evolve - AlphaEvolve Controller")
    parser.add_argument("--data-dir", default="fixtures/", help="数据目录")
    parser.add_argument("--programs", type=int, default=100, help="候选总数上限")
    parser.add_argument("--generations", type=int, default=50, help="最大代数")
    parser.add_argument("--concurrency", type=int, default=5, help="并行数")
    parser.add_argument("--mode", choices=["seed", "evolve", "full"], default="full",
                        help="运行模式: seed 仅基线, evolve 仅进化, full 完整流程")
    args = parser.parse_args()
    
    config = {**DEFAULT_CONFIG,
              "max_programs": args.programs,
              "max_generations": args.generations,
              "concurrency": args.concurrency}
    
    print(f"🚀 CampusRescue Evolve — AlphaEvolve 控制器")
    print(f"   数据目录: {args.data_dir}")
    print(f"   模式:     {args.mode}")
    print(f"\n{'='*50}")
    
    if args.mode in ("seed", "full"):
        baseline = run_seed_and_evaluate(args.data_dir)
        
    if args.mode in ("evolve", "full"):
        result = run_local_evolution(args.data_dir, config)
        return result
    
    return {"status": "completed"}


if __name__ == "__main__":
    main()
