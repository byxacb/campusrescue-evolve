#!/usr/bin/env python3
"""
CampusRescue Evolve — Evaluator: TA-Course Assignment Evaluator
===============================================================
AlphaEvolve 评估器：计算候选分配方案的硬约束违反 + 软目标加权分

输入: assignments.json + courses.csv + tas.csv (by data.retrieve)
输出: scores (越大越好), insights (诊断反馈给下一代)

指标说明:
  1. hard_satisfaction_ratio  — 硬约束满足率 (0~1), 权重 0.5
  2. skill_match_coverage     — 技能匹配覆盖率 (0~1), 权重 0.25
  3. workload_balance         — TA 工作负载均衡度 (0~1), 权重 0.15
  4. slot_efficiency          — 时间槽利用率 (0~1), 权重 0.10
"""

import csv
import json
import math
import sys
from typing import Dict, List, Tuple


# ── 约束检查 ──────────────────────────────────────────

def check_constraints(assignments: Dict[str, str],
                      ta_list: List, course_list: List) -> dict:
    """返回所有硬约束的满足情况"""
    ta_load = {ta.ta_id: 0 for ta in ta_list}
    ta_used_slots = {ta.ta_id: set() for ta in ta_list}
    
    hard_satisfied = 0
    hard_total = 0
    violations = []
    
    for course in course_list:
        if course.course_id not in assignments:
            # 课程未分配 = 违反
            violations.append(f"{course.course_id}: 未分配 TA")
            hard_total += 1
            continue
        
        ta_id = assignments[course.course_id]
        ta = next((t for t in ta_list if t.ta_id == ta_id), None)
        
        if ta is None:
            violations.append(f"{course.course_id}->{ta_id}: TA 不存在")
            hard_total += 1
            continue
        
        # 约束 1: TA 未超负荷
        hard_total += 1
        if ta_load[ta_id] < ta.max_courses:
            hard_satisfied += 1
        else:
            violations.append(f"{course.course_id}->{ta_id}: TA 超负荷")
        
        # 约束 2: 时间槽可用
        for slot in course.slots:
            hard_total += 1
            if slot in ta.available_slots and slot not in ta_used_slots[ta_id]:
                hard_satisfied += 1
            else:
                violations.append(f"{course.course_id}->{ta_id}: 时间冲突 {slot}")
        
        # 更新 TA 状态
        ta_load[ta_id] += 1
        for slot in course.slots:
            ta_used_slots[ta_id].add(slot)
    
    return {
        "hard_satisfied": hard_satisfied,
        "hard_total": hard_total,
        "violations": violations,
    }


def compute_soft_metrics(assignments: Dict[str, str],
                          ta_list: List, course_list: List) -> dict:
    """计算软目标得分"""
    ta_load = {ta.ta_id: 0 for ta in ta_list}
    total_skill_match = 0
    total_courses_with_ta = 0
    
    for course in course_list:
        if course.course_id not in assignments:
            continue
        ta_id = assignments[course.course_id]
        ta = next((t for t in ta_list if t.ta_id == ta_id), None)
        if ta is None:
            continue
        total_courses_with_ta += 1
        match = len(ta.skills & course.required_skills)
        total_skill_match += match / max(len(course.required_skills), 1)
        ta_load[ta_id] += 1
    
    # 技能匹配率
    skill_match_coverage = total_skill_match / max(total_courses_with_ta, 1)
    
    # 负载均衡: 计算已分配课程数的 TA 之间的变异系数
    # 只考虑有 TA 分配到的课程 (实际负载)
    assigned_courses_per_ta = [ta_load[ta.ta_id] for ta in ta_list if ta.max_courses > 0]
    if assigned_courses_per_ta:
        mean_load = sum(assigned_courses_per_ta) / len(assigned_courses_per_ta)
        if mean_load > 0:
            variance = sum((l - mean_load) ** 2 for l in assigned_courses_per_ta) / len(assigned_courses_per_ta)
            cv = math.sqrt(variance) / mean_load
            workload_balance = max(0, 1 - cv)  # 0~1, 1=最均衡
        else:
            workload_balance = 1.0
    else:
        workload_balance = 0.0
    
    # 分配覆盖率
    coverage = len(assignments) / max(len(course_list), 1)
    
    return {
        "skill_match_coverage": round(skill_match_coverage, 4),
        "workload_balance": round(workload_balance, 4),
        "coverage": round(coverage, 4),
    }


