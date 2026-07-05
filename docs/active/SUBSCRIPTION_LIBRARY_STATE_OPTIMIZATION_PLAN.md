# 订阅与入库状态优化计划

更新时间：2026-06-27

目标：订阅页展示具体缺失集数，搜索页和海报墙后续可复用本地入库状态，只在确认具体集数已入库时显示“已入库”，未入库不显示，减少 Jellyfin 实时查询。

## 当前问题

- 订阅只持久化 `progress_current/progress_total`，不能说明具体哪些集已入库、哪些集缺失。
- 搜索结果如果只依赖订阅进度，无法严格判断 `E83` 是否已入库。
- 未订阅但 Jellyfin 已存在的内容，不能只靠订阅状态标注，需要后续建立全局 Jellyfin 索引。

## 分阶段计划

| 阶段 | 状态 | 目标 | 验收标准 |
| --- | --- | --- | --- |
| 阶段 1：订阅精确集数状态 | Done | 订阅生命周期同步时保存 expected/existing/missing/next_missing。 | 订阅 API 返回具体已入库和缺失集数；`83/100` 不再是唯一状态来源。 |
| 阶段 2：订阅页缺失集展示 | Done | 前端订阅列表展示缺失摘要，如 `缺 E84-E100`，详情展示完整缺失集。 | 用户能直接看到缺哪些集，而不是只看到 `83/100`。 |
| 阶段 3：搜索结果复用订阅精确状态 | Done | 搜索结果解析目标集数，只在订阅 `existing_episodes` 命中时显示 `E83 已入库`。 | 未入库不显示；已入库具体集显示准确；不因 `83/100` 计数误判。 |
| 阶段 4：全局 Jellyfin 入库索引 | Done | 同步 Jellyfin 全库电影/剧集/集数到本地索引。 | 未订阅内容也能在搜索和海报墙显示已入库状态。 |
| 阶段 5：刷新与缓存策略 | Done | 转存完成、手动刷新、定时任务触发局部/全量刷新。 | 搜索页不频繁查 Jellyfin，状态仍能按操作及时更新。 |

## 数据约定

订阅状态新增 `episode_state`：

```json
{
  "expected_episodes": { "1": [1, 2, 3] },
  "existing_episodes": { "1": [1, 2] },
  "missing_episodes": { "1": [3] },
  "next_missing": { "season": 1, "episode": 3 }
}
```

注意：搜索结果判断 `E83 已入库` 必须看 `existing_episodes[season]` 是否包含 `episode`，不能只看 `progress_current >= 83`。

后续订阅自动检查已改为追更游标模型，`next_missing` 仅保留为兼容字段和总体缺失提示。自动检查应读取 `auto_search_target`：

```json
{
  "max_existing": { "season": 1, "episode": 20 },
  "auto_search_target": { "season": 1, "episode": 21 },
  "historical_missing": { "1": [11, 12] },
  "future_available_missing": { "1": [22, 23] }
}
```

历史缺失只展示，不参与定时自动搜索。

## 验证计划

- 后端：
  - 订阅生命周期能生成 exact episode state。
  - 完整入库时 missing 为空，状态 completed。
  - 部分入库时返回 next_missing 和缺失集。
  - 订阅 API 返回 `episode_state`。
- 前端：
  - 订阅页显示缺失区间摘要。
  - 搜索结果仅对 existing 命中的具体集显示已入库。
  - 未命中不显示未入库标签。

## 进度记录

- 2026-06-27：完成阶段 1 后端基础。新增 `subscriptions.episode_state_json` 兼容字段；订阅生命周期同步时持久化 `expected_episodes`、`existing_episodes`、`missing_episodes`、`next_missing`；订阅 API 和订阅状态 payload 返回 `episode_state`。
- 2026-06-27：验证通过：`cd backend && ../venv/bin/python -m unittest discover`，276 tests。
- 2026-06-27：完成阶段 2。订阅列表在入库进度下展示缺失集摘要，支持连续区间和多季前缀，例如 `缺 E84-E100`、`缺 S01E12、S02E1-E3`。
- 2026-06-27：验证通过：`cd frontend && npm test -- --run`，60 tests。
- 2026-06-27：完成阶段 3。搜索结果复用订阅保存的 `episode_state.existing_episodes`，带具体集数的资源只有在精确命中时显示 `E83 已入库`；未入库或缺失集不显示状态。
- 2026-06-27：验证通过：`cd backend && ../venv/bin/python -m unittest test_subscription_state_service test_subscription_lifecycle_service test_subscription_crud_service test_search_aggregation_service`，15 tests；`cd frontend && npm test -- --run src/components/home/SearchResultsList.test.jsx src/utils/media.test.js`，10 tests。
- 2026-06-27：完成阶段 4。新增 `jellyfin_library_items` 本地索引表，支持后台同步 Jellyfin 全库电影、剧集和分集；搜索入库状态优先查本地索引，索引未初始化时才回退实时 Jellyfin 查询。
- 2026-06-27：Jellyfin 配置页新增媒体库索引摘要和“同步媒体库索引”入口；同步任务类型为 `jellyfin_library_sync`。
- 2026-06-27：验证通过：`cd backend && ../venv/bin/python -m unittest discover`，285 tests；`cd frontend && npm test -- --run`，61 tests。
- 2026-06-27：完成阶段 5。新增 Jellyfin 索引节流刷新策略：企业微信转存回调成功、CMS 同步发现成功记录、每日订阅检查完成后会按最小间隔触发索引刷新；手动同步任务完成后前端自动刷新索引摘要。
- 2026-06-27：新增环境变量 `JELLYFIN_LIBRARY_INDEX_REFRESH_MIN_INTERVAL_SECONDS`，默认 1800 秒，避免频繁全量扫描 Jellyfin。
- 2026-06-27：验证通过：`cd backend && ../venv/bin/python -m unittest discover`，287 tests；`cd frontend && npm test -- --run`，61 tests。
- 2026-06-27：订阅自动检查迁移为追更游标模型，自动只搜索 Jellyfin 最高已入库集之后的下一集；历史缺失只展示，由用户手动处理。详细执行计划见 `docs/active/SUBSCRIPTION_CURSOR_AUTOCHECK_PLAN.md`。
