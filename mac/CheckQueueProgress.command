#!/bin/bash
# 双击 → 查看批量队列进度
NOVEL_DIR="$HOME/Documents/novel"

echo "═══════════════════════════════════════"
echo "  批量队列进度"
echo "═══════════════════════════════════════"

# 队列进程状态
if [ -f /tmp/queue_all_novels.pid ] && kill -0 "$(cat /tmp/queue_all_novels.pid)" 2>/dev/null; then
    echo "  队列: 运行中 ✅ (PID: $(cat /tmp/queue_all_novels.pid))"
else
    echo "  队列: 未运行"
fi

# easyVoice 服务
if curl -sf http://localhost:3000/api/v1/tts/engines > /dev/null 2>&1; then
    echo "  服务: 运行中 ✅"
else
    echo "  服务: 已停止 ❌"
fi

# 当前转换状态 — 从 progress.json + 进程检测
CURRENT_STATUS="空闲"
BATCH_PID=$(pgrep -f 'batch_easyvoice\.py' 2>/dev/null | head -1)

if [ -n "$BATCH_PID" ]; then
    # 进程存活，从 progress.json 找 status=processing 的书
    ACTIVE=$(python3 -c "
import json, os, time
from pathlib import Path
out = Path('$NOVEL_DIR/output_easyvoice')
for pf in out.glob('*/progress.json'):
    try:
        p = json.load(open(pf))
        if p.get('status') == 'processing':
            name = p.get('novel', pf.parent.name)
            done = p.get('completed', 0)
            total = p.get('total_segments', 0)
            updated = p.get('updated_at', '')
            print(f'{name}|{done}|{total}|{updated}')
            break
    except: pass
" 2>/dev/null)

    if [ -n "$ACTIVE" ]; then
        IFS='|' read -r BNAME BDONE BTOTAL BUPDATED <<< "$ACTIVE"
        echo "  当前: 转换中 ✅ (PID: $BATCH_PID)"
        echo "    📖 $BNAME"
        echo "    📊 段: $BDONE / $BTOTAL"
        [ -n "$BUPDATED" ] && echo "    🕐 更新: $BUPDATED"
    else
        echo "  当前: 转换中 ✅ (PID: $BATCH_PID, 等待 progress 更新)"
    fi
else
    # 进程不在，但队列活着 → 可能在切换书 / 启动服务
    if [ -f /tmp/queue_all_novels.pid ] && kill -0 "$(cat /tmp/queue_all_novels.pid)" 2>/dev/null; then
        # 看日志最后一行判断
        LAST_LOG=$(tail -1 "$NOVEL_DIR/queue_all_novels.log" 2>/dev/null)
        echo "  当前: 准备中 ⏳ (队列运行中，batch 未启动)"
        [ -n "$LAST_LOG" ] && echo "    日志: $LAST_LOG"
    else
        echo "  当前: 空闲"
    fi
fi

echo ""
echo "── 各书进度 ──"

cd "$NOVEL_DIR"
python3 -c "
import json, os, time
from pathlib import Path
from datetime import timedelta

out = Path('$NOVEL_DIR/output_easyvoice')
txt = Path('$NOVEL_DIR/txt')
completed = 0
total = 0

for f in sorted(txt.glob('*.txt')):
    import re
    name = f.stem
    dn = re.sub(r'[《》]', '', name).strip()
    d = out / dn
    total += 1
    pfile = d / 'progress.json'
    if not pfile.exists():
        print(f'  📝 未开始 | {name[:45]}')
        continue
    p = json.load(open(pfile))
    st = p.get('status','?')
    tot = p.get('total_segments',0)
    done = p.get('completed',0)
    fail = p.get('failed',0)
    pct = int(done*100/tot) if tot else 0
    icon = {'completed':'✅','processing':'⏳','partial':'⚠️','failed':'❌'}.get(st,'❓')

    # ETA
    eta = ''
    mp3s = sorted(d.glob('*.mp3'), key=lambda x: x.stat().st_mtime) if d.exists() else []
    if mp3s and done > 0 and st == 'processing':
        elapsed = time.time() - mp3s[0].stat().st_mtime
        remaining = (tot - done) * (elapsed / done)
        eta = f' ETA:{str(timedelta(seconds=int(remaining)))}'

    if st == 'completed':
        completed += 1

    line = f'  {icon} {pct:3d}% ({done}/{tot})'
    if fail: line += f' fail:{fail}'
    line += f'{eta} | {name[:40]}'
    print(line)

print(f'\n  完成: {completed}/{total} 本')
" 2>/dev/null

echo ""
echo "── 队列总 ETA ──"

python3 -c "
import json, os, time, re
from pathlib import Path
from datetime import timedelta, datetime

out = Path('$NOVEL_DIR/output_easyvoice')
txt = Path('$NOVEL_DIR/txt')

# ── 1. 收集已知书的 segs/MB 比率，用于估算未开始的书 ──
known_ratios = []
all_books = []

for f in sorted(txt.glob('*.txt')):
    name = f.stem
    dn = re.sub(r'[《》]', '', name).strip()
    d = out / dn
    pf = d / 'progress.json'
    size_mb = f.stat().st_size / (1024 * 1024)

    if pf.exists():
        p = json.load(open(pf))
        st = p.get('status', '?')
        total = p.get('total_segments', 0)
        done = p.get('completed', 0)
        if total > 0 and size_mb > 0:
            known_ratios.append(total / size_mb)
        all_books.append({'name': name, 'status': st, 'total': total, 'done': done, 'dir': d, 'size_mb': size_mb})
    else:
        all_books.append({'name': name, 'status': 'pending', 'total': 0, 'done': 0, 'dir': d, 'size_mb': size_mb})

avg_ratio = sum(known_ratios) / len(known_ratios) if known_ratios else 0

# ── 2. 计算总剩余段数 ──
remaining_segs = 0
remaining_books = 0

for b in all_books:
    if b['status'] == 'completed':
        continue
    if b['status'] == 'pending':
        # 估算段数
        est = int(b['size_mb'] * avg_ratio) if avg_ratio > 0 else 0
        remaining_segs += est
        remaining_books += 1
    else:
        # processing / partial / failed
        remaining_segs += max(b['total'] - b['done'], 0)
        remaining_books += 1

# ── 3. 计算当前每段耗时 ──
per_seg = 0

# 优先：从正在 processing 的书的 mp3 时间戳推算
for b in all_books:
    if b['status'] != 'processing' or b['done'] == 0:
        continue
    d = b['dir']
    mp3s = sorted(d.glob('*.mp3'), key=lambda x: x.stat().st_mtime) if d.exists() else []
    if len(mp3s) >= 2:
        first_time = mp3s[0].stat().st_mtime
        last_time = mp3s[-1].stat().st_mtime
        elapsed = last_time - first_time
        # done-1 因为第一个 mp3 的时间是起点
        if b['done'] > 1 and elapsed > 0:
            per_seg = elapsed / (b['done'] - 1)
            break
    # fallback: 用第一个 mp3 到现在
    if mp3s and b['done'] > 0:
        elapsed = time.time() - mp3s[0].stat().st_mtime
        per_seg = elapsed / b['done']
        break

# ── 4. 输出 ──
if remaining_books == 0:
    print('  全部完成! 🎉')
elif per_seg <= 0 or avg_ratio <= 0:
    print(f'  剩余小说: {remaining_books} 本')
    print(f'  剩余段数: ~{remaining_segs} 段 (未开始的书为估算)')
    print(f'  队列总 ETA: 暂无法估算 (当前书进度不足)')
else:
    remaining_secs = remaining_segs * per_seg

    # 格式化每段耗时
    ps_min = int(per_seg) // 60
    ps_sec = int(per_seg) % 60
    ps_str = f'{ps_min}分{ps_sec:02d}秒' if ps_min > 0 else f'{ps_sec}秒'

    # 格式化剩余时间
    days = int(remaining_secs) // 86400
    hours = (int(remaining_secs) % 86400) // 3600
    mins = (int(remaining_secs) % 3600) // 60
    if days > 0:
        remain_str = f'{days}天{hours}小时{mins}分'
    elif hours > 0:
        remain_str = f'{hours}小时{mins}分'
    else:
        remain_str = f'{mins}分钟'

    finish_time = datetime.now() + timedelta(seconds=remaining_secs)
    finish_str = finish_time.strftime('%Y-%m-%d %H:%M')

    print(f'  剩余小说: {remaining_books} 本')
    print(f'  剩余段数: ~{remaining_segs} 段 (未开始的书为估算)')
    print(f'  平均每段: {ps_str}')
    print(f'  预计还需: {remain_str}')
    print(f'  预计完成: {finish_str}')
" 2>/dev/null

echo ""
echo "── 最近日志 ──"
tail -10 "$NOVEL_DIR/queue_all_novels.log" 2>/dev/null || echo "  (无日志)"

echo "═══════════════════════════════════════"
echo ""
read -p "按回车退出..."
