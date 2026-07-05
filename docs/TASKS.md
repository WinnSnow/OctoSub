# 后台任务说明

后台任务状态由后端 `task_service.py` 统一维护，接口为 `GET /api/tasks/{task_id}`。

任务会持久化到 SQLite `tasks` 表，服务重启后仍可通过任务 ID 或任务中心列表查看历史状态。

## 任务来源

- `POST /api/scrape`：频道抓取。
- `POST /api/channels/{channel_name}/retry_missing`：补链。
- `POST /api/messages/match_posters`：批量海报匹配。
- `POST /api/subscriptions/check`：手动订阅检查。
- `POST /api/subscriptions/refresh-lifecycle`：刷新订阅入库状态。
- `POST /api/transfer`：115 转存提交。
- `POST /api/download-history/sync-cms`：CMS 转存结果同步。

## 查询接口

- `GET /api/tasks/{task_id}`：查询单个任务详情，兼容旧进度轮询。
- `GET /api/tasks`：分页查询任务中心列表。
  - Query: `status`、`task_type`、`page`、`limit`。
  - `status` 支持 `all`、`running`、`cancel_requested`、`cancelled`、`completed`、`failed`、`partial_failed`。
- `GET /api/tasks/failure-stats`：按任务类型和错误原因聚合失败统计。
- `POST /api/tasks/{task_id}/retry`：重试支持恢复的失败任务。
- `POST /api/tasks/{task_id}/cancel`：请求停止运行中任务。停止是协作式取消，任务会先保存已完成结果，再进入 `cancelled`。

## 状态字段

- `task_id`：任务 ID。
- `type`：任务类型，例如 `scrape`、`retry_missing_links`、`poster_match`、`subscription_check`、`transfer`。
- `title`：任务标题。
- `status`：`running`、`cancel_requested`、`cancelled`、`completed`、`failed`。前端兼容 `partial_failed`。
- `current` / `total`：进度计数；`total=0` 表示无法计算百分比。
- `message`：当前状态文案。
- `result`：任务完成后的结构化结果。
- `error`：失败原因。
- `created_at`、`updated_at`、`finished_at`：Unix 时间戳。

## 海报匹配任务

`poster_match` 的 `current` / `total` 按唯一媒体 key 统计。批量匹配会持续更新 `result`，包含 `processed_messages`、`unique_media_keys`、`database_key_cache_hits`、`poster_cache_hits`、`tmdb_requests`、`updated_messages`、`skipped_non_media`。

请求停止后不再领取新的 TMDB key，不强杀已经发出的请求；已返回海报的请求仍会写入数据库。最终状态为 `cancelled`，`result.cancelled = true`，并保留 `current`、`total`、`updated_messages` 等统计。

## 前端入口

- API 封装：`frontend/src/api/tasks.js`。
- 首页轮询：`frontend/src/hooks/useHomeSearch.js`。
- 首页展示：`frontend/src/components/home/TaskProgressStrip.jsx`。
- 任务中心：`frontend/src/pages/TasksPage.jsx`。

后续页面接入任务状态时应复用 `api/tasks.js`，不要把任务查询继续放在搜索、订阅或转存 API 模块里。
