#!/usr/bin/env python3
"""给 output_easyvoice 下的 mp3 批量嵌入封面图。

用法:
    python3 scripts/embed_cover.py                      # dry-run 全部
    python3 scripts/embed_cover.py --only <new_name>    # 只处理一本
    python3 scripts/embed_cover.py --only <new_name> --apply
    python3 scripts/embed_cover.py --apply              # 应用到所有

需要 config/novels.json (复制 novels.example.json 自填)。封面图按 new_name 命名
放在 $NOVEL_ROOT/covers/ 下，扩展名 .jpg/.jpeg/.png/.webp 任一均可。

环境变量:
    NOVEL_ROOT      数据目录根（默认 ~/Documents/novel；mp3 在 $NOVEL_ROOT/output_easyvoice，封面在 $NOVEL_ROOT/covers）
    NOVELS_CONFIG   书目配置 json（默认 <repo>/config/novels.json）
"""
import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

_NOVEL_ROOT = Path(os.environ.get("NOVEL_ROOT", str(Path.home() / "Documents/novel"))).expanduser()
ROOT = _NOVEL_ROOT / "output_easyvoice"
COVER_DIR = _NOVEL_ROOT / "covers"

_REPO_ROOT = Path(__file__).resolve().parent.parent
NOVELS_CONFIG = Path(os.environ.get("NOVELS_CONFIG", str(_REPO_ROOT / "config" / "novels.json")))


def load_novels():
    if not NOVELS_CONFIG.exists():
        sys.exit(
            f"❌ 找不到配置文件: {NOVELS_CONFIG}\n"
            f"   请复制 config/novels.example.json 到 config/novels.json 并按格式填写。"
        )
    with open(NOVELS_CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("novels", [])


def find_cover(book_name: str):
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = COVER_DIR / f"{book_name}{ext}"
        if p.exists():
            return p
    return None


def embed_one(mp3: Path, cover: Path, apply: bool):
    tmp = mp3.parent / f"{mp3.stem}.__cv_tmp__.mp3"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(mp3),
        "-i", str(cover),
        "-map", "0:a", "-map", "1",
        "-c", "copy",
        "-map_metadata", "0",
        "-id3v2_version", "3",
        "-metadata:s:v", "title=Album cover",
        "-metadata:s:v", "comment=Cover (front)",
        "-disposition:v:0", "attached_pic",
        "-f", "mp3", str(tmp),
    ]
    if not apply:
        return
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(r.stderr.strip())
    tmp.replace(mp3)


def process_dir(d: Path, apply: bool):
    name = d.name
    cover = find_cover(name)
    if not cover:
        print(f"\n📁 {name}\n   ⚠ 找不到封面文件，跳过（请放到 {COVER_DIR}/{name}.jpg）")
        return 0, 0, 0
    mp3s = sorted(d.glob("*.mp3"))
    total = len(mp3s)
    if total == 0:
        print(f"\n📁 {name}\n   ⚠ 无 mp3，跳过")
        return 0, 0, 0

    print(f"\n📁 {name}")
    print(f"   封面: {cover.name} ({cover.stat().st_size:,} bytes)")
    print(f"   {total} 个 mp3 待嵌入")

    if not apply:
        return total, 0, 0

    success, failed = 0, 0
    for f in mp3s:
        try:
            embed_one(f, cover, apply=True)
            success += 1
        except Exception as e:
            print(f"   ❌ {f.name}: {e}")
            failed += 1
    print(f"   ✓ 完成 {success}/{total}（失败 {failed}）")
    return total, success, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default=None, help="只处理某一本（输入 new_name）")
    args = ap.parse_args()

    novels = load_novels()
    new_names = [n["new_name"] for n in novels]

    print(f"{'═'*60}")
    print(f"  嵌入封面 {'[APPLY]' if args.apply else '[DRY-RUN]'}")
    print(f"{'═'*60}")

    if args.only:
        d = ROOT / args.only
        if not d.is_dir():
            sys.exit(f"目录不存在: {d}")
        process_dir(d, args.apply)
        return

    grand_total, grand_s, grand_f = 0, 0, 0
    for nm in new_names:
        d = ROOT / nm
        if not d.is_dir():
            print(f"\n⚠ 目录不存在，跳过: {nm}")
            continue
        t, s, f = process_dir(d, args.apply)
        grand_total += t
        grand_s += s
        grand_f += f
    print(f"\n{'─'*60}")
    if args.apply:
        print(f"总计: 成功 {grand_s}, 失败 {grand_f}")
    else:
        print(f"DRY-RUN 总计 {grand_total} 个 mp3 待处理。加 --apply 真正执行。")


if __name__ == "__main__":
    main()
