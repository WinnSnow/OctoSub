#!/bin/bash

# Package this project and deploy it to a remote Docker host.
# The script runs locally, uploads an archive to the server, then executes a
# sudo remote deployment script on the server.

set -euo pipefail

TARGET_HOST="${TARGET_HOST:-192.168.31.142}"
TARGET_USER="${TARGET_USER:-winn}"
TARGET_DIR="${TARGET_DIR:-/usr/local/project/media-search}"
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="media-search"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_NAME="${APP_NAME}_${TIMESTAMP}.tar.gz"
LOCAL_ARCHIVE="/tmp/${ARCHIVE_NAME}"
REMOTE_ARCHIVE="/tmp/${ARCHIVE_NAME}"
REMOTE_SCRIPT="/tmp/${APP_NAME}_deploy_${TIMESTAMP}.sh"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
KEEP_BACKUPS="${KEEP_BACKUPS:-3}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        error "缺少命令: $1"
        exit 1
    fi
}

check_local_project() {
    local required_files=(
        "docker-compose.yml"
        "backend/Dockerfile"
        "frontend/Dockerfile.prod"
        "frontend/Dockerfile.prebuilt"
        "frontend/package.json"
        "docker-compose.prebuilt.yml"
        "backend/requirements.txt"
    )

    for file in "${required_files[@]}"; do
        if [ ! -f "$PROJECT_ROOT/$file" ]; then
            error "当前目录不像完整项目，缺少: $file"
            exit 1
        fi
    done
}

build_frontend() {
    info "在本机安装前端依赖并构建生产产物..."
    (
        cd "$PROJECT_ROOT/frontend"
        npm ci --no-audit --no-fund
        npm run build
    )
    if [ ! -f "$PROJECT_ROOT/frontend/dist/index.html" ]; then
        error "前端构建未生成 dist/index.html"
        exit 1
    fi
}

confirm_settings() {
    echo "目标服务器: ${TARGET_USER}@${TARGET_HOST}"
    echo "目标目录:   ${TARGET_DIR}"
    echo "备份目录:   $(dirname "$TARGET_DIR")/media-search_backups/"
    echo "保留备份:   最近 ${KEEP_BACKUPS} 份"
    echo "本地项目:   ${PROJECT_ROOT}"
    echo ""
    warn "远程会先预构建新镜像；只有构建成功后才会停止旧服务、备份并切换代码。"
    warn "切换后如果启动失败，脚本会自动恢复备份并尝试重启旧服务。"
    warn "本机 runtime/ 和 backend/.env 不会上传；服务器现有数据库、Telegram session 和 .env 会从备份中恢复。"
    echo ""

    echo ""
    read -r -p "确认执行远程更新部署请输入 DEPLOY: " confirmation
    if [ "$confirmation" != "DEPLOY" ]; then
        info "已取消部署。"
        exit 0
    fi
}

build_archive() {
    info "开始打包项目..."
    rm -f "$LOCAL_ARCHIVE"

    local excludes=(
        "--exclude=venv"
        "--exclude=.git"
        "--exclude=frontend/node_modules"
        "--exclude=frontend/build"
        "--exclude=backend/__pycache__"
        "--exclude=backend/routers/__pycache__"
        "--exclude=runtime"
        "--exclude=backend/.env"
        "--exclude=.backend.pid"
        "--exclude=.frontend.pid"
        "--exclude=*.pyc"
        "--exclude=*.log"
    )

    tar -czf "$LOCAL_ARCHIVE" "${excludes[@]}" -C "$PROJECT_ROOT" .
    info "打包完成: $LOCAL_ARCHIVE"
}

upload_archive() {
    info "上传压缩包到服务器 /tmp..."
    scp "${SSH_OPTS[@]}" "$LOCAL_ARCHIVE" "${TARGET_USER}@${TARGET_HOST}:${REMOTE_ARCHIVE}"
}

