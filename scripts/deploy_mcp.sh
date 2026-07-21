#!/usr/bin/env bash
# 部署所有 BYO-MCP server 到 Cloud Run
# 用法: ./scripts/deploy_mcp.sh [server_name]

set -e

export PATH=/usr/local/share/google-cloud-sdk/bin:"$PATH"
PROJECT_ID="project-53bf8b85-eb44-4391-a2e"
REGION="us-central1"

SERVERS=(
  "data_retrieve"
  "evaluator_run"
  "audit_report"
  "hardagents_compile"
  "campusflow_run"
)

cd "$(dirname "$0")/.."

for SERVER in "${SERVERS[@]}"; do
  if [ -n "$1" ] && [ "$1" != "$SERVER" ]; then
    continue
  fi
  
  echo "🚀 部署 MCP server: $SERVER"
  
  # 构建镜像
  docker build --build-arg SERVER_NAME=$SERVER \
    -t gcr.io/$PROJECT_ID/mcp-$SERVER:latest .
  
  # 推送镜像
  gcloud auth configure-docker --quiet
  docker push gcr.io/$PROJECT_ID/mcp-$SERVER:latest
  
  # 部署到 Cloud Run
  gcloud run deploy mcp-$SERVER \
    --image gcr.io/$PROJECT_ID/mcp-$SERVER:latest \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 3 \
    --set-env-vars "DATA_DIR=./fixtures,AUDIT_LOG_DIR=./audit_logs,CAMPUSFLOW_DATA_DIR=./run_state" \
    --quiet
  
  echo "✅ $SERVER 部署完成"
  echo ""
done

echo "🎉 所有 MCP server 部署完毕"
echo ""
echo "MCP 服务端点:"
for SERVER in "${SERVERS[@]}"; do
  echo "  gcloud run services describe mcp-$SERVER --region $REGION --format 'value(status.url)'"
done
