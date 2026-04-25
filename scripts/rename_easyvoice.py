#!/usr/bin/env python3
"""精简 output_easyvoice 子目录名 + 重命名 mp3。

用法:
    python3 scripts/rename_easyvoice.py        # dry-run 全部
    python3 scripts/rename_easyvoice.py --apply
    python3 scripts/rename_easyvoice.py --only <old_name>          # 只处理一本
    python3 scripts/rename_easyvoice.py --only <old_name> --apply

需要 config/novels.json (复制 novels.example.json 自填)。

环境变量:
    NOVEL_ROOT      数据目录根（默认 ~/Documents/novel）
    NOVELS_CONFIG   书目配置 json（默认 <repo>/config/novels.json）
"""
import os
import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

_NOVEL_ROOT = Path(os.environ.get("NOVEL_ROOT", str(Path.home() / "Documents/novel"))).expanduser()
ROOT = _NOVEL_ROOT / "output_easyvoice"

_REPO_ROOT = Path(__file__).resolve().parent.parent
NOVELS_CONFIG = Path(os.environ.get("NOVELS_CONFIG", str(_REPO_ROOT / "config" / "novels.json")))

LOG = Path(f"/tmp/rename_easyvoice_log_{datetime.now():%Y%m%d_%H%M%S}.json")
NUM_RE = re.compile(r"_(\d+)\.mp3$")


def load_novels():
    if not NOVELS_CONFIG.exists():
        sys.exit(
            f"❌ 找不到配置文件: {NOVELS_CONFIG}\n"
            f"   请复制 config/novels.example.json 到 config/novels.json 并按格式填写。"
        )
    with open(NOVELS_CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    novels = cfg.get("novels", [])
    if not novels:
        sys.exit(f"❌ {NOVELS_CONFIG} 里 novels 为空")
    return novels


def plan(novels):
    plans = []
    warnings = []
    for n in novels:
        old, new = n["old_name"], n["new_name"]
        old_dir = ROOT / old
        new_dir = ROOT / new
        if not old_dir.exists():
            warnings.append(f"跳过：旧目录不存在 {old}")
            continue
        if new_dir.exists() and new_dir != old_dir:
            warnings.append(f"⚠ 目标已存在，跳过：{new}")
            continue
        mp3s = sorted(old_dir.glob("*.mp3"))
        total = len(mp3s)
        if total == 0:
            warnings.append(f"⚠ 无 mp3：{old}")
            plans.append((old_dir, new_dir, []))
            continue
        pad = len(str(total))
        file_renames = []
        seen = set()
        for f in mp3s:
            m = NUM_RE.search(f.name)
            if not m:
                warnings.append(f"⚠ 无序号：{f.name}（跳过此文件）")
                continue
            num = int(m.group(1))
            if num in seen:
                warnings.append(f"⚠ 序号重复 {num}：{f.name}")
                continue
            seen.add(num)
            new_name = f"{new}_{num:0{pad}d}.mp3"
            if new_name != f.name:
                file_renames.append((f.name, new_name))
        plans.append((old_dir, new_dir, file_renames))
    return plans, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default=None, help="只处理某一本（输入 old_name）")
    args = ap.parse_args()

    novels = load_novels()
    if args.only:
        novels = [n for n in novels if n["old_name"] == args.only]
        if not novels:
            sys.exit(f"❌ 配置里找不到 old_name={args.only}")

    plans, warnings = plan(novels)

    print(f"{'═'*60}")
    print(f"  output_easyvoice 重命名 {'[APPLY]' if args.apply else '[DRY-RUN]'}")
    print(f"{'═'*60}\n")

    if warnings:
        print("⚠ 警告：")
        for w in warnings:
            print(f"   {w}")
        print()

    record = {"timestamp": datetime.now().isoformat(), "applied": args.apply, "items": []}
    for old_dir, new_dir, file_renames in plans:
        total = len(list(old_dir.glob("*.mp3")))
        pad = len(str(total)) if total else 0
        print(f"📁 {old_dir.name}")
        print(f"   → {new_dir.name}  ({total} mp3, pad={pad})")
        if file_renames:
            print(f"   首例: {file_renames[0][0]}")
            print(f"        → {file_renames[0][1]}")
            if len(file_renames) > 1:
                print(f"   末例: {file_renames[-1][0]}")
                print(f"        → {file_renames[-1][1]}")
        record["items"].append({
            "old_dir": str(old_dir),
            "new_dir": str(new_dir),
            "mp3_renames": file_renames,
        })
        print()

    if not args.apply:
        print("DRY-RUN 完成。确认后加 --apply 真正执行。")
        return

    print("\n开始执行...\n")
    for old_dir, new_dir, file_renames in plans:
        for old_name, new_name in file_renames:
            (old_dir / old_name).rename(old_dir / new_name)
        if old_dir != new_dir:
            old_dir.rename(new_dir)
        print(f"✓ {new_dir.name}")

    LOG.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 完成。回滚映射: {LOG}")


if __name__ == "__main__":
    main()