create_remote_script() {
    local local_remote_script
    local_remote_script="$(mktemp)"

    cat > "$local_remote_script" <<EOF
#!/bin/bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR}"
REMOTE_ARCHIVE="${REMOTE_ARCHIVE}"
BACKUP_PARENT="\$(dirname "\$TARGET_DIR")"
BACKUP_ROOT="\${BACKUP_PARENT}/media-search_backups"
BACKUP_DIR="\${BACKUP_ROOT}/media-search_${TIMESTAMP}"
STAGE_DIR="\${TARGET_DIR}.stage_${TIMESTAMP}"
BACKUP_CREATED="no"
DEPLOY_SWAPPED="no"
OLD_STOPPED="no"
KEEP_BACKUPS="${KEEP_BACKUPS}"

info() {
    echo "[REMOTE] \$1"
}

find_compose() {
    if docker compose version >/dev/null 2>&1; then
        echo "docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        echo "docker-compose"
    else
        echo ""
    fi
}

COMPOSE_CMD="\$(find_compose)"
if [ -z "\$COMPOSE_CMD" ]; then
    echo "[REMOTE][ERROR] Docker Compose 未安装或当前 root 用户不可用。"
    exit 1
fi

cleanup_stage() {
    rm -rf "\$STAGE_DIR"
}

rollback_on_exit() {
    local status="\$?"
    trap - EXIT
    cleanup_stage
    rm -f "\$REMOTE_ARCHIVE"

    if [ "\$DEPLOY_SWAPPED" = "yes" ] && [ "\$BACKUP_CREATED" = "yes" ] && [ -d "\$BACKUP_DIR" ]; then
        echo "[REMOTE][ERROR] 新版本启动失败，正在自动回滚..."
        if [ -f "\$TARGET_DIR/docker-compose.yml" ]; then
            (cd "\$TARGET_DIR" && COMPOSE_PROJECT_NAME="${APP_NAME}" \$COMPOSE_CMD down --remove-orphans) || true
        fi
        rm -rf "\$TARGET_DIR"
        cp -a "\$BACKUP_DIR" "\$TARGET_DIR"
        if [ -f "\$TARGET_DIR/docker-compose.yml" ]; then
            (cd "\$TARGET_DIR" && COMPOSE_PROJECT_NAME="${APP_NAME}" \$COMPOSE_CMD up -d) || \
                echo "[REMOTE][ERROR] 备份已恢复，但旧容器自动启动失败。"
        fi
    elif [ "\$DEPLOY_SWAPPED" = "yes" ] && [ "\$BACKUP_CREATED" != "yes" ]; then
        echo "[REMOTE][ERROR] 首次部署失败，没有可回滚的备份。"
    elif [ "\$OLD_STOPPED" = "yes" ] && [ -f "\$TARGET_DIR/docker-compose.yml" ]; then
        echo "[REMOTE][ERROR] 部署在切换前失败，正在重新启动旧服务..."
        (cd "\$TARGET_DIR" && COMPOSE_PROJECT_NAME="${APP_NAME}" \$COMPOSE_CMD up -d) || \
            echo "[REMOTE][ERROR] 旧服务自动启动失败。"
    fi
    exit "\$status"
}

trap rollback_on_exit EXIT

cleanup_old_backups() {
    if [ ! -d "\$BACKUP_ROOT" ]; then
        return
    fi
    info "清理旧备份，仅保留最近 \$KEEP_BACKUPS 份..."
    find "\$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d -name 'media-search_*' \
        | sort -r \
        | tail -n +\$((KEEP_BACKUPS + 1)) \
        | xargs -r rm -rf
}

info "在临时目录解压新版本..."
cleanup_stage
mkdir -p "\$STAGE_DIR"
tar -xzf "\$REMOTE_ARCHIVE" -C "\$STAGE_DIR"
mkdir -p "\$STAGE_DIR/runtime/data" "\$STAGE_DIR/runtime/sessions" "\$STAGE_DIR/runtime/logs" "\$STAGE_DIR/runtime/backups"

if [ -f "\$TARGET_DIR/backend/.env" ]; then
    cp "\$TARGET_DIR/backend/.env" "\$STAGE_DIR/backend/.env"
elif [ -f "\$STAGE_DIR/backend/.env.example" ]; then
    cp "\$STAGE_DIR/backend/.env.example" "\$STAGE_DIR/backend/.env"
else
    touch "\$STAGE_DIR/backend/.env"
fi

info "预先构建新镜像，此阶段不停止旧服务..."
if [ -f "\$STAGE_DIR/docker-compose.prebuilt.yml" ] && [ -f "\$STAGE_DIR/frontend/dist/index.html" ]; then
    info "使用本机预构建的前端产物，跳过远程 npm ci。"
    (
        cd "\$STAGE_DIR"
        COMPOSE_PROJECT_NAME="${APP_NAME}" \$COMPOSE_CMD \
            -f docker-compose.yml \
            -f docker-compose.prebuilt.yml \
            build
    )
else
    (cd "\$STAGE_DIR" && COMPOSE_PROJECT_NAME="${APP_NAME}" \$COMPOSE_CMD build)
fi

if [ -d "\$TARGET_DIR" ]; then
    if [ -f "\$TARGET_DIR/docker-compose.yml" ]; then
        info "新镜像构建成功，停止旧 Docker 项目..."
        (cd "\$TARGET_DIR" && COMPOSE_PROJECT_NAME="${APP_NAME}" \$COMPOSE_CMD down --remove-orphans) || true
        OLD_STOPPED="yes"
    fi

    info "备份旧项目到: \$BACKUP_DIR"
    mkdir -p "\$BACKUP_ROOT"
    rm -rf "\$BACKUP_DIR"
    cp -a "\$TARGET_DIR" "\$BACKUP_DIR"
    if [ ! -d "\$BACKUP_DIR" ]; then
        echo "[REMOTE][ERROR] 备份失败，已中止部署。"
        exit 1
    fi
    BACKUP_CREATED="yes"
    DEPLOY_SWAPPED="yes"
    rm -rf "\$TARGET_DIR"
else
    info "目标目录不存在，跳过旧项目备份: \$TARGET_DIR"
    DEPLOY_SWAPPED="yes"
fi

info "切换到新版本..."
mv "\$STAGE_DIR" "\$TARGET_DIR"

if [ "\$BACKUP_CREATED" = "yes" ] && [ -d "\$BACKUP_DIR/runtime" ]; then
    info "恢复服务器 runtime 数据..."
    rm -rf "\$TARGET_DIR/runtime"
    cp -a "\$BACKUP_DIR/runtime" "\$TARGET_DIR/runtime"
fi

if [ "\$BACKUP_CREATED" = "yes" ]; then
    echo "\$BACKUP_DIR" > "\$TARGET_DIR/DEPLOY_BACKUP_PATH.txt"
fi

if [ ! -f "\$TARGET_DIR/backend/.env" ]; then
    if [ "\$BACKUP_CREATED" = "yes" ] && [ -f "\$BACKUP_DIR/backend/.env" ]; then
        info "恢复旧 backend/.env..."
        mkdir -p "\$TARGET_DIR/backend"
        cp "\$BACKUP_DIR/backend/.env" "\$TARGET_DIR/backend/.env"
    elif [ -f "\$TARGET_DIR/backend/.env.example" ]; then
        info "backend/.env 不存在，使用 .env.example 初始化。"
        cp "\$TARGET_DIR/backend/.env.example" "\$TARGET_DIR/backend/.env"
    else
        info "backend/.env 不存在，创建空文件。"
        touch "\$TARGET_DIR/backend/.env"
    fi
fi

info "启动已预构建的 Docker 项目..."
cd "\$TARGET_DIR"
COMPOSE_PROJECT_NAME="${APP_NAME}" \$COMPOSE_CMD up -d --no-build

info "当前容器状态:"
\$COMPOSE_CMD ps

info "清理远程临时压缩包..."
rm -f "\$REMOTE_ARCHIVE"

cleanup_old_backups

trap - EXIT
info "部署完成。访问地址: http://${TARGET_HOST}:55443"
EOF

    chmod +x "$local_remote_script"
    scp "${SSH_OPTS[@]}" "$local_remote_script" "${TARGET_USER}@${TARGET_HOST}:${REMOTE_SCRIPT}"
    rm -f "$local_remote_script"
}

run_remote_deploy() {
    info "开始远程部署。接下来可能会要求输入 SSH 密码和 sudo 密码。"
    ssh "${SSH_OPTS[@]}" -t "${TARGET_USER}@${TARGET_HOST}" "sudo bash '${REMOTE_SCRIPT}'; status=\$?; rm -f '${REMOTE_SCRIPT}'; exit \$status"
}

cleanup_local() {
    rm -f "$LOCAL_ARCHIVE"
}

main() {
    require_command tar
    require_command scp
    require_command ssh
    require_command npm
    check_local_project
    confirm_settings
    build_frontend
    build_archive
    upload_archive
    create_remote_script
    run_remote_deploy
    cleanup_local
}

main "$@"
