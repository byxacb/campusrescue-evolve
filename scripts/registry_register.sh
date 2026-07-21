#!/usr/bin/env bash
# Agent Registry 注册脚本
# 注册所有 agent、MCP server、endpoint 到 Agent Registry

set -e

PROJECT_ID="${PROJECT_ID:-project-53bf8b85-eb44-4391-a2e}"
REGION="${REGION:-us-central1}"
REGISTRY_DIR="$(dirname "$0")/../agent_platform/registry"
REGISTRY_API="https://agentregistry.googleapis.com/v1"

export PATH="/usr/local/share/google-cloud-sdk/bin:$PATH"
TOKEN=$(gcloud auth print-access-token)

echo "=== 注册 Agent 到 Agent Registry ==="

# 1. 注册 TAProfileCollector Agent
echo "1. 注册 TAProfileCollectorAgent..."
AGENT_DEF=$(cat "$REGISTRY_DIR/ta_profile_collector.json")

curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Goog-User-Project: $PROJECT_ID" \
  -H "Content-Type: application/json" \
  -d "$AGENT_DEF" \
  "$REGISTRY_API/projects/$PROJECT_ID/locations/$REGION/agents?agent_id=ta_profile_collector" \
  | python3 -m json.tool 2>&1 | head -10

echo ""
echo "2. 注册 AssignmentReviewerAgent（需要先创建 JSON 定义）"
echo "   -> 暂未创建定义文件，待后续补充"

echo ""
echo "3. 注册 MCP Server endpoints..."
echo "   -> 需在 Cloud Run 部署完成后注册"

echo ""
echo "=== 注册完成 ==="
echo ""
echo "后续步骤:"
echo "  1. 部署 MCP 到 Cloud Run:  cd firebird-entry && bash scripts/deploy_mcp.sh"
echo "  2. 获取 Cloud Run URL"
echo "  3. 将 URL 注册到 Agent Registry 作为 endpoint"
echo "  4. 在 Agent Designer 中创建 Flow，连接 TAProfileCollector -> AlphaEvolve -> AssignmentReviewer"
