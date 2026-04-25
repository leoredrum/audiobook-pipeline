#!/bin/bash
# 双击 → 批量排队转换 txt/ 下所有小说
# 关闭终端后继续在后台运行

NOVEL_DIR="$HOME/Documents/novel"

echo "═══════════════════════════════════════"
echo "  批量有声书转换"
echo "═══════════════════════════════════════"

cd "$NOVEL_DIR"

# 后台运行
nohup bash queue_all_novels.sh bg >> queue_all_novels.log 2>&1 &
QPID=$!
disown $QPID

sleep 2

# 检查是否成功启动
if kill -0 $QPID 2>/dev/null; then
    echo ""
    echo "  队列已在后台启动 (PID: $QPID)"
    echo ""
    echo "  查看进度:"
    echo "    tail -f ~/Documents/novel/queue_all_novels.log"
    echo "  或双击: CheckQueueProgress.command"
    echo ""
    # 显示前几行日志
    tail -15 queue_all_novels.log 2>/dev/null
else
    echo ""
    echo "  启动失败，查看日志:"
    tail -20 queue_all_novels.log 2>/dev/null
fi

echo ""
read -p "按回车退出（后台任务继续运行）..."
