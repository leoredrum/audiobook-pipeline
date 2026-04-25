#!/bin/bash
# OpenClaw main 有声书模式 — easyVoice 适配层
#
# 用法:
#   audiobook.sh menu              # 展示按钮菜单 (JSON)
#   audiobook.sh novels            # 列出所有 txt 及状态 (JSON)
#   audiobook.sh start "文件名"    # 启动转换
#   audiobook.sh progress          # 所有书的进度 + ETA (JSON)
#   audiobook.sh progress "书名"   # 指定书进度 (JSON)
#   audiobook.sh stop              # 停止当前任务
#   audiobook.sh retry             # 重试失败段
#   audiobook.sh failures          # 列出所有失败段
#   audiobook.sh open              # 打开输出目录

NOVEL_DIR="$HOME/Documents/novel"
TXT_DIR="$NOVEL_DIR/txt"
OUTPUT_DIR="$NOVEL_DIR/output_easyvoice"
LOG_FILE="$NOVEL_DIR/batch_easyvoice.log"
PID_FILE="/tmp/batch_easyvoice.pid"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

cmd="${1:-menu}"
arg="${2:-}"

is_batch_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

service_alive() {
    curl -sf http://localhost:3000/api/v1/tts/engines > /dev/null 2>&1
}

case "$cmd" in

menu)
    echo '📖 有声书模式 — 选择操作：
[[buttons: 📖 有声书模式 | 选择操作 | 📖 开始转换:/audiobook_novels, 📊 检查进度:/audiobook_progress, ⏹ 停止任务:/audiobook_stop, ❌ 查看失败:/audiobook_failures, 🔄 重试失败:/audiobook_retry, 📂 输出目录:/audiobook_open]]'
    ;;

novels)
    python3 -c "
import json, os
from pathlib import Path
from datetime import datetime

txt_dir = Path('$TXT_DIR')
out_dir = Path('$OUTPUT_DIR')
import re

novels = []
for f in sorted(txt_dir.glob('*.txt')):
    name = f.stem
    dir_name = re.sub(r'[《》]', '', name).strip()
    novel_out = out_dir / dir_name
    pfile = novel_out / 'progress.json'

    status = '未开始'
    progress = 0
    total = 0
    completed = 0
    failed = 0

    if pfile.exists():
        try:
            p = json.load(open(pfile))
            total = p.get('total_segments', 0)
            completed = p.get('completed', 0)
            failed = p.get('failed', 0)
            st = p.get('status', '')
            progress = int(completed * 100 / total) if total > 0 else 0
            status = {'completed':'✅已完成','processing':'⏳进行中','partial':'⚠️部分完成','failed':'❌失败'}.get(st, '未知')
        except: pass
    elif novel_out.exists():
        mp3s = list(novel_out.glob('*.mp3'))
        if mp3s:
            status = '⚠️无进度文件'

    chars = f.stat().st_size
    est_hours = chars / 250 / 60  # 粗估

    novels.append({
        'file': f.name,
        'name': name[:40],
        'status': status,
        'progress': progress,
        'total': total,
        'completed': completed,
        'failed': failed,
        'size_mb': round(chars / 1024 / 1024, 1),
    })

print(json.dumps(novels, ensure_ascii=False, indent=2))
"
    ;;

