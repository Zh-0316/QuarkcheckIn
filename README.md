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
- 单实例保护：防止重复启动
- 暗色主题：Catppuccin Mocha 风格界面

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

MIT License
