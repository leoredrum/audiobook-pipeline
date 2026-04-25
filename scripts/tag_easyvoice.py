#!/usr/bin/env python3
"""给 output_easyvoice 下的 mp3 批量打 ID3 tag (album/title/track/genre/artist)。

用法:
    python3 scripts/tag_easyvoice.py                      # dry-run 全部
    python3 scripts/tag_easyvoice.py --only <new_name>    # 只处理某一本
    python3 scripts/tag_easyvoice.py --only <new_name> --apply
    python3 scripts/tag_easyvoice.py --apply              # 应用到所有

需要 config/novels.json (复制 novels.example.json 自填)。tag 在 rename 之后跑，
--only 用 new_name（即重命名后的目录名）。

环境变量:
    NOVEL_ROOT      数据目录根（默认 ~/Documents/novel）
    NOVELS_CONFIG   书目配置 json（默认 <repo>/config/novels.json）
"""
import os
import re
import sys
import json
import argparse
import subprocess
from pathlib import Path

_NOVEL_ROOT = Path(os.environ.get("NOVEL_ROOT", str(Path.home() / "Documents/novel"))).expanduser()
ROOT = _NOVEL_ROOT / "output_easyvoice"

_REPO_ROOT = Path(__file__).resolve().parent.parent
NOVELS_CONFIG = Path(os.environ.get("NOVELS_CONFIG", str(_REPO_ROOT / "config" / "novels.json")))

GENRE = "有声小说"
NUM_RE = re.compile(r"_(\d+)\.mp3$")


def load_novels():
    if not NOVELS_CONFIG.exists():
        sys.exit(
            f"❌ 找不到配置文件: {NOVELS_CONFIG}\n"
            f"   请复制 config/novels.example.json 到 config/novels.json 并按格式填写。"
        )
    with open(NOVELS_CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("novels", [])


def tag_one(src: Path, album: str, num: int, total: int, pad: int, artist: str, apply: bool):
    title = f"第{num:0{pad}d}集"
    track = f"{num}/{total}"
    tmp = src.parent / f"{src.stem}.__tag_tmp__.mp3"

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-c", "copy", "-map", "0",
        "-id3v2_version", "3",
        "-metadata", f"title={title}",
        "-metadata", f"album={album}",
        "-metadata", f"track={track}",
        "-metadata", f"genre={GENRE}",
    ]
    if artist:
        cmd += ["-metadata", f"artist={artist}",
                "-metadata", f"album_artist={artist}"]
    cmd += ["-f", "mp3", str(tmp)]

    if not apply:
        return title, track, artist

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"ffmpeg failed for {src.name}: {r.stderr.strip()}")
    tmp.replace(src)
    return title, track, artist


def process_dir(dir_path: Path, artist: str, apply: bool):
    name = dir_path.name
    mp3s = sorted(dir_path.glob("*.mp3"))
    total = len(mp3s)
    if total == 0:
        print(f"  ⚠ 无 mp3：{name}")
        return 0, 0
    pad = len(str(total))

    print(f"\n📁 {name}")
    print(f"   total={total}, pad={pad}, artist={artist or '(空)'}")

    success, failed = 0, 0
    for f in mp3s:
        m = NUM_RE.search(f.name)
        if not m:
            print(f"   ⚠ 无序号: {f.name}")
            failed += 1
            continue
        num = int(m.group(1))
        try:
            title, track, _ = tag_one(f, name, num, total, pad, artist, apply)
            success += 1
            if not apply and (success <= 2 or success == total):
                print(f"   样例 [{f.name}]")
                print(f"      title={title}, album={name}, track={track}")
        except Exception as e:
            print(f"   ❌ {f.name}: {e}")
            failed += 1
    if apply:
        print(f"   ✓ 完成 {success}/{total}（失败 {failed}）")
    else:
        print(f"   [dry-run] 待处理 {total} 个文件")
    return success, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default=None, help="只处理某一本（输入 new_name）")
    args = ap.parse_args()

    novels = load_novels()
    artist_by_name = {n["new_name"]: n.get("artist", "") for n in novels}

    print(f"{'═'*60}")
    print(f"  output_easyvoice 打 tag {'[APPLY]' if args.apply else '[DRY-RUN]'}")
    print(f"{'═'*60}")

    if args.only:
        d = ROOT / args.only
        if not d.is_dir():
            sys.exit(f"目录不存在: {d}")
        if args.only not in artist_by_name:
            print(f"⚠ {args.only} 不在 novels 配置里，artist 留空")
        artist = artist_by_name.get(args.only, "")
        process_dir(d, artist, args.apply)
        return

    total_s, total_f = 0, 0
    for new_name, artist in artist_by_name.items():
        d = ROOT / new_name
        if not d.is_dir():
            print(f"\n⚠ 目录不存在，跳过: {new_name}")
            continue
        s, f = process_dir(d, artist, args.apply)
        total_s += s
        total_f += f
    print(f"\n{'─'*60}\n总计: 成功 {total_s}, 失败 {total_f}")


if __name__ == "__main__":
    main()
