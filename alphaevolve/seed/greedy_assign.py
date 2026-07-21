"""
CampusRescue Evolve — Seed Program: GreedyAssigner
=================================================
AlphaEvolve 基线种子程序：贪心算法做 TA-课程分配

输入: courses.csv, tas.csv (由 data.retrieve MCP 提供)
输出: assignments.json (TA -> 课程映射表)
目标: 硬约束全部满足的前提下，最大化软目标加权分

# EVOLVE-BLOCK-START
# AlphaEvolve 将在此区域内改写分配逻辑
# EVOLVE-BLOCK-END
"""

import csv
import json
import sys
from typing import Dict, List, Tuple


# ── 数据类型 ──────────────────────────────────────────
class TA:
    def __init__(self, ta_id: str, name: str, skills: List[str],
                 max_courses: int, available_slots: List[str]):
        self.ta_id = ta_id
        self.name = name
        self.skills = set(skills)
        self.max_courses = max_courses
        self.available_slots = available_slots  # e.g., ["Mon-09:00", "Mon-10:00"]


class Course:
    def __init__(self, course_id: str, title: str, required_skills: List[str],
                 slots: List[str], enrollment: int):
        self.course_id = course_id
        self.title = title
        self.required_skills = set(required_skills)
        self.slots = slots
        self.enrollment = enrollment


# ── 种子算法：贪心分配 ──────────────────────────────
def greedy_assign(ta_list: List[TA], course_list: List[Course]
                  ) -> Dict[str, str]:
    """
    按课程优先级（大班优先）贪心分配 TA。
    AlphaEvolve 将对此函数进行变异和优化。
    
    返回: {course_id: ta_id}
    """
    # EVOLVE-BLOCK-START
    # AlphaEvolve 将在此区域内改写分配逻辑。
    # 当前 seed: 简单贪心 - 按 enrollment 降序、技能匹配评分、负载加权。
    # 改进方向: 启发式打分函数、回溯、模拟退火、整数规划、组合优化。
    
    # 按 enrollment 降序排列课程（大课优先分配）
    sorted_courses = sorted(course_list, key=lambda c: -c.enrollment)
    
    # 跟踪每个 TA 已分配课程数
    ta_load: Dict[str, int] = {ta.ta_id: 0 for ta in ta_list}
    # 跟踪每个 TA 已占用的时间槽
    ta_used_slots: Dict[str, set] = {ta.ta_id: set() for ta in ta_list}
    
    assignments: Dict[str, str] = {}
    
    for course in sorted_courses:
        best_ta = None
        best_score = -1
        
        for ta in ta_list:
            # 硬约束 1: TA 未超负荷
            if ta_load[ta.ta_id] >= ta.max_courses:
                continue
            
            # 硬约束 2: 课程所有时间槽 TA 都可用
            slot_conflict = False
            for slot in course.slots:
                if slot not in ta.available_slots:
                    slot_conflict = True
                    break
            if slot_conflict:
                continue
            
            # 硬约束 3: TA 已有分配不与课程时间冲突
            for slot in course.slots:
                if slot in ta_used_slots[ta.ta_id]:
                    slot_conflict = True
                    break
            if slot_conflict:
                continue
            
            # 软目标: 技能匹配度
            skill_overlap = len(ta.skills & course.required_skills)
            if skill_overlap == 0:
                continue  # 至少匹配一个技能
            
            # 评分: 技能匹配数 - 当前负载（偏好负载轻的 TA）
            score = skill_overlap * 10 - ta_load[ta.ta_id]
            
            if score > best_score:
                best_score = score
                best_ta = ta.ta_id
        
        if best_ta:
            assignments[course.course_id] = best_ta
            ta_load[best_ta] += 1
            for slot in course.slots:
                ta_used_slots[best_ta].add(slot)
        # 如无 TA 可用则该课程留空（后期由 AlphaEvolve 改进）
    
    return assignments


# ── 主函数 ────────────────────────────────────────────
def main(data_dir: str):
    """加载数据并运行 seed 分配算法"""
    ta_list = _load_tas(f"{data_dir}/tas.csv")
    course_list = _load_courses(f"{data_dir}/courses.csv")
    
    result = greedy_assign(ta_list, course_list)
    
    with open("assignments.json", "w") as f:
        json.dump({
            "algorithm": "greedy_assign",
            "assignments": result,
            "assigned_count": len(result),
            "unassigned_courses": len(course_list) - len(result),
        }, f, indent=2)
    
    print(f"✅ 分配完成: {len(result)}/{len(course_list)} 门课程已分配 TA")


def _load_tas(path: str) -> List[TA]:
    tas = []
    with open(path) as f:
        for row in csv.DictReader(f):
            tas.append(TA(
                ta_id=row["ta_id"],
                name=row["name"],
                skills=row["skills"].split(";"),
                max_courses=int(row["max_courses"]),
                available_slots=row["slots"].split(";"),
            ))
    return tas


def _load_courses(path: str) -> List[Course]:
    courses = []
    with open(path) as f:
        for row in csv.DictReader(f):
            courses.append(Course(
                course_id=row["course_id"],
                title=row["title"],
                required_skills=row["required_skills"].split(";"),
                slots=row["slots"].split(";"),
                enrollment=int(row["enrollment"]),
            ))
    return courses


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
