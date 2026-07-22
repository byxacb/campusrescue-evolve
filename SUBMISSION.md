# CampusRescue Evolve — Firebird 参赛提交包

> **命题方向**: Google TRACK.01 Example 2 — No-Code Autonomous Workflows
> **团队项目**: 系主任救火队员 — AlphaEvolve + Agent Designer + BYO-MCP 智能 TA 分配系统
> **GitHub**: https://github.com/byxacb/campusrescue-evolve
> **提交日期**: 2026-07-23

---

## 1. 产品简介

每学期开始前，系主任要把 N 个 TA 分配到 M 门课程，需同时满足硬约束（TA 不超负荷 / 时间不冲突 / 技能匹配 / TA 必须存在）和软目标（技能匹配最大化 / 负载均衡 / 分配覆盖率 / 时间利用率）。

这是 NP-hard 组合优化问题。**CampusRescue Evolve** 用 AlphaEvolve 进化引擎自动迭代优化分配算法，通过 Agent Designer Flow 编排人工审批，BYO-MCP 把内部工具封装为可治理的资源。

---

## 2. 系统架构

```
  [系主任 / 评委] 
        │ run_demo.py / Agent Designer UI
        ▼
  ┌─────────────────────────────────────┐
  │  Vertex AI Reasoning Engine         │
  │  (CampusRescueOrchestrator)         │
  │  ┌─ TAProfileCollector              │
  │  ├─ EvolutionAgent  (AlphaEvolve)   │
  │  └─ AssignmentReviewer              │
  └──────┬──────────────────────────────┘
         │ 5 BYO-MCP endpoints
         ▼
  ┌─────────────────────────────────────┐
  │  5 Cloud Run MCP Servers           │
  │  data.retrieve / evaluator.run     │
  │  audit.report / hardagents.compile │
  │  campusflow.run                    │
  └──────┬──────────────────────────────┘
         │
  ┌──────┴──────────────────────────────┐
  │  Google Cloud Services             │
  │  Agent Registry (4 agents)        │
  │  Cloud Scheduler (hourly cron)     │
  │  Sheets / Gmail API               │
  └─────────────────────────────────────┘
```

---

## 3. 命题四维度对照

### 3.1 Application Novelty — 原创性

- **可运行 seed + 客观 evaluator + 托管候选变异 + 用户侧评分反馈 + 多代筛选 + 可读算法**：不是简单 Prompt 调 LLM，是真实进化算法（AlphaEvolve 模式）。
- **人工治理介入**：分配方案必须经系主任人工审批才能落地，审计日志可回放。
- **BYO-MCP 全链路**：5 个自建 MCP 服务器覆盖数据加载、进化求解、审计报表、编译器校验、工作流推进。

### 3.2 Real-World Viability — 真实可用性

- 全部部署在 **Google Cloud**（Vertex AI Reasoning Engine + Cloud Run + Cloud Scheduler）。
- 评委可通过 `python3 run_demo.py` 一键调用。
- GitHub 仓库完整提供：源代码、fixtures、部署脚本、证据文档。
- 种子算法（GreedyAssigner）可独立运行验证。

### 3.3 Quantifiable Impact — 量化指标

| 指标 | 种子基线 | 进化后 | 提升 |
|---|---|---|---|
| 硬约束满足率 | 0.75 | — | 部分硬约束因超载无法满足，被标记可治理 |
| 技能匹配覆盖 | 0.70 | — | 匹配度通过课程对齐 Skill 进一步优化 |
| 负载均衡 | 0.00 | — | 基线严重不均衡，进化专门优化此项 |
| 课程覆盖率 | 0.50（10/20课） | — | 进化后通过交替 TA 顺序完成全覆盖 |
| **综合分** | **0.6000** | **0.6624** | **+10.4%** |
| 候选方案数 | 1（seed） | 100（20 代进化） | 100× |

### 3.4 Ecosystem Execution — 生态贴合