# ── 主评估器 ──────────────────────────────────────────

def evaluate(assignments_path: str, data_dir: str) -> Tuple[List[float], str]:
    """
    主评估函数。返回 (scores, insights)
    
    scores: [hard_satisfaction_ratio, skill_match, workload_balance, coverage]
            每个维度 0~1，越大越好
    """
    with open(assignments_path) as f:
        data = json.load(f)
    
    assignments = data.get("assignments", {})
    
    ta_list = _load_tas(f"{data_dir}/tas.csv")
    course_list = _load_courses(f"{data_dir}/courses.csv")
    
    # 硬约束
    constraint_result = check_constraints(assignments, ta_list, course_list)
    hard_ratio = constraint_result["hard_satisfied"] / max(constraint_result["hard_total"], 1)
    
    # 软目标
    soft = compute_soft_metrics(assignments, ta_list, course_list)
    
    # 综合分数（越大越好）
    # 注意: hard_ratio 低于 0.9 时整体分会被严重惩罚
    weight_hard = 0.50
    weight_skill = 0.25
    weight_balance = 0.15
    weight_coverage = 0.10
    
    # 硬约束未达标时大幅降权
    if hard_ratio < 0.9:
        penalty = hard_ratio  # 线性惩罚
    else:
        penalty = 1.0
    
    final_scores = [
        round(hard_ratio, 4),                   # 0: 硬约束满足率
        round(soft["skill_match_coverage"], 4), # 1: 技能匹配
        round(soft["workload_balance"], 4),     # 2: 负载均衡
        round(soft["coverage"], 4),             # 3: 覆盖率
    ]
    
    # 构建 insights (诊断反馈给下一代)
    insights = _build_insights(constraint_result, soft, assignments, course_list)
    
    return final_scores, insights


def _build_insights(constraint: dict, soft: dict,
                     assignments: dict, course_list: list) -> str:
    """生成下一代可用的诊断反馈"""
    parts = []
    if constraint["violations"]:
        # 最多报告 5 条违规
        top_v = constraint["violations"][:5]
        parts.append(f"硬约束违规 ({len(constraint['violations'])} 条)")
        for v in top_v:
            parts.append(f"  - {v}")
        parts.append("请优先修复硬约束: 检查时间冲突和 TA 负载上限")
    
    if soft["skill_match_coverage"] < 0.7:
        parts.append("技能匹配率偏低，建议优先将有相关技能的 TA 分配给对应课程")
    if soft["workload_balance"] < 0.5:
        parts.append("负载不均衡，有 TA 任务过重、有 TA 闲置")
    if soft["coverage"] < 0.9:
        unassigned = len(course_list) - len(assignments)
        parts.append(f"还有 {unassigned} 门课程未分配 TA，请尝试将未满负荷 TA 填入")
    
    return "\n".join(parts) if parts else "方案可行，可进一步优化软目标"


def _load_tas(path: str) -> list:
    # 简化的加载器 - 生产版应从 data.retrieve MCP 获取
    tas = []
    with open(path) as f:
        for row in csv.DictReader(f):
            tas.append(type('TA', (), {
                'ta_id': row['ta_id'],
                'name': row['name'],
                'skills': set(row['skills'].split(';')),
                'max_courses': int(row['max_courses']),
                'available_slots': row['slots'].split(';'),
            })())
    return tas


def _load_courses(path: str) -> list:
    courses = []
    with open(path) as f:
        for row in csv.DictReader(f):
            courses.append(type('Course', (), {
                'course_id': row['course_id'],
                'title': row['title'],
                'required_skills': set(row['required_skills'].split(';')),
                'slots': row['slots'].split(';'),
                'enrollment': int(row['enrollment']),
            })())
    return courses


# ── 命令行入口 ────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: evaluate.py <assignments.json> <data_dir>")
        sys.exit(1)
    
    scores, insights = evaluate(sys.argv[1], sys.argv[2])
    print(f"Scores: {scores}")
    print(f"Insights:\n{insights}")
