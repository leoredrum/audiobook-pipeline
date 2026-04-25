#!/bin/bash
# 有声书进度监控 — 供 OpenClaw cron 调用
# 检查进度，跨阈值时输出提醒文本，否则静默退出
# 阈值状态存储在 /tmp/audiobook_milestones.json

NOVEL_DIR="$HOME/Documents/novel"
OUTPUT_DIR="$NOVEL_DIR/output_easyvoice"
MILESTONE_FILE="/tmp/audiobook_milestones.json"
PID_FILE="/tmp/batch_easyvoice.pid"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

python3 << 'PYEOF'
import json, os, time, sys
from pathlib import Path
from datetime import datetime, timedelta

OUTPUT_DIR = Path(os.path.expanduser("~/Documents/novel/output_easyvoice"))
MILESTONE_FILE = "/tmp/audiobook_milestones.json"
PID_FILE = "/tmp/batch_easyvoice.pid"
THRESHOLDS = [25, 50, 75, 100]

# 加载已发送阈值
milestones = {}
if os.path.exists(MILESTONE_FILE):
    try:
        milestones = json.load(open(MILESTONE_FILE))
    except:
        milestones = {}

# 检查批处理是否在跑
batch_running = False
if os.path.exists(PID_FILE):
    try:
        pid = int(open(PID_FILE).read().strip())
        os.kill(pid, 0)
        batch_running = True
    except:
        pass

alerts = []

for d in sorted(OUTPUT_DIR.iterdir()):
    if not d.is_dir():
        continue
    pfile = d / "progress.json"
    if not pfile.exists():
        continue

    p = json.load(open(pfile))
    name = p.get("novel", d.name)
    total = p.get("total_segments", 0)
    completed = p.get("completed", 0)
    failed = p.get("failed", 0)
    status = p.get("status", "?")

    if total == 0:
        continue

    pct = int(completed * 100 / total)
    book_key = d.name

    # 已发送阈值
    sent = milestones.get(book_key, [])

    # ETA
    elapsed_str = ""
    eta_str = ""
    finish_str = ""
    mp3s = sorted(d.glob("*.mp3"), key=lambda x: x.stat().st_mtime)
    if mp3s and completed > 0:
        start_time = mp3s[0].stat().st_mtime
        elapsed = time.time() - start_time
        elapsed_str = str(timedelta(seconds=int(elapsed)))
        per_seg = elapsed / completed
        remaining = (total - completed) * per_seg
        eta_str = str(timedelta(seconds=int(remaining)))
        finish_str = (datetime.now() + timedelta(seconds=remaining)).strftime("%m-%d %H:%M")

    # 检查阈值
    for t in THRESHOLDS:
        if pct >= t and t not in sent:
            if t == 100:
                emoji = "✅"
                header = f"有声书转换完成！"
            else:
                emoji = "🔔"
                header = f"有声书进度 {t}%"

            alert = f"""{emoji} {header}
📖 {name[:40]}
📊 {pct}% ({completed}/{total} 段)"""
            if failed > 0:
                alert += f" | 失败:{failed}"
            if elapsed_str:
                alert += f"\n⏱ 已运行: {elapsed_str}"
            if eta_str and t < 100:
                alert += f"\n🏁 预计完成: {finish_str} (剩余 {eta_str})"
            if t == 100:
                # 计算总大小
                total_size = sum(f.stat().st_size for f in d.glob("*.mp3"))
                alert += f"\n📁 {len(mp3s)} 个文件, {total_size/1024/1024:.0f}MB"

            alerts.append(alert)
            sent.append(t)

    # 任务结束且未标记过的清理
    if status in ("completed", "failed") and not batch_running:
        if status == "failed" and "failed" not in sent:
            alerts.append(f"❌ 有声书转换失败\n📖 {name[:40]}\n📊 {completed}/{total} 段完成, {failed} 段失败")
            sent.append("failed")

    milestones[book_key] = sent

# 保存阈值状态
with open(MILESTONE_FILE, "w") as f:
    json.dump(milestones, f)

# 输出提醒（有内容才输出，否则静默）
if alerts:
    print("\n---\n".join(alerts))
else:
    # 无提醒时输出极简状态让 cron 知道在跑
    if batch_running:
        # 找当前正在处理的书
        processing = [d.name for d in OUTPUT_DIR.iterdir()
                      if (d / "progress.json").exists()
                      and json.load(open(d / "progress.json")).get("status") == "processing"]
        if processing:
            sys.exit(0)  # 静默退出，不产生消息
    sys.exit(0)
PYEOF
