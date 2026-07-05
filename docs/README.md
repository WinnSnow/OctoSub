# 项目文档索引

- `API.md`：后端接口按业务域分组说明。
- `MODULES.md`：前后端模块职责、主要数据流和后续拆分方向。
- `TESTING.md`：后端 unittest、前端 Vitest、当前虚拟环境和本地测试命令。
- `RUNTIME_ARTIFACTS.md`：运行产物保留策略、敏感文件和备份建议。
- `TASKS.md`：后台任务 API、状态字段、前端轮询入口和当前接入点。
- `DOCUMENT_STATUS.md`：文档状态索引，区分 current、active、completed 和 legacy。
- `active/`：当前仍需推进的计划和进度文档。
- `archive/completed/`：已经完成并验证过的阶段性计划、进度和总结文档。
- `archive/legacy/`：旧版参考文档，不作为当前实现依据。

这些文档用于后续调试、接口联调、测试回归和代码拆分规划。运行产物默认保留，不作为源码提交或对外分享。

## 当前活跃计划

- `active/CURRENT_PROJECT_OPTIMIZATION_PLAN.md`：当前项目优化推进总入口和阶段顺序。
- `active/POSTER_MATCH_OPTIMIZATION_PLAN.md`：海报补全本地复用、进度、停止和失败缓存开关优化。

## 已完成归档

- `archive/completed/2026-06-13/`：v1.0 交付、完成报告、早期开发计划和启动说明。
- `archive/completed/2026-06-14/`：安全审计与质量检查报告。
- `archive/completed/2026-06-26/`：后端拆分、前端拆分、抓取管线改造等已完成文档。

## 旧版参考

- `archive/legacy/API_LEGACY.md`：根目录旧版 API 文档，当前接口说明以 `docs/API.md` 为准。
