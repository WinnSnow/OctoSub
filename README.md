# OctoSub

OctoSub 是一个面向个人使用的媒体资源搜索、订阅和转存管理工具。它以 PanSou、Telegram 公开频道搜索和本地消息库为入口，结合订阅规则、Jellyfin 媒体库检查、TMDB 海报匹配和 115/CMS 转存流程，帮助你集中管理影视资源发现、去重、订阅检查和下载历史。

> 说明：本项目约 80% 由 AI 辅助实现，代码和文档仍可能存在不完善之处。建议部署前先阅读配置说明，并按自己的转存服务、CMS、Jellyfin 和 Telegram 环境做验证。

> 本项目只提供工具能力，不提供任何资源内容、频道数据、账号、密钥或第三方服务。请自行确认使用方式符合所在地区法律法规和相关平台规则。

## 主要功能

- **资源搜索**
  - 通过 PanSou 接入公开搜索来源。
  - 搜索 Telegram 公开频道资源。
  - 搜索本地已抓取消息库。
  - 识别 115、夸克、百度、阿里云盘、磁力等链接类型。
  - 支持关键词、频道、链接类型等筛选。

- **频道与消息管理**
  - 添加、删除、刷新频道。
  - 抓取频道消息并提取资源链接。
  - 支持代理配置，用于 Telegram、TMDB、公开搜索等网络访问场景。

- **订阅与自动检查**
  - 按关键词、媒体类型、季集信息和质量规则创建订阅。
  - 定时检查新资源。
  - 通过标题解析、指纹和链接去重减少重复转存。
  - 可结合 Jellyfin 检查已有媒体库，避免重复入库。

- **海报和媒体信息**
  - 支持 TMDB 搜索与详情获取。
  - 可为消息和订阅结果匹配海报。
  - 支持本地海报复用和批量补全。

- **转存与下载历史**
  - 支持 115/CMS/企业微信回调式转存流程。
  - 记录转存状态、下载历史、失败原因和重试任务。
  - 支持待确认转存队列，降低订阅自动转存误匹配风险。

- **系统管理**
  - Cookie 登录认证。
  - 后台任务状态查看、取消和重试。
  - 系统状态、依赖配置、运行目录和最近事件诊断。

## 技术栈

- 后端：Python 3.12、FastAPI、SQLite、Telethon
- 前端：React 19、Vite
- 部署：Docker Compose、Nginx、PanSou

## 快速部署

推荐使用 Docker Compose 部署。Compose 会同时启动前端、后端和 PanSou 搜索服务。

- Docker 20.10+
- Docker Compose 2.24+

```bash
git clone https://github.com/WinnSnow/OctoSub.git
cd OctoSub
./deploy.sh start
```

首次启动会按 `backend/.env.example` 创建 `backend/.env`。长期运行前建议先配置管理员密码、`AUTH_SECRET`、Telegram、TMDB、Jellyfin、CMS/转存等参数。

默认登录账号是 `admin`，默认密码是 `admin`。公开部署前务必修改。

默认 Web 地址：`http://localhost:55443`。

## 本地开发运行

本地开发可以使用脚本启动前后端：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
./start.sh
```

默认前端地址：`http://localhost:5172`，后端地址：`http://localhost:8001`。

`start.sh` 只启动前后端。公开搜索依赖 PanSou；如果需要本地公开搜索，可以自行部署 PanSou 并把 `PANSOU_BASE_URL` 指向它，或使用 `./deploy.sh dev` 启动 Docker 开发环境。

## 配置说明

配置文件位于 `backend/.env`。不要提交真实 `.env` 到 Git。

### 基础认证

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `ADMIN_USERNAME` | 是 | `admin` | 管理员用户名 |
| `ADMIN_PASSWORD_HASH` | 生产必填 | 空 | 管理员密码哈希，推荐使用上方命令生成 |
| `ADMIN_PASSWORD` | 否 | `admin` | 明文密码兼容项，仅适合初次体验，不建议生产使用 |
| `AUTH_SECRET` | 生产必填 | 开发占位值 | 登录 token 签名密钥，生产必须固定且足够随机 |
| `AUTH_COOKIE_SECURE` | 否 | `false` | HTTPS 部署时建议设为 `true` |

### 运行时路径

默认数据会写入项目根目录下的 `runtime/`。Docker 部署会把 `./runtime` 挂载到容器内。

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `RUNTIME_DIR` | 否 | `<project>/runtime` | 运行时根目录 |
| `DATA_DIR` | 否 | `runtime/data` | SQLite 数据目录 |
| `SESSION_DIR` | 否 | `runtime/sessions` | Telegram session 目录 |
| `LOG_DIR` | 否 | `runtime/logs` | 日志目录 |
| `DB_PATH` | 否 | `runtime/data/telegram_data.db` | SQLite 数据库路径 |
| `SESSION_NAME` | 否 | `runtime/sessions/anon_dev` | Telethon session 名称或路径 |
| `BACKEND_LOCK_PATH` | 否 | `runtime/backend.lock` | 后端单实例锁文件 |

