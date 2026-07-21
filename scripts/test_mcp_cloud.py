#!/usr/bin/env python3
"""
MCP Cloud Run Endpoint 测试客户端
通过标准 MCP streamable-http 协议测试部署的 MCP server
"""
import httpx
import json
import sys
import re
import time

def test_mcp_endpoint(url: str, tool_name: str = None, tool_args: dict = None):
    """测试 MCP endpoint"""
    print(f"\n=== 测试 {url} ===")
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    
    # 用 stream 客户端
    with httpx.Client(timeout=30.0) as client:
        # 1. 初始化
        print("→ 初始化...")
        with client.stream("POST", f"{url}/mcp",
                          headers=headers,
                          json={"jsonrpc":"2.0","method":"initialize",
                                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                                          "clientInfo":{"name":"testcli","version":"1.0"}},
                                "id":1}) as resp:
            table = resp.headers
            session_id = table.get("mcp-session-id")
            print(f"  Session ID: {session_id[:16]}..." if session_id else "  ❌ 无 session")
            
            for line in resp.iter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    print(f"  Server: {data['result']['serverInfo']['name']} v{data['result']['serverInfo']['version']}")
                    break
        
        if not session_id:
            print("❌ 无法获取 session id")
            return False
        
        # 2. notifications/initialized
        print("→ 已初始化通知...")
        client.post(f"{url}/mcp",
                    headers={**headers, "MCP-Session-Id": session_id},
                    json={"jsonrpc":"2.0","method":"notifications/initialized"})
        
        # 3. tools/list
        print("→ 列出工具...")
        with client.stream("POST", f"{url}/mcp",
                          headers={**headers, "MCP-Session-Id": session_id},
                          json={"jsonrpc":"2.0","method":"tools/list","id":2}) as resp:
            for line in resp.iter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    tools = data["result"]["tools"]
                    print(f"  ✅ 发现 {len(tools)} 个工具:")
                    for t in tools:
                        print(f"     - {t['name']}: {t['description'][:60]}")
                    break
        
        # 4. 调用具体工具
        if tool_name:
            print(f"→ 调用 {tool_name}...")
            with client.stream("POST", f"{url}/mcp",
                              headers={**headers, "MCP-Session-Id": session_id},
                              json={"jsonrpc":"2.0","method":"tools/call",
                                    "params":{"name":tool_name,"arguments":tool_args or {}},
                                    "id":3}) as resp:
                for line in resp.iter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        if "result" in data:
                            content = data["result"].get("content", [])
                            for c in content:
                                if c.get("type") == "text":
                                    text = c["text"]
                                    try:
                                        parsed = json.loads(text)
                                        if isinstance(parsed, list):
                                            print(f"  ✅ 结果: {len(parsed)} 项")
                                            if parsed:
                                                print(f"     首项: {str(parsed[0])[:100]}")
                                        else:
                                            print(f"  ✅ 结果: {str(parsed)[:200]}")
                                    except:
                                        print(f"  ✅ 结果: {text[:200]}")
                        elif "error" in data:
                            print(f"  ❌ 错误: {data['error']['message']}")
                        break
    
    return True


if __name__ == "__main__":
    endpoints = {
        "data_retrieve": "https://mcp-data-retrieve-538412438779.us-central1.run.app",
    }
    
    if len(sys.argv) > 1:
        # 命令行传入 endpoint
        url = sys.argv[1]
        tool = sys.argv[2] if len(sys.argv) > 2 else None
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
        test_mcp_endpoint(url, tool, args)
    else:
        # 默认测试 data_retrieve
        for name, url in endpoints.items():
            test_mcp_endpoint(url, "list_courses")
