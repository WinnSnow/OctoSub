# 海报补全优化计划

更新时间：2026-06-26

本文档跟踪当前未完成的海报补全优化。推进顺序固定为：先完成文档归档和计划沉淀，再按本计划逐项改造；每完成一个小功能，必须补对应测试，并同步更新本文档。

## 当前问题

- 批量海报匹配创建了 `poster_match` 任务，但没有设置真实 `total`，匹配过程中也没有持续更新 `current/message`，前端只能看到不明确的动画进度。
- 任务中心和取消接口已经存在，但海报批量匹配没有接收 `task_id`，也不检查 `cancel_requested`，所以点击停止后后台仍会继续跑。
- 单条补海报会忽略失败缓存，批量补海报默认使用 7 天 miss 缓存；历史失败较多时，手动批量补全可能看起来“没有效果”。
- 本地已有海报不能稳定复用。实际案例：`熔炉边境 (2025)` 已有一条消息带 TMDB 海报和 `TMDB ID：1379413`，另一条同名同年缺海报消息因为没有 TMDB ID 且文本包含推广内容，被候选判定跳过，导致没有机会沿用本地已有海报。

## 实施计划

| 阶段 | 状态 | 目标 | 验收标准 |
| --- | --- | --- | --- |
| 阶段 1：本地海报复用增强 | Done | 已有 TMDB 海报按 TMDB key、标题同年 key、宽松 title-any key 建索引；待补消息先尝试本地复用，再决定是否请求 TMDB。 | `熔炉边境 (2025)` 这类同名同年消息可沿用已有海报，不额外请求 TMDB；标题同名但年份不同不复用。 |
| 阶段 2：任务进度与取消 | Done | 批量海报匹配接入 `task_id`、`update_task`、`is_cancel_requested`、`cancel_task`；按唯一媒体 key 推进进度。 | 前端能看到 `current / total`；点击停止后不再发起新的 TMDB 请求，已写入结果保留。 |
| 阶段 3：失败缓存开关 | Pending | 手动批量补海报增加 `重查失败缓存` 开关，请求体传 `force_retry_misses`；自动抓取后的后台补海报仍使用 miss 缓存。 | 开关开启时 miss 缓存不阻止 TMDB 请求；关闭时保持现有缓存保护。 |
| 阶段 4：前端任务条补强 | Done | 首页任务条支持停止按钮和 `cancel_requested` 展示；完成/停止后刷新当前本地结果。 | 主页无需进入任务中心也能停止海报匹配，状态显示清晰。 |

## 接口和行为约定

- `POST /api/messages/match_posters` 增加可选 JSON 请求体：
  - `force_retry_misses: boolean`
- 未传请求体时保持兼容，默认 `false`。
- 前端手动批量补全默认开启“重查失败缓存”，自动后台补海报不强制重查。
- 本地复用优先于 TMDB 查询：
  - 强匹配：`tmdb:{type}:{tmdb_id}`
  - 标题匹配：`title:{type}:{clean_title}:{year}`
  - 宽松匹配：`title:any:{clean_title}:{year}`
- 宽松匹配只用于复用已有本地 TMDB 海报，不用于直接请求 TMDB。
- 停止语义为保存部分结果：已经写入数据库的海报不回滚，任务最终状态为 `cancelled`，`result.cancelled = true`。
- `poster_match` 进度按唯一媒体 key 统计，`total` 为本次待处理唯一 key 数，`current` 随本地复用、缓存命中、跳过项和 TMDB 请求完成推进。
- 用户请求停止后，worker 不再领取新的 TMDB key；已领取且正在进行中的 TMDB 请求会自然结束，若找到海报仍会写入 `messages.image_url` 并计入 `updated_messages`。

## 测试计划

- 后端测试：
  - 已有海报消息带 TMDB ID，缺海报消息只有同名同年标题时，可以本地复用海报。
  - 带推广内容而被判 `negative_content` 的缺海报消息，仍可先尝试本地复用。
  - 同名不同年份不复用。
  - 类型推断为 `movie/tv/unknown` 不一致但同名同年时，可通过 `title:any` 复用。
  - `force_retry_misses=true/false` 分别覆盖 miss 缓存行为。
  - 取消请求后不再发起新的 TMDB 请求，已写入统计保留。
- 前端测试：
  - 海报补全开关值正确传给 API。
  - 任务条显示真实进度。
  - 停止按钮调用 `cancelTask(task_id)`，`cancel_requested` 状态下禁用重复点击。
- 回归验证：
  - 单条补海报继续强制重查 miss 缓存。
  - 抓取后的自动补海报继续使用 miss 缓存。
  - 任务中心已有停止能力不退化。

## 进度记录

- 2026-06-26：完成文档归档规则整理；本计划创建为当前 active 文档。
- 2026-06-26：完成阶段 1 本地海报复用增强。当前实现会从已有 TMDB 海报消息构建 `tmdb:{type}:{tmdb_id}`、`title:{type}:{clean_title}:{year}`、`title:any:{clean_title}:{year}` 复用 key；低置信或推广文本不会请求 TMDB，但仍可优先复用本地同名同年海报。
- 2026-06-26：阶段 1 验证通过：`cd backend && ../venv/bin/python -m unittest test_poster_match_batch_service test_poster_match_batch_db_service test_poster_match_cache_service`，15 tests。
- 2026-06-26：完成阶段 2 和阶段 4。批量海报匹配按唯一媒体 key 更新任务进度，首页任务条支持停止 `poster_match`；取消后最终状态为 `cancelled`，已匹配海报保留并刷新前端列表。

## 固定推进规则

- 每次只完成一个小功能闭环。
- 每个小功能必须包含对应测试。
- 测试通过后更新本文档的阶段状态和进度记录。
- 未完成阶段保留在 `docs/active/`，完成后再归档到 `docs/archive/completed/`。
