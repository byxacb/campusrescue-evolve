"""Curriculum Alignment Skill — 可复用领域技能。

被 CampusRescueEvolutionAgent 在每代进化中调用，对当前 TA×课程组合做技能匹配评估。
也为 AssignmentReviewer 在审批时复用，形成"评估→进化→再评估"的闭环。

可独立用 Python 包 import，也可作为 MCP tool 包装到 audit.report 之外的二号 MCP。
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import json
from pathlib import Path

# 核心技能 → 权重倍率（从 1.0 到 weight_core_skills）
CORE_SKILL_BOOST = {
    "Python": 2.0, "Statistics": 1.8, "ML": 1.8, "DataAnalysis": 1.5,
    "Java": 1.5, "WebDevelopment": 1.2, "Database": 1.2,
    "NLP": 1.5, "ComputerVision": 1.5, "R": 1.3,
}

def _normalize(s: str) -> str:
    return (s or "").strip().lower().replace("_", "").replace("-", "")

def _skill_match(req: str, have: str) -> bool:
    a, b = _normalize(req), _normalize(have)
    if not a or not b:
        return False
    if a == b:
        return True
    # 容忍 "ml" vs "machinelearning"
    aliases = {
        "ml": {"machinelearning"},
        "ai": {"artificialintelligence"},
        "nlp": {"naturallanguageprocessing"},
        "cv": {"computervision"},
    }
    if a in aliases and b in aliases[a]:
        return True
    if b in aliases and a in aliases[b]:
        return True
    return a in b or b in a

def align_curriculum(course_syllabi: List[Dict[str, Any]],
                     ta_profiles: List[Dict[str, Any]],
                     options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """对齐课程需求与 TA 技能，返回匹配矩阵 + 缺口 + 建议。"""
    opts = options or {}
    min_match = float(opts.get("min_match_score", 0.3))
    core_w = float(opts.get("weight_core_skills", 2.0))
    
    match_matrix: List[Dict[str, Any]] = []
    coverage: Dict[str, List[Dict[str, Any]]] = {}
    
    for course in course_syllabi:
        cid = course["course_id"]
        req_skills = course["required_skills"]
        for ta in ta_profiles:
            tid = ta["ta_id"]
            ta_skills = ta["skills"]
            
            matched, missing = [], []
            weighted_total, achieved = 0.0, 0.0
            for r in req_skills:
                w = CORE_SKILL_BOOST.get(r, 1.0) * (core_w if r in CORE_SKILL_BOOST else 1.0)
                weighted_total += w
                if any(_skill_match(r, h) for h in ta_skills):
                    matched.append(r)
                    achieved += w
                else:
                    missing.append(r)
            
            score = (achieved / weighted_total) if weighted_total > 0 else 0.0
            if score >= min_match:
                match_matrix.append({
                    "course_id": cid, "ta_id": tid,
                    "match_score": round(score, 4),
                    "matched_skills": matched, "missing_skills": missing,
                })
                coverage.setdefault(cid, []).append({"ta_id": tid, "score": score})
    
    # 缺口分析
    gaps: List[Dict[str, Any]] = []
    for course in course_syllabi:
        cid = course["course_id"]
        cov = coverage.get(cid, [])
        if not cov:
            unmatched = course["required_skills"]
            severity = "critical" if len(unmatched) >= 3 else (
                "moderate" if len(unmatched) == 2 else "low"
            )
            gaps.append({
                "course_id": cid,
                "gap_severity": severity,
                "unmatched_skills": unmatched,
            })
    
    # 建议
    recs: List[str] = []
    if gaps:
        recs.append(f"识别到 {len(gaps)} 门课程存在技能缺口；建议补招 TA 或调整课程需求。")
    if any(m["match_score"] >= 0.85 for m in match_matrix):
        recs.append("存在高匹配度 (≥0.85) 的 TA×课程对，进化引擎应优先锁定这些组合。")
    if not recs:
        recs.append("所有课程都有至少一个匹配度 ≥0.3 的 TA，可以进入进化阶段。")
    
    return {
        "match_matrix": match_matrix,
        "coverage_gaps": gaps,
        "recommendations": recs,
        "stats": {
            "total_courses": len(course_syllabi),
            "total_tas": len(ta_profiles),
            "compatible_pairs": len(match_matrix),
            "avg_match_score": (
                sum(m["match_score"] for m in match_matrix) / len(match_matrix)
                if match_matrix else 0.0
            ),
        },
    }

if __name__ == "__main__":
    import sys
    # CLI: python curriculum_alignment.py courses.json tas.json
    if len(sys.argv) >= 3:
        courses = json.loads(Path(sys.argv[1]).read_text())
        tas = json.loads(Path(sys.argv[2]).read_text())
        result = align_curriculum(courses, tas)
        print(json.dumps(result, ensure_ascii=False, indent=2))
