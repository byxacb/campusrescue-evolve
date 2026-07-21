import httpx, json, sys

urls = {
    "data_retrieve": "https://mcp-data-retrieve-5l3z4bmblq-uc.a.run.app",
    "evaluator_run": "https://mcp-evaluator-run-5l3z4bmblq-uc.a.run.app",
    "audit_report": "https://mcp-audit-report-5l3z4bmblq-uc.a.run.app",
    "hardagents_compile": "https://mcp-hardagents-compile-5l3z4bmblq-uc.a.run.app",
    "campusflow_run": "https://mcp-campusflow-run-5l3z4bmblq-uc.a.run.app",
}

headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
init = {"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}

all_ok = True
for name, base in urls.items():
    try:
        with httpx.Client(timeout=10) as c:
            r = c.post(f"{base}/mcp", headers=headers, json=init)
            session = r.headers.get("mcp-session-id","")
            ok = session != "" and r.status_code == 200
            print(f"  {'✅' if ok else '❌'} {name}: {base}")
            if ok:
                sys.stdout.flush()
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        all_ok = False

print(f"\n{'='*40}")
print(f"全部 {'通过' if all_ok else '有失败'}!")