start)
    if [ -z "$arg" ]; then
        echo '{"error":"请指定文件名，例如: audiobook.sh start \"小说.txt\""}'
        exit 1
    fi
    if ! [ -f "$TXT_DIR/$arg" ]; then
        # 模糊匹配
        match=$(ls "$TXT_DIR"/*"$arg"* 2>/dev/null | head -1)
        if [ -n "$match" ]; then
            arg=$(basename "$match")
        else
            echo "{\"error\":\"文件不存在: $arg\"}"
            exit 1
        fi
    fi
    cd "$NOVEL_DIR"
    ./easyvoice.sh start "$arg"
    echo "{\"ok\":true,\"file\":\"$arg\",\"message\":\"转换已启动\"}"
    ;;

progress)
    python3 -c "
import json, os, time, re
from pathlib import Path
from datetime import datetime, timedelta

out_dir = Path('$OUTPUT_DIR')
pid_file = '$PID_FILE'
log_file = '$LOG_FILE'
target_name = '''$arg'''.strip()

running = os.path.exists(pid_file) and os.system(f'kill -0 \$(cat {pid_file}) 2>/dev/null') == 0

results = []
for d in sorted(out_dir.iterdir()):
    if not d.is_dir():
        continue
    pfile = d / 'progress.json'
    if not pfile.exists():
        continue
    if target_name and target_name not in d.name:
        continue

    p = json.load(open(pfile))
    name = p.get('novel', d.name)
    total = p.get('total_segments', 0)
    completed = p.get('completed', 0)
    failed = p.get('failed', 0)
    status = p.get('status', '?')
    updated = p.get('updated_at', '')
    pct = int(completed * 100 / total) if total > 0 else 0

    # ETA 计算
    eta_str = ''
    elapsed_str = ''
    finish_str = ''
    if status == 'processing' and completed > 0 and updated:
        try:
            # 从 progress.json 的 updated_at 和第一个 mp3 的创建时间估算
            mp3s = sorted(d.glob('*.mp3'), key=lambda x: x.stat().st_mtime)
            if mp3s:
                start_time = mp3s[0].stat().st_mtime
                now = time.time()
                elapsed = now - start_time
                elapsed_str = str(timedelta(seconds=int(elapsed)))

                if completed > 0:
                    per_seg = elapsed / completed
                    remaining = (total - completed) * per_seg
                    eta_str = str(timedelta(seconds=int(remaining)))
                    finish_time = datetime.now() + timedelta(seconds=remaining)
                    finish_str = finish_time.strftime('%m-%d %H:%M')
        except: pass

    results.append({
        'name': name[:50],
        'status': status,
        'progress': pct,
        'completed': completed,
        'total': total,
        'failed': failed,
        'elapsed': elapsed_str,
        'eta': eta_str,
        'finish_at': finish_str,
        'updated_at': updated,
    })

svc_alive = os.system('curl -sf http://localhost:3000/api/v1/tts/engines > /dev/null 2>&1') == 0
output = {
    'running': running,
    'service': svc_alive,
    'novels': results,
}

# 最近日志
try:
    with open(log_file) as f:
        lines = f.readlines()
    key_lines = [l.strip() for l in lines if any(k in l for k in ['完成','失败','角色','分为','启动','错误','补跑'])]
    output['recent_log'] = key_lines[-5:] if key_lines else []
except:
    output['recent_log'] = []

print(json.dumps(output, ensure_ascii=False, indent=2))
"
    ;;

stop)
    cd "$NOVEL_DIR"
    ./easyvoice.sh stop
    echo '{"ok":true,"message":"已停止"}'
    ;;

retry)
    # 找所有 status=partial/failed 的书，重新启动转换（已完成段会自动跳过）
    python3 -c "
import json
from pathlib import Path
out_dir = Path('$OUTPUT_DIR')
to_retry = []
for d in sorted(out_dir.iterdir()):
    pfile = d / 'progress.json'
    if not pfile.exists(): continue
    p = json.load(open(pfile))
    if p.get('status') in ('partial', 'failed') and p.get('failed', 0) > 0:
        to_retry.append(p.get('novel', d.name))
if to_retry:
    print(f'需要补跑: {len(to_retry)} 本')
    for n in to_retry: print(f'  - {n[:50]}')
else:
    print('没有需要补跑的书')
"
    if [ -n "$arg" ]; then
        cd "$NOVEL_DIR" && ./easyvoice.sh start "$arg"
    fi
    ;;

failures)
    python3 -c "
import json
from pathlib import Path
out_dir = Path('$OUTPUT_DIR')
total_failed = 0
for d in sorted(out_dir.iterdir()):
    pfile = d / 'progress.json'
    if not pfile.exists(): continue
    p = json.load(open(pfile))
    parts = p.get('failed_parts', [])
    if parts:
        total_failed += len(parts)
        print(f'{p.get(\"novel\", d.name)[:40]}:')
        for fp in parts[:10]:
            print(f'  - {fp}')
        if len(parts) > 10:
            print(f'  ... 还有 {len(parts)-10} 个')
if total_failed == 0:
    print('没有失败段')
else:
    print(f'\n共 {total_failed} 个失败段')
"
    ;;

open)
    open "$OUTPUT_DIR" 2>/dev/null || echo "输出目录不存在"
    ;;

*)
    echo "audiobook.sh — OpenClaw 有声书模式"
    echo ""
    echo "  menu          展示菜单"
    echo "  novels        列出所有 txt 及状态"
    echo "  start <文件>  启动转换"
    echo "  progress      查看进度和 ETA"
    echo "  stop          停止任务"
    echo "  retry         补跑失败段"
    echo "  failures      列出失败段"
    echo "  open          打开输出目录"
    ;;
esac
