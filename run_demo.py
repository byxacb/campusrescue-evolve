"""CampusRescueOrchestrator 评委 demo 一键脚本。

用法:
    cd firebird-entry
    source .venv/bin/activate
    python3 run_demo.py            # 默认一句话自我介绍
    python3 run_demo.py "请跑一遍 5 阶段工作流"  # 自定义 query

产出:
    /tmp/campusrun_demo_out.json   —— 结构化结果
    /tmp/campusrun_demo.log        —— 完整事件日志
"""
import json
import sys
import vertexai
from vertexai import agent_engines

PROJECT = "project-53bf8b85-eb44-4391-a2e"
LOCATION = "us-west1"
STAGING_BUCKET = f"gs://{PROJECT}-adk-staging"
ENGINE_ID = "2073459027659980800"

def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "请用一句话介绍你自己和5阶段工作流"
    print(f"=== Reasoning Engine: {ENGINE_ID} ===")
    print(f"=== Query: {query} ===\n")

    vertexai.init(project=PROJECT, location=LOCATION, staging_bucket=STAGING_BUCKET)
    ae = agent_engines.AgentEngine(
        f"projects/538412438779/locations/us-west1/reasoningEngines/{ENGINE_ID}"
    )
    sess = ae.create_session(user_id="demo_user")
    print(f"=== SID: {sess['id']} ===\n")

    events = []
    for ev in ae.stream_query(user_id="demo_user", session_id=sess["id"], message=query):
        events.append(ev)
        s = str(ev)
        if len(s) > 600:
            s = s[:600] + "..."
        print(f"[ev {len(events)}] {s}\n")
        if len(events) >= 15:
            print("...capped at 15 events")
            break

    print(f"\n=== total events: {len(events)} ===")

    out = {
        "engine_id": ENGINE_ID,
        "session_id": sess["id"],
        "query": query,
        "events_count": len(events),
        "first_event_type": type(events[0]).__name__ if events else "none",
        "first_event_str": str(events[0])[:1000] if events else "",
    }
    with open("/tmp/campusrun_demo_out.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("=== saved /tmp/campusrun_demo_out.json ===")

if __name__ == "__main__":
    main()
