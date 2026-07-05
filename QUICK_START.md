# OctoSub 快速参考

## Docker 启动

推荐使用 Docker Compose 部署。Compose 会同时启动前端、后端和 PanSou 搜索服务。

```bash
git clone https://github.com/WinnSnow/OctoSub.git
cd OctoSub
./deploy.sh start
```

默认访问地址：`http://localhost:55443`。

首次启动会按 `backend/.env.example` 创建 `backend/.env`。长期运行前建议先配置管理员账号、`AUTH_SECRET`、Telegram、TMDB、Jellyfin、CMS/转存等参数。

默认登录账号是 `admin`，默认密码是 `admin`。公开部署前务必修改。

## 本地开发

本地开发可以用脚本启动前后端：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
./start.sh
```

默认前端地址：`http://localhost:5172`，后端地址：`http://localhost:8001`。

`start.sh` 只启动前后端。公开搜索依赖 PanSou；如果需要本地公开搜索，可以自行部署 PanSou 并把 `PANSOU_BASE_URL` 指向它，或使用 `./deploy.sh dev` 启动 Docker 开发环境。

## 关键配置

配置文件：`backend/.env`

| 配置 | 用途 |
| --- | --- |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` / `AUTH_SECRET` | 登录认证 |
| `API_ID` / `API_HASH` | Telegram 登录、频道抓取 |
| `PANSOU_BASE_URL` / `PANSOU_ENABLED` | PanSou 公开搜索 |
| `TMDB_API_KEY` | 海报和媒体信息 |
| `FORWARD_URL` / `WECOM_*` / `CMS_*` | 115/CMS/企业微信转存和状态回写 |
| `JELLYFIN_URL` / `JELLYFIN_API_KEY` | Jellyfin 媒体库检查 |

115 转存成功后的状态回写依赖 CMS 相关接口和回调/同步逻辑。如果使用的不是兼容 CMS 的转存项目，可能需要自行调整回调解析或同步接口。

## 常见问题

- 登录失败：检查 `backend/.env` 里的管理员账号、密码哈希和 `AUTH_SECRET`。
- 公开搜索结果少或失败：检查 PanSou 是否启动，以及 `PANSOU_BASE_URL` 是否可访问。
- Telegram 频道抓取不可用：检查 `API_ID`、`API_HASH`、代理和 Telegram session。
- 转存后状态不更新：检查 CMS/企业微信回调配置，以及转存项目是否兼容当前状态回写逻辑。

更多说明见 [README.md](README.md) 和 [DEPLOYMENT.md](DEPLOYMENT.md)。
