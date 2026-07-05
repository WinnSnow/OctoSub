# 运行产物说明

本项目保留运行产物用于调试、复现问题和本地验证，但运行产物不属于源码，不应提交到版本控制。

## 目录约定

- `runtime/data/`：SQLite 数据库和相关 WAL/SHM 文件。保留后可以复现本地库、订阅、下载历史和缓存问题。
- `runtime/sessions/`：Telegram session 文件。用于保持登录态，包含敏感认证信息。
- `runtime/logs/`：后端、前端和任务日志。用于排查外部服务、转存、抓取和定时任务问题。
- `runtime/backups/`：手动备份、清理前备份和问题复现快照。
- `runtime/backend.lock`：后端单实例锁文件。默认由 `RUNTIME_DIR` 推导，也可以通过 `BACKEND_LOCK_PATH` 指定。
- `venv/`：Python 虚拟环境。建议创建在项目根目录下的 `venv/`，用于本地开发和测试，不属于源码。
- `frontend/node_modules/`：npm 依赖目录。用于本地开发和测试，不属于源码。
- `frontend/dist/`：前端构建产物。可用于生产包验证和部署回归对比。

## 保留原则

- 不主动删除运行产物。问题复现、接口回归、前端构建对比和登录态验证都可能依赖这些文件。
- 需要清理前先复制到 `runtime/backups/`，并记录清理时间和原因。
- `venv/`、`frontend/node_modules/`、`frontend/dist/` 可本地保留，但不要当作源码维护；依赖变更应以 `requirements.txt`、`package.json`、`package-lock.json` 为准。
- 可分享文档和源码时，不分享 `runtime/data/`、`runtime/sessions/`、`runtime/logs/` 和 `.env`。

## 路径配置

- `RUNTIME_DIR`：运行产物根目录；未配置时默认是项目根目录下的 `runtime/`。
- `DATA_DIR`、`SESSION_DIR`、`LOG_DIR`：分别控制数据、Telegram session、日志目录。如果未显式配置 `RUNTIME_DIR`，后端会优先从这些目录推导运行产物根目录。
- `BACKEND_LOCK_PATH`：后端锁文件路径。默认是 `${RUNTIME_DIR}/backend.lock`。

## 敏感文件

以下文件可能包含账号、密钥、登录态或私有资源链接，分享前必须脱敏：

- `backend/.env`
- `runtime/sessions/*.session`
- `runtime/data/*.db`
- `runtime/logs/*.log`

## 调试建议

复现问题前先停止服务，再备份运行数据：

```bash
./stop.sh
mkdir -p runtime/backups/manual
cp -a runtime/data runtime/sessions runtime/logs runtime/backups/manual/
```

如果需要重建依赖环境：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

cd frontend
npm install
```

如果需要重新生成前端构建产物：

```bash
cd frontend
npm run build
```
