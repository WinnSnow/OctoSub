# 模块职责说明

## 后端

- `routers/*`：HTTP 路由层。目标状态是只处理入参、调用 service、返回响应。
- `db.py`：数据库初始化和轻量迁移。
- `task_service.py`：后台任务内存状态中心，供抓取、补链、订阅检查、海报匹配和转存查询。
- `search_service.py` / `search_aggregation_service.py`：统一搜索、PanSou 搜索和 TG 实时搜索编排。
- `public_search_service.py`：公开 Telegram 页面抓取和解析。
- `scrape_service.py`：Telegram 频道抓取、补链重试和消息入库编排。
- `subscription_service.py`：订阅 CRUD、手动/定时检查、转存策略。后续应继续拆分。
- `subscription_lifecycle_service.py`：订阅完成度、缺集识别和 Jellyfin 状态同步。
- `transfer_service.py`：115 转发、企业微信回调、CMS 同步和下载历史写入。后续应继续拆分。
- `telegram_service.py`：Telegram client/session 和代理配置。后续应拆分为 client 与 proxy 两个模块。
- `poster_service.py` / `poster_match_service.py`：TMDB 搜索、海报墙和海报批量匹配。
- `jellyfin_service.py` / `jellyfin_client.py`：Jellyfin 配置、连接测试和媒体库查询。
- `library_state_service.py`：批量解析前端搜索结果并查询 Jellyfin 入库状态。

## 前端

- `src/api/*`：后端 API 调用封装。
- `src/hooks/useHomeSearch.js`：首页搜索、任务、海报墙、转存和弹窗状态。后续应继续拆成多个 hooks。
- `src/pages/*`：页面组合层。目标状态是减少业务逻辑，主要组合组件和 hooks。
- `src/components/home/*`：首页搜索栏、结果列表、任务条、海报墙。
- `src/components/subscriptions/*`：订阅表单、订阅表格、调度状态。
- `src/utils/*`：纯函数工具，适合优先保持高测试覆盖。

## 主要数据流

- 公开搜索：首页 -> `/api/search` -> PanSou -> 必要时 TG 实时搜索 -> 订阅状态注入 -> 前端结果列表。
- 本地库：频道抓取 -> `messages/links` 表 -> `/api/messages` -> 前端本地库。
- 订阅检查：调度器或手动任务 -> 搜索 -> 相关性/质量/去重 -> 自动转存或进入待确认。
- 转存：前端提交 115 链接 -> 企业微信加密转发 -> CMS/回调同步 -> 下载历史。
- 海报匹配：消息标题 -> TMDB 查询/缓存 -> 更新消息 `image_url`。