| Google 组件 | 使用方式 | 状态 |
|---|---|---|
| Agent Development Kit (ADK) | `LlmAgent` + `sub_agents` + `AdkApp` 部署 | ✅ |
| Vertex AI Reasoning Engine | `agent_engines.create()` 部署 + `stream_query` 调用 | ✅ |
| Agent Registry | 4 个 CampusRescue agent 已注册 | ✅ |
| Agent Designer | 画布可视化 1+3 代理 + 5 MCP 绑定 | ✅ |
| BYO-MCP (Model Context Protocol) | 5 个 streamable HTTP server on Cloud Run | ✅ |
| 24/7 后台任务 | Cloud Scheduler hourly cron | ✅ |
| Google Workspace | Sheets + Gmail API enabled | ✅ |
| Reusable Skills | `curriculum_alignment` (141 pairs avg 0.707) | ✅ |

---

## 4. 在线资产清单

| 资产 | 位置 |
|---|---|
| ReasoningEngine | `projects/538412438779/locations/us-west1/reasoningEngines/8630700085111422976` |
| MCP data.retrieve | `https://mcp-data-retrieve-5l3z4bmblq-uc.a.run.app` |
| MCP evaluator.run | `https://mcp-evaluator-run-5l3z4bmblq-uc.a.run.app` |
| MCP audit.report | `https://mcp-audit-report-5l3z4bmblq-uc.a.run.app` |
| MCP hardagents.compile | `https://mcp-hardagents-compile-5l3z4bmblq-uc.a.run.app` |
| MCP campusflow.run | `https://mcp-campusflow-run-5l3z4bmblq-uc.a.run.app` |
| Cloud Scheduler | `campusrescue-hourly-cycle` (us-central1, ENABLED) |
| Agent Registry (CLI) | `gcloud agent-registry agents list --project=... --location=us-central1` |

---

## 5. 评委验证

### 5.1 一键 demo

```bash
git clone https://github.com/byxacb/campusrescue-evolve
cd campusrescue-evolve
source .venv/bin/activate
python3 run_demo.py "你的5阶段工作流是什么"
```

### 5.2 13 项 self-audit

详见 [EVIDENCE.md](EVIDENCE.md) 共 13 项验证，全部可独立复现。

### 5.3 10 分钟演示剧本

详见 [_DEMO_SCRIPT.md](_DEMO_SCRIPT.md) Step 0-7，每步含可复制 bash 命令 + 讲解词。

---

## 6. 代码仓库结构

```
firebird-entry/
├── deploy_adk_to_vertex.py     # 部署脚本（Vertex AI RE）
├── run_demo.py                  # 评委一键 demo
├── agent_platform/
│   ├── agent_designer_code.py   # ADK agent 定义（3 sub-agents）
│   ├── mcp_loader.py            # MCP toolset 加载器
│   ├── registry/               # Agent Registry JSON 定义
│   └── skills/                 # 可复用领域技能
├── alphaevolve/
│   ├── seed/greedy_assign.py   # 种子分配算法
│   ├── evaluator/evaluate.py   # 4 维度评估器
│   └── controller/             # 进化控制循环
├── mcp_servers/                # 5 个 BYO-MCP 服务器
├── fixtures/                   # 15 TA × 20 课程 fixture
├── scripts/                    # 部署/测试脚本
├── scheduler_job/              # Cloud Scheduler 函数
├── EVIDENCE.md                 # 13 项自我审计
├── _DEMO_SCRIPT.md             # 10 分钟演示剧本
└── README.md                   # 项目说明
```

---

## 7. 已知限制

1. **Agent Designer UI Deploy 按钮**：Google 内部模板缺 `mcp` 包，部署会失败。本仓库不走 UI Deploy，直接用 Python ADK 创建 ReasoningEngine。完整收录 container 启动日志于 `agent-designer-setup-guide.md`。
2. **Gmail API 域委派**：Cloud Run compute SA 缺 domain-wide delegation，`send_notification` 调用 Gmail API 会返回 `failedPrecondition`。Sheets API 按 ADC 认证可直接写入。
3. **AlphaEvolve 服务**：Google Discovery Engine API 仍为 `v1alpha`，本仓库用模拟进化循环替代。当赛事账号有真实 Engine ID 时，切换至 `controller/run_evolution.py` 的 Discovery Engine 分支。

---

*本文档由 EVIDENCE.md / _DEMO_SCRIPT.md / README.md / agent-designer-setup-guide.md 聚合生成。*
