#!/bin/bash

# OctoSub 启动脚本
# 用于快速启动和管理 Docker 容器

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

compose_version() {
    if docker compose version --short &> /dev/null; then
        docker compose version --short | sed 's/^v//'
    elif command -v docker-compose &> /dev/null; then
        docker-compose version --short 2>/dev/null | sed 's/^v//'
    fi
}

version_at_least() {
    local current="$1"
    local required="$2"
    [ "$current" = "$required" ] && return 0
    [ "$(printf '%s\n%s\n' "$required" "$current" | sort -V | head -n 1)" = "$required" ]
}

# 检查 Docker 是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi

    if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi

    local current_compose_version
    current_compose_version="$(compose_version)"
    if [ -z "$current_compose_version" ] || ! version_at_least "$current_compose_version" "2.24.0"; then
        print_error "当前 Docker Compose 版本过低：${current_compose_version:-unknown}"
        print_error "生产配置需要 Docker Compose 2.24.0+ 以支持 env_file raw 格式。"
        exit 1
    fi
}

compose() {
    if docker compose version &> /dev/null; then
        docker compose "$@"
    else
        docker-compose "$@"
    fi
}

# 检查配置文件
check_config() {
    mkdir -p runtime/data runtime/sessions runtime/logs runtime/backups
    if [ ! -f "backend/.env" ]; then
        print_warn "未找到 backend/.env 文件"
        print_info "正在创建默认配置文件..."
        cp backend/.env.example backend/.env 2>/dev/null || touch backend/.env
        print_warn "请编辑 backend/.env 文件配置必要的参数"
    fi
}

# 启动服务（生产环境）
start_prod() {
    print_info "启动生产环境..."
    compose up -d --build
    print_info "✓ 服务已启动"
    print_info "前端访问地址: http://localhost:55443"
    print_info "后端 API: http://localhost:55443/api"
    print_info "PanSou 搜索服务: http://localhost:8888"
    print_info ""
    print_info "查看日志: ./deploy.sh logs"
    print_info "停止服务: ./deploy.sh stop"
}

# 启动服务（开发环境）
start_dev() {
    print_info "启动开发环境..."
    compose -f docker-compose.dev.yml up -d --build
    print_info "✓ 服务已启动"
    print_info "前端访问地址: http://localhost:5172"
    print_info "后端 API 地址: http://localhost:8001"
    print_info "PanSou 搜索服务: http://localhost:8888"
}

# 停止服务
stop() {
    print_info "停止服务..."
    compose down
    compose -f docker-compose.dev.yml down 2>/dev/null || true
    print_info "✓ 服务已停止"
}

# 重启服务
restart() {
    print_info "重启服务..."
    stop
    sleep 2
    start_prod
}

logs() {
    if [ -z "$2" ]; then
        compose logs -f
    else
        compose logs -f "$2"
    fi
}

# 查看状态
status() {
    print_info "服务状态:"
    compose ps
}

# 清理
clean() {
    print_warn "此操作将删除所有容器、镜像和数据卷"
    read -p "确认继续? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "清理中..."
        compose down -v --rmi all
        print_info "✓ 清理完成"
    else
        print_info "已取消"
    fi
}

# 进入容器
shell() {
    if [ -z "$2" ]; then
        print_error "请指定容器名称: backend 或 frontend"
        exit 1
    fi

    case "$2" in
        backend)
            compose exec backend /bin/bash
            ;;
        frontend)
            compose exec frontend /bin/sh
            ;;
        *)
            print_error "未知的容器名称: $2"
            exit 1
            ;;
    esac
}

# 备份数据库
backup() {
    BACKUP_DIR="./runtime/backups"
    mkdir -p "$BACKUP_DIR"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/telegram_data_${TIMESTAMP}.db"

    print_info "备份数据库..."
    cp runtime/data/telegram_data.db "$BACKUP_FILE"
    print_info "✓ 备份完成: $BACKUP_FILE"
}

# 显示帮助
show_help() {
    cat << EOF
OctoSub 部署脚本

用法: $0 [命令]

命令:
  start       启动生产环境服务
  dev         启动开发环境服务
  stop        停止所有服务
  restart     重启服务
  logs        查看日志 (可选参数: backend/frontend/pansou)
  status      查看服务状态
  shell       进入容器 (参数: backend/frontend)
  backup      备份数据库
  clean       清理所有容器、镜像和数据
  help        显示此帮助信息

示例:
  $0 start              # 启动生产环境
  $0 dev                # 启动开发环境
  $0 logs backend       # 查看后端日志
  $0 shell backend      # 进入后端容器

EOF
}

# 主函数
main() {
    check_docker
    check_config

    case "${1:-help}" in
        start)
            start_prod
            ;;
        dev)
            start_dev
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        logs)
            logs "$@"
            ;;
        status)
            status
            ;;
        shell)
            shell "$@"
            ;;
        backup)
            backup
            ;;
        clean)
            clean
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
