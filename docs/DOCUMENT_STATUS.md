# 文档状态索引

更新时间：2026-06-26

本文档用于区分当前可维护文档、仍在推进的计划文档、已完成归档文档和旧版参考文档。后续新增文档时先归入对应状态，避免根目录和归档目录混放。

## 状态定义

- `Current`：当前仍有效的说明文档，用于开发、联调、测试或部署参考。
- `Active`：未完成或正在推进的计划文档，必须保留在 `docs/active/`。
- `Completed`：已经完成、已验证或已被当前计划替代的阶段性文档，统一归档到 `docs/archive/completed/`。
- `Legacy`：旧版参考文档，内容可能不再完全匹配当前实现，仅用于追溯。

## Current 文档

| 文档 | 状态 | 用途 |
| --- | --- | --- |
| `README.md` | Current | 项目总览、功能说明和入口导航。 |
| `QUICK_START.md` | Current | 本地和 Docker 快速启动参考。 |
| `DEPLOYMENT.md` | Current | 部署流程、配置和排障说明。 |
| `frontend/README.md` | Current | 前端工程说明。 |
| `docs/API.md` | Current | 当前后端 API 按业务域分组说明。 |
| `docs/MODULES.md` | Current | 前后端模块职责和主要数据流。 |
| `docs/TESTING.md` | Current | 后端 unittest、前端 Vitest 和本地测试命令。 |
| `docs/RUNTIME_ARTIFACTS.md` | Current | 运行产物、敏感文件和备份策略。 |
| `docs/TASKS.md` | Current | 后台任务接口、状态字段和前端入口。 |

## Active 文档

| 文档 | 状态 | 下一步 |
| --- | --- | --- |
| `docs/active/CURRENT_PROJECT_OPTIMIZATION_PLAN.md` | Active | 作为当前优化推进总入口，按阶段更新状态。 |
| `docs/active/POSTER_MATCH_OPTIMIZATION_PLAN.md` | Active | 按阶段完成海报补全本地复用、任务进度/取消、失败缓存开关和前端任务条补强。 |

## Completed 归档

| 目录 | 状态 | 内容 |
| --- | --- | --- |
| `docs/archive/completed/2026-06-13/` | Completed | v1.0 交付、完成报告、早期开发计划和启动说明。 |
| `docs/archive/completed/2026-06-14/` | Completed | 安全审计与质量检查报告。 |
| `docs/archive/completed/2026-06-26/` | Completed | 后端拆分、前端拆分、抓取管线改造和验证记录。 |

## Legacy 归档

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| `docs/archive/legacy/API_LEGACY.md` | Legacy | 根目录旧版 API 文档，已由 `docs/API.md` 作为当前接口文档替代。 |

## 维护规则

- 未完成计划只放在 `docs/active/`，不要放进归档目录。
- 完成计划必须记录测试或验证结果，再移动到 `docs/archive/completed/<date>/`。
- 当前有效说明文档保留在根目录或 `docs/` 根部，便于开发和联调时直接查阅。
- 旧版但仍有追溯价值的文档放在 `docs/archive/legacy/`，不要作为当前实现依据。
