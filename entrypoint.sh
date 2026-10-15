#!/bin/bash
set -e

CRON_SCHEDULE="${CRON_SCHEDULE:-0 9 * * *}"

echo "======================================================================"
echo "  夸克网盘自动签到"
echo "======================================================================"
echo "  当前定时: $CRON_SCHEDULE (时区 Asia/Shanghai)"
echo ""
echo "  【签到方式】"
echo "  启动签到 - 容器每次启动时自动执行一次"
echo "  定时签到 - 按上方 cron 时间自动执行"
echo "  手动签到 - docker exec quark-checkin python /app/checkIn_Quark.py"
echo ""
echo "  【修改签到时间】"
echo "  编辑 docker-compose.yml 的 CRON_SCHEDULE 后，重新创建容器即可"
echo "  0 9 * * *      每天 09:00 一次"
echo "  0 */6 * * *    每 6 小时一次"
echo "  0 8,12,16,20 * * *  每天 4 个时段"
echo "======================================================================"

# 获取 Python 绝对路径（cron 环境 PATH 精简，必须用绝对路径）
PYTHON_BIN=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "/usr/local/bin/python")

# 将 COOKIE_QUARK 写入文件，供 cron 任务读取（cron 不继承容器的自定义环境变量）
printf '%s' "$COOKIE_QUARK" > /etc/quark-cookie

# 首次启动立即执行一次签到（脚本自带分界线）
# 即使失败也不阻止容器启动，后续定时任务仍会执行
$PYTHON_BIN /app/checkIn_Quark.py startup || echo "首次签到失败，不影响后续定时任务"

# 设置 cron 定时任务（/etc/cron.d 标准格式，含用户名和 PATH）
# cron 执行时手动注入 COOKIE_QUARK，从文件读取以兼容多账号换行等特殊字符
cat > /etc/cron.d/quark-checkin <<EOF
PATH=/usr/local/bin:/usr/bin:/bin
$CRON_SCHEDULE root cd /app && COOKIE_QUARK="\$(cat /etc/quark-cookie)" $PYTHON_BIN /app/checkIn_Quark.py scheduled >> /proc/1/fd/1 2>&1
EOF
chmod 0644 /etc/cron.d/quark-checkin

echo "定时任务已就绪，容器保持运行中..."
exec cron -f