### Telegram

如果只使用公开搜索，可以先不配置 Telegram 登录。抓取频道入库、登录 Telegram、补链等功能需要配置。

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `API_ID` | 相关功能必填 | `0` | Telegram API ID |
| `API_HASH` | 相关功能必填 | 空 | Telegram API HASH |

### 搜索与海报

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `PUBLIC_SEARCH_CHANNELS` | 否 | 空 | 公开搜索频道列表，逗号分隔 |
| `PUBLIC_SEARCH_TTL_SECONDS` | 否 | `1200` | 公开搜索缓存时间 |
| `PANSOU_BASE_URL` | 否 | `http://pansou:8888` | PanSou 服务地址。Docker Compose 使用容器名，本地手动部署可改为 `http://127.0.0.1:8888` |
| `PANSOU_ENABLED` | 否 | `true` | 是否启用 PanSou。关闭后公开搜索来源会减少 |
| `TMDB_API_KEY` | 海报/详情功能需要 | 空 | TMDB API Key |

### PanSou 搜索服务

公开搜索的信息来源包含 PanSou。Docker Compose 已内置 `pansou` 服务；非 Docker 部署需要自行提供 PanSou 地址。如果暂时不用公开搜索，可以设置 `PANSOU_ENABLED=false`。

### Douban

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DOUBAN_ENABLED` | 否 | `true` | 是否启用豆瓣相关能力 |
| `DOUBAN_BASE_URL` | 否 | `https://frodo.douban.com/api/v2` | 豆瓣 API 地址 |
| `DOUBAN_API_KEY` | 否 | 空 | 豆瓣 API Key |
| `DOUBAN_API_SECRET` | 否 | 空 | 豆瓣 API Secret |
| `DOUBAN_TIMEOUT_SECONDS` | 否 | `8` | 请求超时 |

### 115 / CMS / 企业微信转存

订阅自动转存、手动转存和 CMS 同步需要配置这些服务。当前项目里的转存流程按“115 转存服务 + CMS 回调/同步”这个模式设计：

- `FORWARD_URL` 是提交转存请求的入口，通常指向你自己的企业微信/CMS 转存入口。
- 转存成功后的状态回写依赖 CMS 相关接口和回调/同步逻辑。
- 如果你使用的不是兼容 CMS 的转存项目，可能可以提交转存，但 OctoSub 不一定能收到“转存成功/失败”的回调，也就无法自动更新下载历史和订阅状态。
- 如果你使用的是其它 115 转存项目，需要先研究该项目的回调方式、状态查询接口和返回字段，再调整 OctoSub 后端的回调解析或 CMS 同步逻辑。
- 实在不确定接口怎么改，可以把你的转存项目接口文档、回调样例和当前代码一起交给 AI 辅助改造。

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `FORWARD_URL` | 转存功能必填 | 空 | 企业微信/CMS 转存入口 |
| `WECOM_TOKEN` | 回调校验需要 | 空 | 企业微信 token |
| `WECOM_ENCODING_AES_KEY` | 回调解密需要 | 空 | 企业微信 EncodingAESKey |
| `WECOM_CORP_ID` | 回调解密需要 | 空 | 企业微信 Corp ID |
| `CMS_BASE_URL` | CMS 同步需要 | 空 | CMS 服务地址 |
| `CMS_SHARE_DOWN_LIST_URL` | CMS 同步需要 | 空 | CMS 下载列表接口 |
| `CMS_TRANSFER_POLL_ENABLED` | 否 | `true` | 是否启用 CMS 转存轮询 |

### Jellyfin

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `JELLYFIN_URL` | 否 | 空 | Jellyfin 服务地址 |
| `JELLYFIN_API_KEY` | 否 | 空 | Jellyfin API Key |

### 订阅任务

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `SUBSCRIPTION_ENABLED` | 否 | `true` | 是否启用订阅检查 |
| `SUBSCRIPTION_CHECK_HOUR` | 否 | `2` | 每日检查小时 |
| `SUBSCRIPTION_CHECK_MINUTE` | 否 | `0` | 每日检查分钟 |

## 安全注意事项

- 不要公开 `backend/.env`。
- 不要公开 Telegram session、SQLite 数据库、日志和备份文件。
- 默认账号密码是 `admin/admin`，公开部署前必须修改。
- 生产环境必须配置固定的 `AUTH_SECRET`。
- 生产环境建议只使用 `ADMIN_PASSWORD_HASH`，不要使用明文 `ADMIN_PASSWORD`。
- 如果反向代理启用 HTTPS，建议设置 `AUTH_COOKIE_SECURE=true`。
- 请自行申请和保管 Telegram、TMDB、Jellyfin、企业微信和 CMS 等第三方服务密钥。

## 免责声明

OctoSub 是个人媒体资源管理和自动化工具。项目不内置、不分发、不托管任何影视资源或频道数据。使用者需要自行承担账号、网络、第三方服务和资源使用相关责任，并遵守适用法律法规和平台规则。

## License

MIT License. See [LICENSE](LICENSE).
