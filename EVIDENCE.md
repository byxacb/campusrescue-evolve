# Live Evidence — CampusRescue Evolve 评委一键 Self-Audit

> 本文档让任何评审 / 评委都能在 5 分钟内独立验证整套系统在 GCP 上跑通。
> 所有命令 PowerShell / bash 通用，无需 GUI 点击。
> 最后更新：2026-07-23

---

## 0. 前置准备

```bash
# 登录 GCP（已登录可跳过）
gcloud auth login
gcloud config set project project-53bf8b85-eb44-4391-a2e
```

---

## 1. Reasoning Engine 在线？

```bash
gcloud ai reasoning-engines list \
  --project=project-53bf8b85-eb44-4391-a2e \
  --region=us-west1 \
  --format="table(name,displayName)"
```

期望看到 1 条：
```
NAME                                                  DISPLAYNAME
projects/538412438779/locations/us-west1/reasoningEngines/2073459027659980800  CampusRescueOrchestrator
```

---

## 2. Reasoning Engine 真能 stream_query？

```bash
cd firebird-entry
source .venv/bin/activate
python3 run_demo.py "请用一句话介绍你自己和5阶段工作流"
```

期望：终端打印 `=== Reasoning Engine: 2073459027659980800 ===`，并以 `=== total events: N ===` 结尾。模型回答问题的文本会以 `text=` 形式出现。

---

## 3. 5 个 BYO-MCP 在线？

```bash
gcloud run services list \
  --project=project-53bf8b85-eb44-4391-a2e \
  --region=us-central1 \
  --filter="metadata.name:mcp-" \
  --format="table(name,reachable)"
```

期望 5 行全 REACHABLE_YES：
- mcp-data-retrieve
- mcp-evaluator-run
- mcp-audit-report
- mcp-hardagents-compile
- mcp-campusflow-run

---

## 4. MCP 协议握手？

```bash
URL="https://mcp-audit-report-5l3z4bmblq-uc.a.run.app"
SESSION=$(curl -s -i -X POST "$URL/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"audit","version":"1.0"}}}' \
  | grep -i "mcp-session-id" | awk '{print $2}' | tr -d '\r\n')
echo "Session: $SESSION"

curl -s -X POST "$URL/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Session-Id: $SESSION" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2}' | head -c 800
```

期望：拿到 session id，看到 6 个工具：`list_runs / get_run / replay / get_stats / export_to_sheets / send_notification`。

---

## 5. Agent Registry 已注册？

```bash
gcloud agent-registry agents list \
  --project=project-53bf8b85-eb44-4391-a2e \
  --location=us-central1 \
  --format="value(displayName)" | grep CampusRescue
```

期望 4 行：
```
CampusRescueOrchestrator
CampusRescueTAProfileCollector
CampusRescueEvolutionAgent
CampusRescueAssignmentReviewer
```

---

## 6. Cloud Scheduler 在跑？

```bash
gcloud scheduler jobs describe campusrescue-hourly-cycle \
  --project=project-53bf8b85-eb44-4391-a2e \
  --location=us-central1 \
  --format="value(state, schedule)"
```

期望：`ENABLED  0 * * * *`

```bash
# 手动触发一次（200 = 成功调通 RE）
curl -s -o /tmp/sched.txt -w "HTTP %{http_code}\n" -X POST \
  "https://campusrescue-scheduler-538412438779.us-central1.run.app" \
  -H "Content-Type: application/json" -d '{}'
cat /tmp/sched.txt
```

期望：`HTTP 200` + JSON 返回 `engine_id / session_id / events`。

---

## 7. Google Workspace 集成？

```bash
gcloud services list \
  --project=project-53bf8b85-eb44-4391-a2e \
  --enabled \
  --filter="name:sheets.googleapis.com OR name:gmail.googleapis.com" \
  --format="value(config.name)"
```

期望 2 行：
```
gmail.googleapis.com
sheets.googleapis.com
```

工具实现：见 [mcp_servers/audit_report/server.py](mcp_servers/audit_report/server.py) 的 `export_to_sheets` 与 `send_notification`。

---

## 8. Git 历史？

```bash
cd firebird-entry
git log --oneline -5
```

期望看到：
```
8ad580f feat: workspace integration + final RE deploy
9334716 feat: v1.1 - Vertex AI Reasoning Engine deploy + endpoint test
c957253 feat: delivery v1.0 - CampusRescue Evolve complete
5683619 feat: Firebird Hackathon entry - AlphaEvolve + BYO-MCP + Agent Designer
```

---

## 9. 本地代码可 import？

```bash
cd firebird-entry
source .venv/bin/activate
python3 -c "
from agent_platform.agent_designer_code import root_agent
print('Agent:', root_agent.name)
print('Sub-agents:', [a.name for a in (root_agent.sub_agents or [])])
"
```

期望看到 3 个子代理名称。

---

## 10. 文档对应？

- [README.md](README.md) — Top-level 项目介绍 + Live Status
- [agent-designer-setup-guide.md](agent-designer-setup-guide.md) — Agent Designer UI 配置指引
- [EVIDENCE.md](EVIDENCE.md) — 本文档，评委一键 self-audit
- [deploy_adk_to_vertex.py](deploy_adk_to_vertex.py) — 部署脚本
- [run_demo.py](run_demo.py) — 评委 demo 脚本

---

## 已知限制（不影响评分）

1. **Agent Designer UI 的 Deploy 按钮**：Google 内部模板缺 `mcp` 包，部署会失败。本仓库不走 UI Deploy，直接用 Python ADK 创建 ReasoningEngine。已在 README "Agent Designer UI Deploy 失败的官方修复路径" 详述。
2. **Agent Registry PATCH endpoint**：REST `PATCH /v1/.../agents/{id}` 返回 404；gcloud CLI 也无 update 命令。Registry 条目由 Google 内部自动化系统创建，不可手动改 protocol/interface URL。这是 Google 产品现状，与本项目无关。
3. **IAM propagation 时延**：授予 `roles/aiplatform.admin` 后约 30-60s 才生效。Cloud Scheduler 第一次跑可能仍 500。
4. **Agent Designer 画布上 3 个子代理的 detail**：需要在 UI 上手动填（指令、模型、MCP 绑定）。整个 system 已能不依赖画布运行。
