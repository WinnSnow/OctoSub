#!/bin/bash

# 停止服务脚本

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-5172}"

cd "$ROOT_DIR" || exit 1

echo "🛑 停止 OctoSub 服务..."

stop_pid_file() {
    local file="$1"
    local label="$2"
    if [ -f "$file" ]; then
        local pid
        pid=$(cat "$file")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            echo "✓ ${label} 已停止 (PID: $pid)"
        fi
        rm -f "$file"
    fi
}

stop_pid_file ".backend.pid" "后端服务"
stop_pid_file ".frontend.pid" "前端服务"

# 清理本项目残留进程。限定路径和启动参数，避免误杀其他项目。
find_project_processes() {
    pgrep -af "$ROOT_DIR/venv/bin/python ../scripts/timestamped_runner.py" 2>/dev/null || true
    pgrep -af "$ROOT_DIR/venv/bin/python ../venv/bin/uvicorn main:app" 2>/dev/null || true
    pgrep -af "$ROOT_DIR/venv/bin/uvicorn main:app" 2>/dev/null || true
    pgrep -af "$ROOT_DIR/frontend/node_modules/.bin/vite" 2>/dev/null || true
    pgrep -af "node ./node_modules/.bin/vite --host 0.0.0.0 --port $FRONTEND_PORT" 2>/dev/null || true
    pgrep -af "cd $ROOT_DIR/frontend.*npm start" 2>/dev/null || true
}

stop_project_processes() {
    local pids
    pids="$(find_project_processes | awk '{print $1}' | sort -u)"
    if [ -z "$pids" ]; then
        return
    fi

    kill $pids 2>/dev/null || true
    sleep 1

    local stubborn_pids=""
    local pid
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            stubborn_pids="$stubborn_pids $pid"
        fi
    done

    if [ -n "$stubborn_pids" ]; then
        kill -9 $stubborn_pids 2>/dev/null || true
    fi
}

stop_project_processes

remaining_processes="$(find_project_processes)"
if [ -n "$remaining_processes" ]; then
    echo ""
    echo "⚠️  仍检测到本项目残留进程："
    echo "$remaining_processes"
    echo ""
    echo "请使用有权限的用户清理，例如："
    echo "   sudo kill -9 <PID>"
    exit 1
fi

echo ""
echo "✓ 所有 OctoSub 服务已停止"
