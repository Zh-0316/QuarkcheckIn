# 夸克网盘签到助手

夸克网盘每日自动签到工具，支持多账户管理，GUI 界面，后台静默运行。

## 功能特性

- 多账户管理：支持添加多个夸克网盘账户，独立签到
- 自动签到：启动后自动签到，每天 00:30 准时执行
- 三层定时防护：精确定时器 + 系统唤醒监听 + 4小时安全兜底
- 签到防重复：每个账户每天只签到一次（今日已签到时仅展示结果，不会重复请求签到接口）
- 签到结果反馈：显示今日签到空间、连签进度、累计签到天数、总容量等详情
- 批量签到：一键签到全部账户，或选择指定账户签到
- 系统托盘：最小化到托盘后台运行，关闭窗口不退出
- 开机自启：支持设置 Windows 开机自动启动

## 快速开始

### 方式一：直接使用（推荐）

从 [Releases](../../releases) 下载最新版 `QuarkCheckIn.zip`，解压到任意文件夹，双击 `QuarkCheckIn.exe` 运行即可。

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

## 抓包获取签到 URL

程序只依赖链接中的 `kps`、`sign`、`vcode` 三个鉴权参数，其余参数会自动忽略。

### 手机端抓包

1. 安装抓包工具（如 Reqable 等）
2. 打开抓包工具，开始抓包
3. 打开夸克网盘 APP，进入签到页面
4. 在抓包工具中找到 URL 类似下面的请求
   ```
   https://drive-member.quark.cn/1/clouddrive/capacity/growth/info?kps=xxxx&sign=xxxx&vcode=xxxx
   ```
5. 复制该请求的完整 URL（必须包含 `kps`、`sign`、`vcode` 三个参数）
6. 回到程序，点击「添加用户」，粘贴 URL 即可

### 注意事项

- `kps` / `sign` / `vcode` 有时效，失效后程序会提示"获取成长信息失败"，此时重新抓一条链接更新即可
- 多个账户需要分别抓包获取各自的 URL
- 换账号时删除旧用户、添加新用户即可，无需其他配置

## Docker / NAS 版

除 GUI 版外，本仓库 `docker/` 目录另提供一个**无界面**的 Docker 版：用环境变量配置账号、容器内置 cron 每天自动签到，适合 NAS / 服务器 7×24 常驻。抓包取参数的方式与上文完全相同。

直接拉镜像运行：

```bash
docker run -d --name quark-checkin \
  -e TZ=Asia/Shanghai \
  -e CRON_SCHEDULE="0 9 * * *" \
  -e COOKIE_QUARK="user=张三; url=抓包链接整段粘贴;" \
  --restart unless-stopped \
  ghcr.io/zh-0316/quark-checkin:latest
```

- 多账号：`COOKIE_QUARK` 用换行或 `&&` 分隔多段 `user=..; url=..;`
- 定时：`CRON_SCHEDULE` 为 cron 表达式，默认每天 09:00；签到接口幂等，一天跑多次不会重复签，可设 `0 */6 * * *` 多次兜底防漏签
- 手动补签：`docker exec quark-checkin python /app/checkIn_Quark.py`
- 也可克隆后用 `docker/docker-compose.yml`：`docker compose up -d --build`
- 参数过期时重新抓包替换 `COOKIE_QUARK` 并 `docker compose up -d --force-recreate`

镜像为多架构（`linux/amd64` + `linux/arm64`），x86 主机与 ARM 群晖 / 威联通 NAS 通用。

## 项目结构

```
checkIn_Quark/
├── checkIn_Quark.py          # 主程序
├── icon.ico                  # 程序图标
├── requirements.txt          # Python 依赖
├── .gitignore                # Git 忽略规则
└── README.md                 # 项目说明
```

运行后自动生成的数据文件：

```
├── users.json                # 用户数据
├── sign_records.json         # 签到记录
└── settings.json             # 程序设置
```

## 技术栈

- Python 3.13+
- PyQt6（GUI 框架）
- requests（HTTP 请求）
- PyInstaller（打包工具）

## 致谢

- 源码改编自 [@BNDou](https://github.com/BNDou/Auto_Check_In) 的脚本

## 许可证

本项目基于 AGPL-3.0 协议开源，详见 [LICENSE](LICENSE)。

## 免责声明

本项目为个人兴趣开发，程序没有任何破解行为，只是对夸克原有的API进行封装，仅使用你自己账号的抓包参数请求官方签到接口，仅供学习与交流使用，未盈利也未授权商业使用，请仅在授权范围内使用，严禁用于非法用途。




