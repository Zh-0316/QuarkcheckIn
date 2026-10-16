# 夸克网盘签到助手

夸克网盘每日自动签到工具。支持Windows 部署，支持多账户管理、托盘后台静默运行；另提供 Docker 部署，支持多架构，适合24小时运行。

## 功能特性

- **Windows 版**：多账户独立签到；每天 00:30 精确定时 + 系统唤醒监听 + 4 小时兜底，三层防护防漏签；今日已签不重复请求；托盘后台运行、开机自启
- **Docker 版**：环境变量配置多账号；容器启动即签一次 + 内置 cron 定时；断网自动重试；多架构现成镜像，无需自行构建

## 抓包获取签到 URL

使用本程序不需要账号密码，只需要从手机端抓一条签到请求的 URL，程序只依赖其中的 `kps`、`sign`、`vcode` 三个鉴权参数，其余参数会自动忽略。

1. 手机安装抓包工具（如 Reqable 等），开始抓包
2. 打开夸克网盘 APP，进入签到页面（进入即会自动签到）
3. 在抓包工具中找到 URL 类似下面的请求
   ```
   https://drive-member.quark.cn/1/clouddrive/capacity/growth/info?kps=xxxx&sign=xxxx&vcode=xxxx
   ```
4. 复制该请求的完整 URL（必须包含 `kps`、`sign`、`vcode` 三个参数）

抓到的 URL 用在下面两处之一：GUI 版粘贴到「添加用户」；Docker 版填入 `COOKIE_QUARK` 环境变量。

> 注意：`kps` / `sign` / `vcode` 有时效，失效后程序会提示"获取成长信息失败"，重新抓一条更新即可；多账户需分别抓包。

## Windows 部署

### 方式一：直接使用（推荐）

从 [Releases](https://github.com/Zh-0316/QuarkcheckIn/releases) 下载最新版 `QuarkCheckIn.zip`，解压到任意文件夹，双击 `QuarkCheckIn.exe` 运行即可。

> 首次运行会在 exe 同目录下生成 `users.json`、`sign_records.json`、`settings.json` 三个数据文件，请勿删除。

### 方式二：从源码运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python checkIn_Quark.py
```

### 方式三：自行打包

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "QuarkCheckIn" --icon "icon.ico" --add-data "icon.ico;." checkIn_Quark.py
```

## Docker 部署

`docker/` 支持docker 部署：环境变量配置账号、容器内置 cron 定时签到。抓包方式与上文相同，镜像由 GitHub Actions 自动构建发布，直接拉取即可。

### 环境变量说明

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `COOKIE_QUARK` | ✅ | — | 账号配置，格式 `user=任意名称; url=抓包链接整段;`（`user` 只用来区分账号，随便填）；多账号用 `&&` 拼接，数量不限 |
| `CRON_SCHEDULE` | 否 | `0 9 * * *` | 定时签到时间（cron 表达式：分 时 日 月 周） |
| `TZ` | 建议 | — | 填 `Asia/Shanghai`，保证定时按北京时间执行 |

说明：
- `user=` 随便填写，它只用于在日志里区分是哪个账号
- 签到接口幂等，一天跑多次也不会重复签到，只有当天第一次真正签；推荐设 `0 */6 * * *` 多次兜底，防止断网恰好错过签到点导致漏签
- 容器**每次启动时都会立即先签一次**，之后才按 cron 定时执行

### 多账号配置

账号数量不限，多个账号用 `&&` 拼成一行，整串作为 `COOKIE_QUARK` 的值：

```
user=账号A; url=抓包链接A;&&user=账号B; url=抓包链接B;
```

### 方式一：命令行一键运行

```bash
docker run -d --name quark-checkin \
  -e TZ=Asia/Shanghai \
  -e CRON_SCHEDULE="0 9 * * *" \
  -e COOKIE_QUARK="user=用户名; url=抓包链接整段粘贴;" \
  --restart unless-stopped \
  ghcr.io/zh-0316/quark-checkin:latest
```

常用命令：

```bash
docker logs -f quark-checkin                                # 查看签到日志
docker exec quark-checkin python /app/checkIn_Quark.py      # 手动补签一次
```

### 方式二：NAS 图形界面

在 NAS 的 Docker 管理界面找到 **「Compose」**，新建项目并粘贴以下内容，点击部署即可（首次部署会自动拉取镜像）：

```yaml
services:
  quark-checkin:
    image: ghcr.io/zh-0316/quark-checkin:latest
    container_name: quark-checkin
    restart: unless-stopped
    environment:
      TZ: Asia/Shanghai
      CRON_SCHEDULE: "0 9 * * *"
      COOKIE_QUARK: "user=用户名; url=抓包链接整段粘贴;"
```

- **验证结果**：部署完成后打开容器日志，会打印当前定时时间和首次签到结果
- **参数过期**：编辑这段 YAML，替换 `COOKIE_QUARK` 的值后重新部署即可，无需重建镜像
- **升级版本**：在项目页面选择「重新拉取镜像并重建容器」

### 方式三：克隆源码本地构建

```bash
git clone https://github.com/Zh-0316/QuarkcheckIn.git
cd QuarkcheckIn/docker
docker compose up -d --build
```

> 仓库自带的 `docker-compose.yml` 使用 `build: .`（本地构建），若想直接用发布好的现成镜像，把其中的 `build: .` 替换为上面方式二的 `image:` 一行即可。

## 项目结构

```
QuarkcheckIn/
├── checkIn_Quark.py              # Windows 版主程序
├── icon.ico                      # 程序图标
├── requirements.txt              # Windows 项目依赖
├── README.md / LICENSE           # 说明与许可证
├── docker/                       # Docker目录
│   ├── checkIn_Quark.py          # Docker签到脚本
│   ├── Dockerfile                # 镜像构建定义
│   ├── docker-compose.yml        # compose 部署模板
│   ├── entrypoint.sh             # 容器启动 + cron 安装
│   └── requirements.txt          # Docker 部署依赖
└── .github/workflows/
    └── docker-publish.yml        # 推送后自动构建多架构镜像并发布到 ghcr
```

Windows 版运行后自动生成的数据文件（与 exe 或脚本同目录）：

```
├── users.json                # 用户数据
├── sign_records.json         # 签到记录
└── settings.json             # 程序设置
```

## 技术栈

- Python 3.9+（Windows 版建议 3.13；Docker 镜像基于 python:3.11-slim）
- PyQt6（GUI 框架，仅 Windows 版）
- requests（HTTP 请求）
- PyInstaller（打包工具）
- GitHub Actions + ghcr.io（Docker 镜像自动构建与发布）

## 致谢

- 源码改编自 [@BNDou](https://github.com/BNDou/Auto_Check_In) 的脚本

## 许可证

本项目基于 AGPL-3.0 协议开源，详见 [LICENSE](LICENSE)。

## 免责声明

本项目为个人兴趣开发，程序没有任何破解行为，只是对夸克原有的API进行封装，仅使用你自己账号的抓包参数请求官方签到接口，仅供学习与交流使用，未盈利也未授权商业使用，请仅在授权范围内使用，严禁用于非法用途。
