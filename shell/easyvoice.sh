#!/bin/bash
# easyVoice 有声书服务管理 + 批量转换
#
# 用法:
#   ./easyvoice.sh start [书名]    # 启动服务+批量转换
#   ./easyvoice.sh status          # 查看进度
#   ./easyvoice.sh stop            # 停止转换
#   ./easyvoice.sh server          # 只启动服务
#   ./easyvoice.sh server-stop     # 停止服务
#   ./easyvoice.sh list            # 列出已生成音频

NOVEL_DIR="$HOME/Documents/novel"
EASYVOICE_DIR="$NOVEL_DIR/easyVoice"
OUTPUT_DIR="$NOVEL_DIR/output_easyvoice"
LOG_FILE="$NOVEL_DIR/batch_easyvoice.log"
SERVER_LOG="/tmp/easyvoice-server.log"
PID_FILE="/tmp/batch_easyvoice.pid"
SERVER_PID_FILE="/tmp/easyvoice-server.pid"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export MODE=production

cmd="${1:-help}"
name="${2:-}"

health_check() {
    curl -sf http://localhost:3000/api/v1/tts/engines > /dev/null 2>&1
}

start_server() {
    if health_check; then
        echo "easyVoice 服务已在运行"
        return 0
    fi

    # 清理残留
    pkill -f "node.*dist/server.js" 2>/dev/null
    sleep 1

    echo "启动 easyVoice 服务..."
    cd "$EASYVOICE_DIR/packages/backend"

    # 直接用 node 启动，不经 pnpm
    nohup node dist/server.js >> "$SERVER_LOG" 2>&1 &
    local pid=$!
    echo $pid > "$SERVER_PID_FILE"
    disown $pid

    for i in $(seq 1 30); do
        if health_check; then
            echo "easyVoice 服务已启动 (PID: $pid, http://localhost:3000)"
            return 0
        fi
        sleep 1
    done

    echo "错误: easyVoice 启动失败"
    tail -10 "$SERVER_LOG" 2>/dev/null
    return 1
}

stop_server() {
    if [ -f "$SERVER_PID_FILE" ]; then
        kill "$(cat "$SERVER_PID_FILE")" 2>/dev/null
        rm -f "$SERVER_PID_FILE"
    fi
    pkill -f "node.*dist/server.js" 2>/dev/null
    echo "easyVoice 服务已停止"
}

case "$cmd" in
    server)
        start_server
        ;;

    server-stop)
        stop_server
        ;;

    start)
        start_server || exit 1
        # 停掉旧的批处理
        [ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null

        cd "$NOVEL_DIR"
        if [ -n "$name" ]; then
            nohup python3 -u batch_easyvoice.py --file "$name" > "$LOG_FILE" 2>&1 &
        else
            nohup python3 -u batch_easyvoice.py > "$LOG_FILE" 2>&1 &
        fi
        echo $! > "$PID_FILE"
        disown "$(cat "$PID_FILE")"
        echo "批量转换已启动 (PID: $(cat "$PID_FILE"))"
        echo "查看进度: tail -f $LOG_FILE"
        ;;

    status)
        echo "════════════════════════════════════════"
        echo "  easyVoice 状态"
        echo "════════════════════════════════════════"

        # 1. 服务
        if health_check; then
            echo "  服务:   运行中 ✅ (http://localhost:3000)"
        else
            echo "  服务:   已停止 ❌"
        fi

        # 2. 批处理
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "  批处理: 运行中 ✅ (PID: $(cat "$PID_FILE"))"
        else
            echo "  批处理: 未运行"
        fi

        # 3-6. 从 progress.json 读取各书进度
        echo ""
        echo "── 小说进度 ──"
        completed_books=0
        total_books=0
        if [ -d "$OUTPUT_DIR" ]; then
            for dir in "$OUTPUT_DIR"/*/; do
                [ -d "$dir" ] || continue
                total_books=$((total_books + 1))
                bname=$(basename "$dir")
                pfile="$dir/progress.json"
                if [ -f "$pfile" ]; then
                    # 用 python 解析 progress.json
                    python3 -c "
import json, sys
with open('$pfile') as f:
    p = json.load(f)
total = p.get('total_segments', 0)
done = p.get('completed', 0)
fail = p.get('failed', 0)
status = p.get('status', '?')
updated = p.get('updated_at', '')
pct = int(done * 100 / total) if total > 0 else 0

icon = {'completed':'✅','processing':'⏳','partial':'⚠️','failed':'❌'}.get(status, '❓')
print(f'  {icon} {p.get(\"novel\",\"?\")[:45]}')
print(f'     {done}/{total} 段 ({pct}%) | 失败:{fail} | {status} | {updated}')
" 2>/dev/null
                    # 统计完成数
                    st=$(python3 -c "import json; print(json.load(open('$pfile')).get('status',''))" 2>/dev/null)
                    [ "$st" = "completed" ] && completed_books=$((completed_books + 1))
                else
                    count=$(find "$dir" -name "*.mp3" 2>/dev/null | wc -l | tr -d ' ')
                    size=$(du -sh "$dir" 2>/dev/null | cut -f1)
                    echo "  📁 $bname: ${count}个文件, ${size} (无进度文件)"
                fi
            done
        fi

        if [ $total_books -eq 0 ]; then
            echo "  (无输出)"
        else
            echo ""
            echo "  已完成: ${completed_books}/${total_books} 本"
        fi

        # 7. 输出目录
        echo "  输出:   $OUTPUT_DIR"

        # 8. 最近关键日志
        echo ""
        echo "── 最近日志 ──"
        if [ -f "$LOG_FILE" ]; then
            grep -E "小说:|完成:|失败:|分为|模式:|角色:|启动|错误" "$LOG_FILE" 2>/dev/null | tail -10
            [ $? -ne 0 ] && tail -10 "$LOG_FILE" 2>/dev/null
        else
            echo "  (无日志)"
        fi
        echo "════════════════════════════════════════"
        ;;

    stop)
        if [ -f "$PID_FILE" ]; then
            kill "$(cat "$PID_FILE")" 2>/dev/null && echo "批处理已停止" || echo "批处理进程不存在"
            rm -f "$PID_FILE"
        else
            echo "批处理未在运行"
        fi
        ;;

    list)
        if [ -d "$OUTPUT_DIR" ]; then
            for dir in "$OUTPUT_DIR"/*/; do
                [ -d "$dir" ] || continue
                bname=$(basename "$dir")
                count=$(find "$dir" -name "*.mp3" 2>/dev/null | wc -l | tr -d ' ')
                size=$(du -sh "$dir" 2>/dev/null | cut -f1)
                echo "$bname: ${count}个文件, ${size}"
            done
        else
            echo "没有输出"
        fi
        ;;

    help|*)
        echo "easyVoice 有声书工具"
        echo ""
        echo "  server         启动 easyVoice 服务"
        echo "  server-stop    停止服务"
        echo "  start          启动批量转换（所有小说）"
        echo "  start \"书名\"   只转换指定小说"
        echo "  status         查看进度"
        echo "  stop           停止转换"
        echo "  list           列出已生成音频"
        ;;
esac
