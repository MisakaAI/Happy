#!/bin/bash

set -e

# 获取当前脚本所在目录的上级目录（项目根目录）
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

HAPPY_BEGIN="# === HAPPY BEGIN ==="
HAPPY_END="# === HAPPY END ==="
CURRENT_CRON="$(mktemp)"
NEW_CRON="$(mktemp)"

cleanup() {
    rm -f "$CURRENT_CRON" "$NEW_CRON"
}
trap cleanup EXIT

# 没有安装过 crontab 时，`crontab -l` 会返回非零状态。
crontab -l > "$CURRENT_CRON" 2>/dev/null || :

# 删除之前由本脚本写入的所有 HAPPY 区块，保留其他内容。
awk -v begin="$HAPPY_BEGIN" -v end="$HAPPY_END" '
    $0 == begin { in_happy_block = 1; next }
    in_happy_block && $0 == end { in_happy_block = 0; next }
    !in_happy_block { print }
' "$CURRENT_CRON" > "$NEW_CRON"

cat >> "$NEW_CRON" <<EOF
$HAPPY_BEGIN
# 骑行建议（周一至周五 07:30）
30 7 * * 1-5 cd $BASE_DIR && PYTHONPATH=$BASE_DIR $BASE_DIR/.venv/bin/python -m cron.cycling_tips >> /dev/null 2>> $BASE_DIR/logs/error.log
# 天气（每10分钟）
*/10 * * * * cd $BASE_DIR && PYTHONPATH=$BASE_DIR $BASE_DIR/.venv/bin/python -m cron.qweather weather >> /dev/null 2>> $BASE_DIR/logs/error.log
# 空气质量（每小时15分、45分）
15,45 * * * * cd $BASE_DIR && PYTHONPATH=$BASE_DIR $BASE_DIR/.venv/bin/python -m cron.qweather air >> /dev/null 2>> $BASE_DIR/logs/error.log
# 外汇汇率（每分钟）
* * * * * cd $BASE_DIR && PYTHONPATH=$BASE_DIR $BASE_DIR/.venv/bin/python -m cron.fx >> /dev/null 2>> $BASE_DIR/logs/error.log
# 摩根标普 500 指数型发起式基金（每天17:00）
0 17 * * * cd $BASE_DIR && PYTHONPATH=$BASE_DIR $BASE_DIR/.venv/bin/python -m cron.fund 017641 >> /dev/null 2>> $BASE_DIR/logs/error.log
# 摩根纳斯达克 100 指数型发起式基金（每天17:00）
0 17 * * * cd $BASE_DIR && PYTHONPATH=$BASE_DIR $BASE_DIR/.venv/bin/python -m cron.fund 019172 >> /dev/null 2>> $BASE_DIR/logs/error.log
# 黄金（每分钟）
* * * * * cd $BASE_DIR && PYTHONPATH=$BASE_DIR $BASE_DIR/.venv/bin/python -m cron.gold >> /dev/null 2>> $BASE_DIR/logs/error.log
$HAPPY_END
EOF

echo "生成 cron:"
cat "$NEW_CRON"

echo
echo "安装 crontab..."

crontab "$NEW_CRON"

echo "完成"
