# 后端 API 文档

所有业务接口默认需要系统登录 Cookie，公开接口除外：`/api/auth/login`、`/api/auth/logout`、`/api/auth/me`、`/api/health`、`/api/wecom/callback`。

## 认证

- `GET /api/health`：健康检查。
- `POST /api/auth/login`：系统登录。Body: `{ "username": "...", "password": "..." }`。
- `GET /api/auth/me`：获取当前登录用户。
- `POST /api/auth/logout`：退出系统登录。

## Telegram 与代理

- `GET /api/telegram/status`：Telegram client 连接和登录状态。
- `POST /api/telegram/login/send-code`：发送登录验证码。
- `POST /api/telegram/login/verify-code`：校验验证码。
- `POST /api/telegram/login/verify-password`：校验 2FA 密码。
- `POST /api/telegram/logout`：退出 Telegram 登录。
- `POST /api/telegram/reset-session`：重置本地 session 文件。
- `GET /api/proxy`：读取代理配置和当前系统连接模式。
- `POST /api/proxy`：保存代理配置。
- `PATCH /api/proxy/state`：切换代理启用状态或模式。
- `DELETE /api/proxy`：删除代理配置。
- `POST /api/proxy/test`：测试代理连接。

## 频道与抓取

- `GET /api/channels`：频道列表。
- `POST /api/channels`：新增频道。Body: `{ "url": "channel_or_tme_url" }`。
- `DELETE /api/channels/{channel_id}`：删除频道。
- `POST /api/scrape`：启动抓取任务。Body 可选：`{ "channel_name": "channel" }`。返回 `task_id`。
- `POST /api/channels/{channel_name}/retry_missing`：补链任务。返回 `task_id`。
- `POST /api/messages/retry`：重试单条消息。
- `GET /api/tasks/{task_id}`：查询后台任务状态。
  - 响应字段见 `docs/TASKS.md`。
- `GET /api/tasks`：分页查询后台任务列表。Query: `status`、`task_type`、`page`、`limit`。
- `GET /api/tasks/failure-stats`：按任务类型和失败原因聚合最近失败统计。
- `POST /api/tasks/{task_id}/retry`：重试可恢复的失败任务。
- `POST /api/tasks/{task_id}/cancel`：请求停止运行中任务。返回 `cancel_requested` 状态。

## 消息与本地库

- `GET /api/messages`：本地消息列表。
  - Query: `page`、`limit`、`search`、`channel_name`、`channel_names`。
  - `channel_name` 保留兼容；多频道筛选使用重复 query key：`channel_names=a&channel_names=b`。
- `POST /api/messages/clear`：清空全部或指定频道消息。
- `POST /api/library-states`：批量查询媒体库状态。
- `POST /api/messages/match_poster_single`：匹配单条消息海报。
- `POST /api/messages/match_posters`：启动批量海报匹配任务。返回 `task_id`；任务按唯一媒体 key 更新进度，支持通过任务取消接口停止，已匹配海报会保留。
- `POST /api/messages/update_poster`：手动更新消息海报。
- `POST /api/tmdb/search`：手动搜索 TMDB。

## 搜索与海报墙

- `GET /api/search`：统一搜索。
  - Query: `keyword`、`cloud_type`、`channels`、`force_refresh`、`tmdb_id`、`tmdb_type`、`year`、`season`、`episode`、`sort`。
  - `cloud_type` 和 `channels` 使用重复 query key。
  - `sort` 支持 `score`、`latest`、`quality`、`relevance`/`confidence`。
  - 结果项可包含 `score`、`score_reason`、`quality_tags`，用于解释综合排序和前端筛选。
- `GET /api/public-search`：公开 TG 频道搜索。
- `GET /api/poster-wall`：TMDB 海报墙。

## 订阅

- `GET /api/subscriptions`：订阅列表。
- `POST /api/subscriptions`：新增订阅。
- `PUT /api/subscriptions/{subscription_id}`：更新订阅。
- `PATCH /api/subscriptions/{subscription_id}/status`：更新订阅状态。
- `DELETE /api/subscriptions/{subscription_id}`：删除订阅。
- `POST /api/subscriptions/check`：启动手动订阅检查。Body 可选：`{ "subscription_id": 1 }`。返回 `task_id`。
- `POST /api/subscriptions/refresh-lifecycle`：后台刷新订阅 Jellyfin 入库状态。Body 可选：`{ "subscription_id": 1 }`。返回 `task_id`。
- `GET /api/subscriptions/scheduler`：订阅调度器状态。

## 转存与下载历史

- `POST /api/transfer`：提交 115 转存任务。新任务返回 `task_id`；重复资源返回 `skipped`。
- `POST /api/forward_115_link`：旧转发入口，保留兼容。
- `GET /api/pending-transfers`：待确认转存列表。Query: `status`、`limit`。
- `POST /api/pending-transfers/{pending_id}/approve`：批准待确认转存。
- `POST /api/pending-transfers/{pending_id}/reject`：拒绝待确认转存。
- `GET /api/download-history`：下载历史。Query: `subscription_id`、`status`、`page`、`limit`。返回 `{ items, total, page, limit }`。
- `POST /api/download-history/sync-cms`：启动 CMS 转存结果同步任务。返回 `task_id`。
- `POST /api/download-history`：手动新增历史记录。
- `GET /api/wecom/callback`：企业微信回调验证。
- `POST /api/wecom/callback`：企业微信转存结果回调。

## Jellyfin

- `GET /api/jellyfin/status`：Jellyfin 状态。
- `GET /api/jellyfin/config`：读取已保存配置。
- `POST /api/jellyfin/config`：保存配置。
- `POST /api/jellyfin/test`：测试连接。可传 `{ "url": "...", "api_key": "..." }` 测试当前输入，不保存配置；不传时测试已保存配置。

## 系统状态

- `GET /api/system/status`：系统健康汇总，包括数据库、Telegram、代理、Jellyfin、缓存、CMS、TMDB、调度器、运行路径、配置健康、失败任务和最近结构化事件。
- `POST /api/system/cache/cleanup`：清理过期缓存。Query 可选：`table`。
