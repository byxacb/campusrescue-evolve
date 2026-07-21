"""
BYO-MCP #1: data.retrieve
=========================
读取课程和 TA 数据，提供给 AlphaEvolve agent / 其他 MCP server 调用

工具集:
  - course.list     → 列出所有课程
  - course.get      → 获取单个课程详情
  - ta.list         → 列出所有 TA
  - ta.get          → 获取单个 TA 详情
  - data.load       → 加载完整数据集 (csv → json)

部署: Streamable HTTP, Cloud Run
"""

from fastmcp import FastMCP
import csv
import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "./fixtures"))

mcp = FastMCP(
    name="data.retrieve",
    version="0.1.0",
)


def _load_tas():
    tas = []
    path = DATA_DIR / "tas.csv"
    if not path.exists():
        return tas
    with open(path) as f:
        for row in csv.DictReader(f):
            tas.append({
                "ta_id": row["ta_id"],
                "name": row["name"],
                "skills": row["skills"].split(";"),
                "max_courses": int(row["max_courses"]),
                "available_slots": row["slots"].split(";"),
            })
    return tas


def _load_courses():
    courses = []
    path = DATA_DIR / "courses.csv"
    if not path.exists():
        return courses
    with open(path) as f:
        for row in csv.DictReader(f):
            courses.append({
                "course_id": row["course_id"],
                "title": row["title"],
                "required_skills": row["required_skills"].split(";"),
                "slots": row["slots"].split(";"),
                "enrollment": int(row["enrollment"]),
            })
    return courses


@mcp.tool()
def list_courses() -> list[dict]:
    """列出所有课程，返回完整字段"""
    return _load_courses()


@mcp.tool()
def get_course(course_id: str) -> dict | None:
    """获取单个课程详情"""
    for c in _load_courses():
        if c["course_id"] == course_id:
            return c
    return None


@mcp.tool()
def list_tas() -> list[dict]:
    """列出所有 TA，返回完整字段"""
    return _load_tas()


@mcp.tool()
def get_ta(ta_id: str) -> dict | None:
    """获取单个 TA 详情"""
    for t in _load_tas():
        if t["ta_id"] == ta_id:
            return t
    return None


@mcp.tool()
def load_dataset() -> dict:
    """加载完整数据集，返回 {courses:[], tas:[]}"""
    return {
        "courses": _load_courses(),
        "tas": _load_tas(),
        "counts": {
            "courses": len(_load_courses()),
            "tas": len(_load_tas()),
        },
    }


@mcp.tool()
def list_unassigned_courses(assignments: dict) -> list[dict]:
    """给定 assignments 字典 {course_id: ta_id}，返回未分配 TA 的课程列表"""
    assigned = set(assignments.keys())
    return [c for c in _load_courses() if c["course_id"] not in assigned]


if __name__ == "__main__":
    import os
    
    port = int(os.environ.get("PORT", "8080"))
    
    # Streamable HTTP 模式
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        log_level="INFO",
    )
