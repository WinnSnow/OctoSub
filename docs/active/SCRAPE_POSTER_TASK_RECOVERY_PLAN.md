# 抓取与补全海报任务恢复计划

目标：本地库页面离开后再返回，仍能看到正在运行的抓取或补全海报进度；抓取完成后的自动补海报改为可追踪 `poster_match` 任务，并避免已有自动补海报运行时直接跳过新消息。

## 决策原则

- 手动“补全海报”后端接口保持不变，仍使用 `POST /api/messages/match_posters` 创建 `poster_match` 任务。
- 首页负责保存并恢复本地库相关任务 id，包括 `fetch` 和 `poster_match`。
- 抓取任务完成后，如果有新增消息，自动补海报必须是正式任务，并把 task id 写回抓取任务结果。
- 自动补海报只处理抓取新增消息；手动补全海报仍是用户显式触发的批量补齐。
- 自动补海报运行中再次抓取到新消息时，追加到内存队列，不再跳过。
- 任务表中不应长期存在没有后台 runner 的 `running` 任务；读取任务时需要识别陈旧准备中任务并标记失败。

## 实施计划

- 首页 `useHomeSearch` 新增 `tg-web-view:home-active-task-id`，启动抓取、单频道刷新、手动补全海报和转存任务时保存 task id。
- 首页挂载时优先读取 localStorage task id，通过 `getTask` 恢复；无有效任务时只从 `getTasks` 兜底查询运行中或停止中的 `fetch`。
- `poster_match` 只通过明确保存的 task id 恢复，或由 `fetch` 完成返回的 `poster_backfill_task_id` 接续展示；不从任务列表自动捞历史海报任务，避免旧的 0 进度任务常驻首页。
- 轮询到 `fetch` 完成且 result 带 `poster_backfill_task_id` 时，任务条自动切换到对应 `poster_match`。
- `scrape_task_service.run_scrape_task` 在完成抓取前调用 `schedule_poster_backfill`，把返回的 task id 写入 `poster_backfill_task_id`。
- `scrape_poster_backfill_service.schedule_poster_backfill` 创建正式 `poster_match` 任务，返回 task id。
- 自动补海报维护 `_PENDING_POSTER_BACKFILL_IDS` 队列，运行中再次 schedule 时追加 ids 并返回当前 task id。
- 自动补海报 runner 循环处理运行期间追加的新批次，完成后汇总 `processed_messages`、`updated_messages`、`tmdb_requests`、`batches`、`queued_messages`。
- 任务服务读取 `running/cancel_requested` 任务时识别陈旧任务：
  - `current=0,total=0,message` 包含“准备中”且超过 5 分钟未更新，标记为 failed。
  - 其他运行中任务超过 30 分钟未更新，标记为 failed。
- 前端恢复 localStorage 中的 `poster_match` 时也过滤陈旧的 0 进度准备中任务，并清理保存的 task id。
- 前端轮询任务最终状态时按 task id 做幂等处理，避免同一个 completed/failed/cancelled 响应重复触发 toast、刷新或阶段切换。

## 当前进度

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| 首页任务恢复 | Done | `useHomeSearch` 可从 localStorage 恢复明确保存的任务；无保存任务时只兜底恢复 `fetch`，避免旧海报任务常驻。 |
| 手动补全海报恢复 | Done | 点击“补全海报”会保存 `poster_match` task id，切换页面回来可恢复进度。 |
| 抓取到补海报切换 | Done | `fetch` completed 后若带 `poster_backfill_task_id`，前端自动切换到补海报任务。 |
| 自动补海报正式任务 | Done | 抓取后自动补海报创建 `poster_match` 任务，并写入抓取任务结果。 |
| 自动补海报队列合并 | Done | 运行中再次 schedule 会追加消息 id，不再跳过新批次。 |
| 陈旧任务兜底 | Done | 后端读取任务时会把陈旧 running 任务标记 failed；前端不会恢复陈旧 0 进度海报任务。 |
| 完成提示幂等 | Done | 同一个任务最终状态只处理一次，避免“所有频道同步完成”等提示重复弹出。 |
| 测试覆盖 | Done | 已补后端抓取/自动补海报测试和前端任务恢复测试。 |

## 验证记录

- 2026-06-28：通过 `cd backend && ../venv/bin/python -m unittest test_scrape_task_service test_scrape_poster_backfill_service test_poster_match_batch_service`，18 tests。
- 2026-06-28：通过 `cd frontend && npm test -- --run src/hooks/useHomeSearch.test.js src/components/home/TaskProgressStrip.test.jsx`，18 tests。

## 后续复盘点

- 当前自动补海报队列是内存队列；如果后端进程重启，未处理队列不会恢复。后续如需强可靠性，可增加数据库持久队列。
- 首页恢复任务时只显示一个当前任务；无明确保存 task id 时只兜底恢复抓取任务，手动补全海报必须来自本页面保存的 task id。
- 转存任务 id 也会保存，但恢复优先级低于抓取和补海报；后续可按页面语义拆分不同 localStorage key。
