#!/bin/zsh
# 批量排队转换全部小说 — 逐本处理，自动跳过已完成，支持断点续传
#
# 用法:
#   ./queue_all_novels.sh        # 前台运行（双击 .command 用）
#   ./queue_all_novels.sh bg     # 后台运行

NOVEL_DIR="$HOME/Documents/novel"
TXT_DIR="$NOVEL_DIR/txt"
OUTPUT_DIR="$NOVEL_DIR/output_easyvoice"
LOG_FILE="$NOVEL_DIR/queue_all_novels.log"
PID_FILE="/tmp/queue_all_novels.pid"
BATCH_PID_FILE="/tmp/batch_easyvoice.pid"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# ── 防重复启动 ──
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "════════════════════════════════════════"
    echo "  队列任务已在运行 (PID: $(cat "$PID_FILE"))"
    echo "════════════════════════════════════════"
    echo ""
    echo "  查看进度: tail -f $LOG_FILE"
    echo "  或双击: CheckQueueProgress.command"
    echo ""
    if [ "$1" != "bg" ]; then
        read -p "按回车退出..."
    fi
    exit 0
fi

# 写入 PID
echo $$ > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT

# ── 日志函数 ──
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

# ── 启动 easyVoice 服务 ──
start_service() {
    if curl -sf http://localhost:3000/api/v1/tts/engines > /dev/null 2>&1; then
        return 0
    fi
    log "启动 easyVoice 服务..."
    cd "$NOVEL_DIR"
    ./easyvoice.sh server
    if ! curl -sf http://localhost:3000/api/v1/tts/engines > /dev/null 2>&1; then
        log "错误: easyVoice 启动失败"
        return 1
    fi
    return 0
}

# ── 获取小说状态 ──
get_novel_status() {
    local txt_file="$1"
    local name
    name=$(basename "$txt_file" .txt)
    local dir_name
    dir_name=$(echo "$name" | sed 's/[《》]//g' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    local novel_out="$OUTPUT_DIR/$dir_name"
    local pfile="$novel_out/progress.json"

    if [ ! -f "$pfile" ]; then
        echo "pending"
        return
    fi

    local st
    st=$(python3 -c "import json; print(json.load(open('$pfile')).get('status','unknown'))" 2>/dev/null)
    echo "$st"
}

# ── 主流程 ──
log "════════════════════════════════════════"
log "  批量队列开始"
log "════════════════════════════════════════"

start_service || exit 1

# 扫描所有 txt
TXT_FILES=()
while IFS= read -r f; do
    TXT_FILES+=("$f")
done < <(find "$TXT_DIR" -maxdepth 1 -name "*.txt" -type f | sort)
TOTAL=${#TXT_FILES[@]}

if [ "$TOTAL" -eq 0 ]; then
    log "没有找到 txt 文件"
    exit 0
fi

log "找到 $TOTAL 本小说"

# 分类
SKIP=0
RESUME=0
QUEUE=0
QUEUE_LIST=()

for txt in "${TXT_FILES[@]}"; do
    name=$(basename "$txt" .txt)
    nstatus=$(get_novel_status "$txt")
    case "$nstatus" in
        completed)
            log "  ✅ 跳过(已完成): $name"
            SKIP=$((SKIP + 1))
            ;;
        partial|failed)
            log "  🔄 续跑($status): $name"
            RESUME=$((RESUME + 1))
            QUEUE_LIST+=("$txt")
            ;;
        processing)
            log "  ⏳ 续跑(进行中): $name"
            RESUME=$((RESUME + 1))
            QUEUE_LIST+=("$txt")
            ;;
        *)
            log "  📝 待转换: $name"
            QUEUE=$((QUEUE + 1))
            QUEUE_LIST+=("$txt")
            ;;
    esac
done

TOTAL_QUEUE=${#QUEUE_LIST[@]}
log ""
log "队列: ${TOTAL_QUEUE}本待处理 (跳过:${SKIP} 续跑:${RESUME} 新增:${QUEUE})"
log ""

if [ "$TOTAL_QUEUE" -eq 0 ]; then
    log "所有小说已完成，无需处理"
    exit 0
fi

# ── 逐本处理 ──
DONE=0
FAIL=0

for i in "${!QUEUE_LIST[@]}"; do
    txt="${QUEUE_LIST[$i]}"
    name=$(basename "$txt")
    idx=$((i + 1))

    log "────────────────────────────────────────"
    log "[$idx/$TOTAL_QUEUE] 开始: $name"

    # 确认服务还活着
    if ! curl -sf http://localhost:3000/api/v1/tts/engines > /dev/null 2>&1; then
        log "  服务不可用，尝试重启..."
        start_service || { log "  服务启动失败，跳过"; FAIL=$((FAIL+1)); continue; }
    fi

    # 直接调 batch_easyvoice.py 前台运行（这样能等它完成再处理下一本）
    cd "$NOVEL_DIR"
    python3 -u batch_easyvoice.py --file "$name" >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?

    if [ "$EXIT_CODE" -eq 0 ]; then
        log "  完成: $name"
        DONE=$((DONE + 1))
    else
        log "  失败(exit $EXIT_CODE): $name"
        FAIL=$((FAIL + 1))
    fi
done

# ── 汇总 ──
log ""
log "════════════════════════════════════════"
log "  批量队列完成"
log "  处理: $TOTAL_QUEUE 本"
log "  成功: $DONE"
log "  失败: $FAIL"
log "  跳过: $SKIP"
log "════════════════════════════════════════"
