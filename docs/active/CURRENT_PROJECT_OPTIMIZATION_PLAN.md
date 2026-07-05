# 当前项目优化推进计划

更新时间：2026-06-26

本文档作为当前项目优化的总入口。执行顺序固定为：先完成文档归档和状态区分，再按小功能闭环推进优化；每完成一个小功能，必须补对应测试，并同步更新相关文档。

## 推进原则

- 每次只推进一个小功能闭环。
- 小功能必须包含实现、测试和文档更新。
- 测试未通过时不进入下一个功能阶段。
- 未完成计划保留在 `docs/active/`。
- 完成后归档到 `docs/archive/completed/<date>/`，并更新 `docs/DOCUMENT_STATUS.md`。

## 当前阶段

| 阶段 | 状态 | 目标 | 交付物 |
| --- | --- | --- | --- |
| 阶段 0：文档归档与计划沉淀 | Done | 已完成文档归档，区分 current、active、completed、legacy 文档。 | `docs/DOCUMENT_STATUS.md`、`docs/archive/README.md`、`docs/README.md`。 |
| 阶段 1：海报补全本地复用增强 | Done | 先复用本地已有 TMDB 海报，再决定是否请求 TMDB。 | 代码实现、后端测试、`POSTER_MATCH_OPTIMIZATION_PLAN.md` 进度更新。 |
| 阶段 2：海报批量任务进度与取消 | Pending | 批量海报匹配接入真实进度和取消检查。 | 代码实现、后端/前端测试、任务文档更新。 |
| 阶段 3：失败缓存重查开关 | Pending | 手动批量补海报支持重查失败缓存，自动补海报保持缓存保护。 | API/前端实现、测试、接口文档更新。 |
| 阶段 4：前端任务条补强 | Pending | 首页任务条支持停止按钮、取消中状态和完成后刷新。 | 前端实现、测试、文档更新。 |

## 立即执行队列

1. 开始阶段 2：海报批量任务进度与取消。
2. 接入 `poster_match` 任务真实 `total/current/message` 更新。
3. 接入取消检查，停止后保留已写入海报，任务状态记录为 `cancelled`。
4. 增加对应后端测试，通过后更新 `docs/active/POSTER_MATCH_OPTIMIZATION_PLAN.md` 和 `docs/TASKS.md`。

## 详细计划入口

- `docs/active/POSTER_MATCH_OPTIMIZATION_PLAN.md`：海报补全优化的详细问题、接口约定、测试计划和阶段进度。
- `docs/DOCUMENT_STATUS.md`：文档状态和归档位置索引。
