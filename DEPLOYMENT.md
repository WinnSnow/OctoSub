# 🚀 OctoSub 部署指南

本文档提供完整的部署和启动说明。

---

## 📋 目录

- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [部署方式](#部署方式)
- [常见问题](#常见问题)

---

## 系统要求

### 最低配置

- **操作系统**: Linux / macOS / Windows (WSL2)
- **Docker**: 20.10+
- **Docker Compose**: 2.24+（生产配置使用 `env_file.format=raw`，用于保留密码哈希中的 `$` 字符）
- **内存**: 2GB+
- **磁盘**: 5GB+

### 推荐配置

- **CPU**: 4核+
- **内存**: 4GB+
- **磁盘**: 20GB+ (SSD)

---

## 快速开始

### 1. 克隆或下载项目

```bash
git clone https://github.com/WinnSnow/OctoSub.git
cd OctoSub
```

### 2. 配置环境变量

首次使用 `./deploy.sh start` 会按 `backend/.env.example` 创建 `backend/.env`。长期运行前建议先编辑后端配置文件：

```bash
nano backend/.env
```

**必须配置的参数**：

```ini
# 系统管理员账号
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=pbkdf2_sha256$260000$<salt>$<base64-digest>

# 认证密钥（生产环境必须固定为随机长字符串）
AUTH_SECRET=<generate-a-long-random-secret>

# 115 / CMS / 企业微信转存配置
FORWARD_URL=https://your-cms.example.com/api/wx/message?source=wx
WECOM_TOKEN=<your-wecom-token>
```

**可选配置**（订阅功能需要）：

```ini
# Jellyfin 配置（可选，用于媒体库去重）
JELLYFIN_URL=http://your-jellyfin-host:8096
JELLYFIN_API_KEY=your_jellyfin_api_key_here

# 订阅系统配置
SUBSCRIPTION_ENABLED=true
SUBSCRIPTION_CHECK_HOUR=2
SUBSCRIPTION_CHECK_MINUTE=0
```

### 3. 启动服务

#### 方式一：使用部署脚本（推荐）

```bash
# 启动生产环境
./deploy.sh start

# 或启动开发环境
./deploy.sh dev
```

生产环境会通过 `docker-compose.yml` 的 `env_file` 读取 `backend/.env`，并使用 raw 格式保留 `ADMIN_PASSWORD_HASH` 等值中的 `$` 字符。请不要把 `backend/.env` 提交到版本控制。

### 4. 访问应用

- **前端界面**: http://localhost:55443
- **后端 API**: http://localhost:55443/api
- **PanSou 搜索服务**: http://localhost:8888
- **默认管理员账号**: `admin`
- **默认管理员密码**: `admin`，公开部署前务必修改

---

## 配置说明

### 后端环境变量（backend/.env）

| 变量名 | 说明 | 必须 | 默认值 |
|--------|------|------|--------|
| `ADMIN_USERNAME` | 管理员用户名 | 是 | admin |
| `ADMIN_PASSWORD_HASH` | 管理员密码哈希 | 生产必填 | - |
| `ADMIN_PASSWORD` | 明文密码兼容项 | 否 | admin |
| `AUTH_SECRET` | JWT 密钥 | 是 | - |
| `AUTH_TTL_SECONDS` | 登录有效期（秒） | 否 | 43200 (12小时) |
| `RUNTIME_DIR` | 运行产物根目录 | 否 | runtime |
| `DATA_DIR` | 数据目录 | 否 | runtime/data |
| `SESSION_DIR` | Telegram session 目录 | 否 | runtime/sessions |
| `LOG_DIR` | 日志目录 | 否 | runtime/logs |
| `BACKEND_LOCK_PATH` | 后端单实例锁文件 | 否 | runtime/backend.lock |
| `DB_PATH` | 数据库路径 | 否 | runtime/data/telegram_data.db |
| `SESSION_NAME` | Telegram session 名称 | 否 | runtime/sessions/anon |
| `FORWARD_URL` | 115转存接口 | 是 | - |
| `WECOM_TOKEN` | 企业微信Token | 是 | - |
| `CMS_BASE_URL` | CMS 服务地址 | 否 | - |
| `CMS_SHARE_DOWN_LIST_URL` | CMS 下载列表接口 | 否 | - |
| `PANSOU_BASE_URL` | PanSou 服务地址 | 否 | http://pansou:8888 |
| `PANSOU_ENABLED` | 是否启用 PanSou | 否 | true |
| `TMDB_API_KEY` | TMDB 海报和详情 API Key | 否 | - |
| `JELLYFIN_URL` | Jellyfin 服务器地址 | 否 | - |
| `JELLYFIN_API_KEY` | Jellyfin API密钥 | 否 | - |
| `SUBSCRIPTION_ENABLED` | 订阅系统开关 | 否 | true |
| `SUBSCRIPTION_CHECK_HOUR` | 订阅检查时间（小时） | 否 | 2 |
| `PUBLIC_SEARCH_CHANNELS` | 公开搜索频道 | 否 | 空 |

### 端口映射

| 服务 | 容器端口 | 主机端口 | 说明 |
|------|----------|----------|------|
| 前端 | 80 | 55443 | Nginx 静态服务 |
| 后端 | 8001 | 不暴露 | FastAPI 服务，仅供容器网络内部访问 |
| PanSou | 8888 | 8888 | 公开搜索服务 |

---

## 部署方式

### 方式一：生产环境部署（推荐）

使用 Nginx + 生产构建版本，性能最优。

```bash
# 启动
./deploy.sh start

# 停止
./deploy.sh stop

# 重启
./deploy.sh restart

# 查看日志
./deploy.sh logs

# 查看状态
./deploy.sh status
```

**特点**：
- ✅ 前端代码打包优化（gzip、缓存）
- ✅ Nginx 反向代理
- ✅ 自动重启（`restart: unless-stopped`）
- ✅ 健康检查

### 方式二：开发环境部署

支持代码热重载，适合开发调试。

```bash
# 启动开发环境
./deploy.sh dev

# 查看日志
docker compose -f docker-compose.dev.yml logs -f

# 停止
docker compose -f docker-compose.dev.yml down
```

**特点**：
- 📝 代码挂载（支持热重载）
- 📝 源码映射（便于调试）
- 📝 React 开发服务器

### 方式三：本地脚本运行

不使用 Docker，适合快速测试。

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r backend/requirements.txt

# 启动前后端
./start.sh
```

访问 http://localhost:5172。`start.sh` 只启动前后端；公开搜索依赖 PanSou，需要自行部署并配置 `PANSOU_BASE_URL`，或使用 `./deploy.sh dev`。

---

## 常用命令

### 使用部署脚本

```bash
# 启动生产环境
./deploy.sh start

# 启动开发环境
./deploy.sh dev

# 停止所有服务
./deploy.sh stop

# 重启服务
./deploy.sh restart

# 查看所有日志
./deploy.sh logs

# 查看后端日志
./deploy.sh logs backend

# 查看前端日志
./deploy.sh logs frontend

# 查看服务状态
./deploy.sh status

# 进入后端容器
./deploy.sh shell backend

# 进入前端容器
./deploy.sh shell frontend

# 备份数据库
./deploy.sh backup

# 清理所有容器和镜像
./deploy.sh clean

# 显示帮助
./deploy.sh help
```

### 直接使用 Docker Compose

```bash
# 启动（后台）
docker compose up -d

# 启动（前台，查看日志）
docker compose up

# 停止
docker compose down

# 重新构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f backend

# 查看状态
docker compose ps

# 进入容器
docker compose exec backend bash
docker compose exec frontend sh

# 重启特定服务
docker compose restart backend
```

---

## 数据持久化

### 重要数据文件

| 文件 | 路径 | 说明 |
|------|------|------|
| 数据库 | `runtime/data/telegram_data.db` | SQLite 数据库 |
| Session | `runtime/sessions/anon.session` | Telegram 会话 |
| 日志 | `runtime/logs/` | 本地启动日志 |
| 配置 | `backend/.env` | 环境变量配置 |

### 备份方案

#### 自动备份

```bash
# 添加定时任务（每天凌晨3点备份）
crontab -e

# 添加以下行
0 3 * * * cd /path/to/octosub && ./deploy.sh backup
```

#### 手动备份

```bash
# 使用脚本备份
./deploy.sh backup

# 或手动复制
cp runtime/data/telegram_data.db runtime/backups/telegram_data_$(date +%Y%m%d).db
```

---

## Jellyfin 配置（可选）

订阅系统可以与 Jellyfin 集成，自动检查媒体库避免重复下载。

### 1. 获取 Jellyfin API 密钥

1. 登录 Jellyfin 管理后台
2. 进入 **控制台 → API 密钥**
3. 点击 **新建 API 密钥**
4. 输入应用名称（如 "OctoSub"）
5. 复制生成的密钥

### 2. 配置环境变量

编辑 `backend/.env`：

```ini
JELLYFIN_URL=http://your-jellyfin-host:8096
JELLYFIN_API_KEY=your_api_key_here
```

### 3. 重启服务

```bash
./deploy.sh restart
```

### 4. 测试连接

访问前端 → **Jellyfin** 页面 → 点击 **测试连接**

---

## 订阅系统使用

### 1. 创建订阅

访问 **订阅管理** 页面，点击 **新建订阅**：

- **订阅关键词**: 如 "庆余年"
- **媒体类型**: 剧集 / 电影
- **质量过滤**: 如 `4K|2160p` (可选)

### 2. 自动检查

系统每天凌晨2点自动执行订阅检查任务。

### 3. 手动触发

点击 **手动检查** 按钮立即执行一次检查。

### 4. 查看历史

访问 **下载历史** 页面查看转存记录。

---

## 监控和日志

### 查看实时日志

```bash
# 所有服务
./deploy.sh logs

# 后端日志
./deploy.sh logs backend

# 前端日志
./deploy.sh logs frontend
```

### 日志文件位置

- 后端日志：容器内 `/app` 目录
- 前端日志：Nginx 标准输出

### 健康检查

```bash
# 查看健康状态
docker compose ps

# 后端健康检查
curl http://localhost:55443/api/health

# 前端健康检查
curl http://localhost:55443
```

---

## 性能优化

### 生产环境优化

1. **前端优化**
   - ✅ 代码分割和懒加载
   - ✅ Gzip 压缩
   - ✅ 静态资源缓存（1年）
   - ✅ CDN 加速（可选）

2. **后端优化**
   - ✅ 数据库 WAL 模式
   - ✅ 搜索结果缓存（20分钟）
   - ✅ 连接池和异步处理

3. **Docker 优化**
   - ✅ 多阶段构建
   - ✅ 镜像层缓存
   - ✅ .dockerignore 排除无关文件

### 资源限制（可选）

编辑 `docker-compose.yml`，添加资源限制：

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

---

## 常见问题

### 1. 端口被占用

**问题**: `Error: port 55443 is already in use`

**解决**: 修改 `docker-compose.yml` 中的端口映射：

```yaml
ports:
  - "8080:80"  # 改为8080
```

### 2. 数据库锁定

**问题**: `database is locked`

**解决**: 
```bash
# 停止所有服务
./deploy.sh stop

# 确保没有进程占用数据库
lsof runtime/data/telegram_data.db

# 重启服务
./deploy.sh start
```

### 3. 容器无法启动

**问题**: 容器反复重启

**解决**:
```bash
# 查看日志
./deploy.sh logs backend

# 检查配置文件
cat backend/.env

# 重新构建
docker compose up -d --build --force-recreate
```

### 4. 前端页面空白

**问题**: 访问前端显示空白

**解决**:
```bash
# 检查前端构建
docker compose logs frontend

# 重新构建前端
docker compose up -d --build frontend
```

### 5. API 请求失败

**问题**: 前端无法连接后端 API

**解决**:
- 检查后端是否启动：`curl http://localhost:55443/api/health`
- 检查网络：`docker network ls`
- 查看 nginx 配置：`docker compose exec frontend cat /etc/nginx/conf.d/default.conf`

---

## 安全建议

### 生产环境部署

1. **更改默认密码**
   ```bash
   # 生成新的密码哈希
   python3 -c "import hashlib, os; salt = os.urandom(16).hex(); print(f'pbkdf2_sha256$260000${salt}$' + hashlib.pbkdf2_hmac('sha256', b'YOUR_PASSWORD', salt.encode(), 260000).hex())"
   ```

2. **更新 AUTH_SECRET**
   ```bash
   # 生成随机密钥
   openssl rand -base64 32
   ```

3. **配置防火墙**
   ```bash
   # 只开放必要端口
   sudo ufw allow 55443/tcp
   sudo ufw enable
   ```

4. **使用 HTTPS**
   - 配置 SSL 证书（Let's Encrypt）
   - 启用 HTTPS 强制跳转

5. **限制访问**
   - 使用 IP 白名单
   - 启用速率限制

---

## 升级和迁移

### 升级服务

```bash
# 拉取最新代码
git pull

# 重新构建并启动
./deploy.sh restart
```

### 数据迁移

```bash
# 1. 在旧服务器备份
./deploy.sh backup

# 2. 复制备份文件到新服务器
scp runtime/backups/telegram_data_*.db user@new-server:/path/to/project/runtime/backups/

# 3. 在新服务器恢复
cp runtime/backups/telegram_data_*.db runtime/data/telegram_data.db

# 4. 启动服务
./deploy.sh start
```

---

## 技术支持

- **项目仓库**: 查看项目根目录的文档
- **问题反馈**: 检查日志文件
- **配置示例**: 参考 `backend/.env` 文件

---

**最后更新**: 2026-06-13  
**版本**: v1.0.0
