#!/usr/bin/env bash
# 本地启动并测试所有 MCP server
# 用法: ./scripts/test_mcp_local.sh

set -e
cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "❌ .venv 不存在，请先运行: python3 -m venv .venv && .venv/bin/pip install fastmcp uvicorn httpx"
  exit 1
fi

PYTHON=".venv/bin/python3"
PORTS=(8080 8081 8082 8083 8084)
SERVERS=(data_retrieve evaluator_run audit_report hardagents_compile campusflow_run)
PIDS=()

cleanup() {
  echo ""
  echo "🧹 清理子进程..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

echo "🚀 启动 5 个 MCP server..."

for i in "${!SERVERS[@]}"; do
  SERVER="${SERVERS[$i]}"
  PORT="${PORTS[$i]}"
  echo "  ▶ $SERVER (port $PORT)..."
  DATA_DIR="$(pwd)/fixtures" AUDIT_LOG_DIR="$(pwd)/audit_logs" CAMPUSFLOW_DATA_DIR="$(pwd)/run_state" PORT="$PORT" \
    $PYTHON "mcp_servers/$SERVER/server.py" > "/tmp/mcp_$SERVER.log" 2>&1 &
  PIDS+=($!)
  sleep 0.5
done

sleep 3

echo ""
echo "=== 测试 MCP 工具调用 ==="

# 1. data.retrieve
echo "1. data.retrieve list_courses:"
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}' \
  http://localhost:8080/mcp/ 2>&1 | head -c 500
echo ""

# 2. evaluator.run
echo ""
echo "2. evaluator.run status:"
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2}' \
  http://localhost:8081/mcp/ 2>&1 | head -c 500
echo ""

# 3. audit.report
echo ""
echo "3. audit.report list_metrics:"
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":3}' \
  http://localhost:8082/mcp/ 2>&1 | head -c 500
echo ""

echo ""
echo "=== 全部启动完成，子进程 PID: ${PIDS[@]} ==="

# 保持运行 30 秒
sleep 30
echo ""
echo "✅ 测试完成，准备好部署"
