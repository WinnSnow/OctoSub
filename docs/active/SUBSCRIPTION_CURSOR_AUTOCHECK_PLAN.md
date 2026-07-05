# 订阅追更游标自动检查计划

更新时间：2026-06-27

目标：订阅自动检查只沿 Jellyfin 当前追更进度向前推进一集。历史缺失只标记和展示，由用户手动搜索处理，避免一次性搜索多个缺失集或 fallback 到泛关键词误转存。

## 行为定义

- Jellyfin 一集都没有：自动检查 `E1`。
- Jellyfin 最高已有 `E20`，TMDB 目标到 `E30`：自动检查 `E21`。
- Jellyfin 已有 `E1-E10、E20-E30`：自动不搜索，展示历史缺失 `E11-E19`。
- 某一集搜索失败后，下次仍检查同一集，直到 Jellyfin 入库后游标才前进。
- TV 精准订阅没有自动检查目标时，不 fallback 搜纯标题。

## 实施计划

| 阶段 | 状态 | 内容 | 验收标准 |
| --- | --- | --- | --- |
| 阶段 1：后端游标状态 | Done | `episode_state` 增加 `max_existing`、`auto_search_target`、`historical_missing`、`future_available_missing`。 | 能区分历史缺失和下一集自动检查目标。 |
| 阶段 2：自动检查目标 | Done | 订阅检查只读取 `auto_search_target`；TV+TMDB 无目标时直接跳过搜索。 | E20/30 只搜 E21；E1-E10,E20-E30 不自动搜索 E11-E19。 |
| 阶段 3：定时任务配置 | Done | 增加 `SUBSCRIPTION_CHECK_INTERVAL_SECONDS`，默认 3600 秒；设为 0 时沿用每日固定时间。 | 支持 30 分钟、1 小时、每天三种使用方式。 |
| 阶段 4：前端展示 | Done | 订阅页展示下次自动检查、历史缺失、后续待追；按钮文案改为“检查下一集”。 | 用户能看清自动会搜哪一集、哪些缺失需手动处理。 |
| 阶段 5：测试与回归 | Done | 更新后端/前端测试并运行回归。 | 相关定向测试和全量测试通过。 |

## 配置

- `SUBSCRIPTION_CHECK_INTERVAL_SECONDS=1800`：每 30 分钟检查。
- `SUBSCRIPTION_CHECK_INTERVAL_SECONDS=3600`：每 1 小时检查，当前默认。
- `SUBSCRIPTION_CHECK_INTERVAL_SECONDS=0`：使用 `SUBSCRIPTION_CHECK_HOUR` 和 `SUBSCRIPTION_CHECK_MINUTE` 每天固定时间检查。

## 进度记录

- 2026-06-27：完成后端追更游标状态计算，自动目标从 `min(missing)` 改为 `max(existing)+1`。
- 2026-06-27：完成 TV 精准订阅无自动目标时跳过搜索，避免历史缺失触发泛搜。
- 2026-06-27：完成订阅定时任务 interval 配置，默认每 1 小时。
- 2026-06-27：完成订阅页展示和按钮文案调整。
- 2026-06-27：验证通过：`cd backend && ../venv/bin/python -m unittest test_subscription_lifecycle_service test_subscription_check_item_service test_subscription_check_search_service test_subscription_schedule_state_service`，19 tests。
- 2026-06-27：验证通过：`cd frontend && npm test -- --run src/utils/subscriptions.test.js src/pages/SubscriptionsPage.test.jsx src/components/subscriptions/SubscriptionSchedulerStatus.test.jsx`，6 tests。
- 2026-06-27：验证通过：`cd backend && ../venv/bin/python -m unittest discover`，297 tests。
- 2026-06-27：验证通过：`cd frontend && npm test -- --run`，64 tests。
