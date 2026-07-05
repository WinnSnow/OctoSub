#!/bin/bash

# 快速启动脚本 - 本地开发环境

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-5172}"

cd "$ROOT_DIR" || exit 1
mkdir -p runtime/data runtime/sessions runtime/logs

echo "=================================="
echo "  OctoSub 快速启动"
echo "=================================="
echo ""

# 先清理本项目旧实例，避免旧 CRA/uvicorn 进程占用端口。
if [ -x "./stop.sh" ]; then
    ./stop.sh >/dev/null 2>&1 || true
fi

# 如果旧进程属于其他用户，stop.sh 可能没有权限杀掉。继续启动会让多个
# Telethon 客户端共用同一个 session，容易触发 Telegram AuthKeyDuplicated。
REMAINING_PROCESSES="$(pgrep -af "$ROOT_DIR/venv/bin/python ../scripts/timestamped_runner.py|$ROOT_DIR/venv/bin/python ../venv/bin/uvicorn main:app|$ROOT_DIR/frontend/node_modules/.bin/vite|node ./node_modules/.bin/vite --host 0.0.0.0 --port $FRONTEND_PORT" || true)"
if [ -n "$REMAINING_PROCESSES" ]; then
    echo "❌ 检测到本项目仍有旧进程在运行，已中止启动，避免 Telegram 会话冲突。"
    echo ""
    echo "$REMAINING_PROCESSES"
    echo ""
    echo "请先停止这些进程，例如："
    echo "   sudo kill <PID>"
    echo "然后重新执行："
    echo "   ./start.sh"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境不存在，请先创建："
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r backend/requirements.txt"
    exit 1
fi

# 启动后端
echo "🚀 启动后端服务..."
cd backend || exit 1
source ../venv/bin/activate

# 检查并安装依赖
echo "📦 检查依赖..."
pip install -q -r requirements.txt

nohup ../venv/bin/python ../scripts/timestamped_runner.py --log ../runtime/logs/backend.log -- ../venv/bin/uvicorn main:app --host 0.0.0.0 --port "$BACKEND_PORT" >/dev/null 2>&1 &
BACKEND_PID=$!
echo "✓ 后端已启动 (PID: $BACKEND_PID)"
echo "  日志: runtime/logs/backend.log"
echo "  API: http://localhost:$BACKEND_PORT"
cd .. || exit 1

# 启动前端
echo ""
echo "🚀 启动前端服务..."
cd frontend || exit 1

if [ ! -d "node_modules" ]; then
    echo "📦 安装前端依赖..."
    npm install
fi

nohup ../venv/bin/python ../scripts/timestamped_runner.py --log ../runtime/logs/frontend.log -- ./node_modules/.bin/vite --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort >/dev/null 2>&1 &
FRONTEND_PID=$!
echo "✓ 前端已启动 (PID: $FRONTEND_PID)"
echo "  日志: runtime/logs/frontend.log"
echo "  URL: http://localhost:$FRONTEND_PORT"
cd .. || exit 1

# 保存 PID
echo "$BACKEND_PID" > .backend.pid
echo "$FRONTEND_PID" > .frontend.pid

echo ""
echo "=================================="
echo "✓ 服务启动完成！"
echo "=================================="
echo ""
echo "访问地址: http://localhost:$FRONTEND_PORT"
echo "管理员账号请在 backend/.env 中配置。"
echo ""
echo "停止服务: ./stop.sh"
echo "查看日志: tail -f runtime/logs/backend.log runtime/logs/frontend.log"
echo ""
