#!/usr/bin/env python3
"""
easyVoice 批量小说转音频 — 多角色自动配音版
默认模式: 角色分析 + /generateJson 多音色
回退模式: --single-voice zh-CN-YunxiNeural
"""

import os, sys, re, json, time, argparse, subprocess
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# scripts/ 在 sys.path 上，analyze_roles 直接 import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_roles import analyze_text as _analyze_text

# 数据目录由 NOVEL_ROOT 决定（默认 ~/Documents/novel）
NOVEL_DIR = Path(os.environ.get("NOVEL_ROOT", str(Path.home() / "Documents/novel"))).expanduser()
TXT_DIR = NOVEL_DIR / "txt"
OUTPUT_DIR = NOVEL_DIR / "output_easyvoice"
# easyVoice 服务路径：默认在 NOVEL_DIR/easyVoice，可用 EASYVOICE_DIR 环境变量覆盖
EASYVOICE_DIR = Path(os.environ.get("EASYVOICE_DIR", str(NOVEL_DIR / "easyVoice"))).expanduser()
# voice config 默认在本 repo 的 config/，可用 VOICE_CONFIG 环境变量覆盖
_REPO_ROOT = Path(__file__).resolve().parent.parent
VOICE_CONFIG_PATH = Path(os.environ.get("VOICE_CONFIG", str(_REPO_ROOT / "config" / "easyvoice_voices.json"))).expanduser()
API = "http://localhost:3000"
CHARS_PER_SEGMENT = 15000
MAX_RETRIES = 5
RETRY_DELAYS = [5, 15, 30, 60, 120]  # 指数退避


def load_voice_config():
    with open(VOICE_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_server():
    """确认 easyVoice 服务在运行，没运行则拉起"""
    try:
        urlopen(f"{API}/api/v1/tts/engines", timeout=5)
        return True
    except Exception:
        print("easyVoice 未运行，尝试启动...")
        backend_dir = EASYVOICE_DIR / "packages" / "backend"
        server_js = backend_dir / "dist" / "server.js"
        if not server_js.exists():
            print(f"错误: {server_js} 不存在，请先 pnpm build")
            return False
        env = {**os.environ, "MODE": "production",
               "PATH": f"/opt/homebrew/bin:/usr/local/bin:{os.environ.get('PATH', '')}"}
        subprocess.Popen(
            ["node", str(server_js)], cwd=str(backend_dir),
            stdout=open("/tmp/easyvoice-server.log", "a"),
            stderr=subprocess.STDOUT, env=env,
        )
        for _ in range(30):
            time.sleep(1)
            try:
                urlopen(f"{API}/api/v1/tts/engines", timeout=3)
                print("easyVoice 已启动")
                return True
            except Exception:
                pass
        print("错误: easyVoice 启动失败")
        return False


def health_check():
    try:
        urlopen(f"{API}/api/v1/tts/engines", timeout=3)
        return True
    except Exception:
        return False


# ── 进度文件 ──

def write_progress(novel_output, novel_name, total, success, skipped, failed, status, failed_parts=None):
    p = {
        "novel": novel_name,
        "total_segments": total,
        "completed": success + skipped,
        "success": success,
        "skipped": skipped,
        "failed": failed,
        "status": status,
        "failed_parts": (failed_parts or [])[:20],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        with open(novel_output / "progress.json", "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── 文本读取 ──

def read_novel_text(txt_path):
    # 搜书吧来源 txt 部分为 GB18030 编码，先试 UTF-8，失败再 fallback
    raw = Path(txt_path).read_bytes()
    for enc in ("utf-8", "gb18030"):
        try:
            text = raw.decode(enc)
            if enc != "utf-8":
                print(f"  [编码] {Path(txt_path).name}: 用 {enc} 解码")
            return text
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"无法识别编码 (utf-8/gb18030 都失败): {txt_path}")


# ── 章节切分 ──

def split_chapters(text):
    chapter_re = re.compile(
        r'^\s*(第[一二三四五六七八九十百千零\d]+[章节回卷部集篇].*?$'
        r'|Chapter\s*\d+.*?$'
        r'|CHAPTER\s*\d+.*?$'
        r'|卷[一二三四五六七八九十\d]+.*?$'
        r'|\d{1,4}[、.．]\s*\S+.*?$)',
        re.MULTILINE
    )
    splits = list(chapter_re.finditer(text))
    if not splits:
        return split_by_size(text, CHARS_PER_SEGMENT)
    chapters = []
    if splits[0].start() > 200:
        preface = text[:splits[0].start()].strip()
        if preface:
            chapters.append(("序", preface))
    for i, m in enumerate(splits):
        start = m.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        title = m.group().strip()[:30]
        body = text[start:end].strip()
        if body:
            chapters.append((title, body))
    return chapters


def split_by_size(text, max_chars):
    paragraphs = text.split("\n")
    segments, current, current_len, part = [], [], 0, 0
    for p in paragraphs:
        current.append(p)
        current_len += len(p)
        if current_len >= max_chars:
            part += 1
            segments.append((f"第{part}段", "\n".join(current)))
            current, current_len = [], 0
    if current:
        part += 1
        segments.append((f"第{part}段", "\n".join(current)))
    return segments


def merge_small_chapters(chapters, min_chars=CHARS_PER_SEGMENT):
    merged, buf_t, buf_b, buf_len = [], [], [], 0
    for title, body in chapters:
        buf_t.append(title)
        buf_b.append(body)
        buf_len += len(body)
        if buf_len >= min_chars:
            label = f"{buf_t[0]} ~ {buf_t[-1]}" if len(buf_t) > 1 else buf_t[0]
            merged.append((label, "\n\n".join(buf_b)))
            buf_t, buf_b, buf_len = [], [], 0
    if buf_b:
        label = f"{buf_t[0]} ~ {buf_t[-1]}" if len(buf_t) > 1 else buf_t[0]
        merged.append((label, "\n\n".join(buf_b)))
    return merged


# ── 生产问题记录 ──

ISSUES_LOG = OUTPUT_DIR / "_analysis_issues.jsonl"

def log_issue(novel_name, part_num, reason, roles, text_preview=""):
    """轻量记录角色分析异常"""
    try:
        entry = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "novel": novel_name,
            "part": part_num,
            "reason": reason,
            "roles": roles,
            "preview": text_preview[:100],
        }
        with open(ISSUES_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── 角色分析 → easyVoice JSON ──

def analyze_and_build_json(text, voice_cfg):
    """
    分析文本角色 → 构建 /generateJson 的 data 数组。
    返回 (data_array, role_summary_str)
    """
    roles_map = voice_cfg["roles"]
    defaults = voice_cfg.get("default_params", {})

    # 调用角色分析
    config_for_analyze = {
        "roles": {k: v for k, v in roles_map.items()},  # 兼容格式
        "gender_keywords": {"male": [], "female": []},
        "speech_verbs": [],
    }
    # analyze_roles 需要 config["roles"][role] 可以是 dict 或 str
    # 这里传入的 roles_map 值是 {"voice":..., "desc":...}，但 analyze_roles
    # 只关心 key 存在与否来映射 role tag，不读 voice。
    # 我们直接用 analyze_roles 的内置 config。
    try:
        tagged_text, _, report = _analyze_text(text)
    except Exception as e:
        print(f"    角色分析异常: {e}，回退单音色")
        return None, "分析失败"

    # 解析 tagged_text → segments
    # 格式: [role_tag]文本内容[/role_tag]
    tag_re = re.compile(r'\[(\w+)\](.*?)\[/\1\]', re.DOTALL)
    matches = list(tag_re.finditer(tagged_text))

    if not matches:
        print(f"    角色标注为空，回退单音色")
        return None, "无标注"

    data = []
    role_counts = {}

    for m in matches:
        role_tag = m.group(1)
        segment_text = m.group(2).strip()
        if not segment_text or len(segment_text) < 2:
            continue

        # 查配置映射
        if role_tag in roles_map:
            voice_info = roles_map[role_tag]
        else:
            voice_info = roles_map.get("unknown", {"voice": "zh-CN-YunxiNeural", "desc": "未知"})

        voice = voice_info["voice"] if isinstance(voice_info, dict) else voice_info
        desc = voice_info.get("desc", role_tag) if isinstance(voice_info, dict) else role_tag

        data.append({
            "desc": desc,
            "text": segment_text,
            "voice": voice,
            "rate": voice_info.get("rate", defaults.get("rate", "+0%")) if isinstance(voice_info, dict) else defaults.get("rate", "+0%"),
            "pitch": voice_info.get("pitch", defaults.get("pitch", "+0Hz")) if isinstance(voice_info, dict) else defaults.get("pitch", "+0Hz"),
            "volume": voice_info.get("volume", defaults.get("volume", "+0%")) if isinstance(voice_info, dict) else defaults.get("volume", "+0%"),
        })

        role_counts[role_tag] = role_counts.get(role_tag, 0) + 1

    summary = ", ".join(f"{k}:{v}" for k, v in sorted(role_counts.items(), key=lambda x: -x[1]))
    return data, summary


def build_single_voice_json(text, voice, voice_cfg):
    """单音色回退：整段文本用一个音色"""
    defaults = voice_cfg.get("default_params", {})
    return [{
        "desc": "全文",
        "text": text,
        "voice": voice,
        "rate": defaults.get("rate", "+0%"),
        "pitch": defaults.get("pitch", "+0Hz"),
        "volume": defaults.get("volume", "+0%"),
    }]


# ── 音频生成 ──

def _calc_timeout(num_segments):
    """根据片段数计算合理超时: 每片段约 3 秒 + 30 秒余量，上限 300 秒"""
    return min(300, max(60, num_segments * 3 + 30))


def _retry_delay(attempt):
    """指数退避"""
    return RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]


def _do_request(url, payload, timeout):
    """发送请求，返回 (audio_bytes, None) 或 (None, error_str)"""
    try:
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if len(data) < 1000:
                try:
                    err = json.loads(data)
                    return None, f"API错误: {err}"
                except json.JSONDecodeError:
                    pass
            return data, None
    except Exception as e:
        etype = type(e).__name__
        return None, f"{etype}: {e}"


def generate_multirole(data_array, output_path):
    """调用 /generateJson 生成多角色音频，带指数退避重试"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"data": data_array}).encode("utf-8")
    timeout = _calc_timeout(len(data_array))

    for attempt in range(MAX_RETRIES):
        if not health_check():
            print(f"    服务不可用，尝试重启...")
            if not ensure_server():
                return False
            time.sleep(3)

        audio, err = _do_request(f"{API}/api/v1/tts/generateJson", payload, timeout)
        if audio:
            with open(output_path, "wb") as f:
                f.write(audio)
            return True

        delay = _retry_delay(attempt)
        print(f"    失败 (第{attempt+1}次, {delay}s后重试): {err}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(delay)

    return False


def generate_single(text, voice, output_path):
    """单音色 /createStream，带指数退避重试"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "text": text, "voice": voice,
        "pitch": "+0Hz", "rate": "+0%", "volume": "+0%",
    }).encode("utf-8")
    timeout = _calc_timeout(1)

    for attempt in range(MAX_RETRIES):
        if not health_check():
            if not ensure_server():
                return False
            time.sleep(3)

        audio, err = _do_request(f"{API}/api/v1/tts/createStream", payload, timeout)
        if audio:
            with open(output_path, "wb") as f:
                f.write(audio)
            return True

        delay = _retry_delay(attempt)
        print(f"    失败 (第{attempt+1}次, {delay}s后重试): {err}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(delay)

    return False


# ── 小说处理 ──

def process_novel(txt_path, voice_cfg, single_voice=None):
    novel_name = txt_path.stem
    dir_name = re.sub(r'[《》]', '', novel_name).strip()
    novel_output = OUTPUT_DIR / dir_name
    novel_output.mkdir(parents=True, exist_ok=True)

    mode_str = f"单音色 ({single_voice})" if single_voice else "多角色自动配音"

    print(f"\n{'═' * 60}")
    print(f"  小说: {novel_name}")
    print(f"  模式: {mode_str}")
    print(f"  输出: {novel_output}")

    text = read_novel_text(txt_path)

    total_chars = len(text)
    print(f"  总字数: {total_chars:,}")

    chapters = split_chapters(text)
    segments = merge_small_chapters(chapters)
    print(f"  分为 {len(segments)} 段")
    print(f"{'═' * 60}")

    success, skipped, failed = 0, 0, 0
    failed_parts = []
    total_segs = len(segments)

    write_progress(novel_output, novel_name, total_segs, 0, 0, 0, "processing")

    for i, (label, body) in enumerate(segments):
        part_num = i + 1
        filename = f"{dir_name}_{part_num:03d}.mp3"
        output_path = novel_output / filename

        if output_path.exists() and output_path.stat().st_size > 10000:
            print(f"  [{part_num:03d}/{total_segs}] 已存在，跳过: {filename}")
            skipped += 1
            write_progress(novel_output, novel_name, total_segs, success, skipped, failed, "processing", failed_parts)
            continue

        chars = len(body)
        est_min = chars / 250
        print(f"  [{part_num:03d}/{len(segments)}] {label} ({chars:,}字, ~{est_min:.0f}分钟)")

        if single_voice:
            # 单音色模式
            print(f"    模式: 单音色 ({single_voice})")
            ok = generate_single(body, single_voice, output_path)
        else:
            # 多角色模式
            data_array, role_summary = analyze_and_build_json(body, voice_cfg)
            if data_array and len(data_array) > 0:
                print(f"    角色: {role_summary}")
                print(f"    分段: {len(data_array)} 个语音片段")
                # 异常检测: unknown 占比过高
                unk_count = sum(1 for d in data_array if d["desc"] == "未知角色")
                if unk_count > len(data_array) * 0.5:
                    log_issue(novel_name, part_num, f"unknown过多({unk_count}/{len(data_array)})",
                              role_summary, body[:100])
                ok = generate_multirole(data_array, output_path)
            else:
                # 回退单音色
                fallback_voice = voice_cfg["roles"]["narrator"]["voice"]
                print(f"    回退: 单音色 ({fallback_voice})，原因: {role_summary}")
                log_issue(novel_name, part_num, f"回退单音色: {role_summary}",
                          "narrator_fallback", body[:100])
                ok = generate_single(body, fallback_voice, output_path)

        if ok and output_path.exists() and output_path.stat().st_size > 1000:
            size_mb = output_path.stat().st_size / 1024 / 1024
            print(f"    完成: {filename} ({size_mb:.1f}MB)")
            success += 1
        else:
            if output_path.exists():
                output_path.unlink()
            print(f"    失败: {filename}")
            failed += 1
            failed_parts.append(label)

        write_progress(novel_output, novel_name, total_segs, success, skipped, failed, "processing", failed_parts)

    # ── 二轮补跑 failed_parts ──
    if failed > 0:
        print(f"\n  === 二轮补跑 {failed} 个失败段 ===")
        retry_failed = []
        for i, (label, body) in enumerate(segments):
            if label not in failed_parts:
                continue
            part_num = i + 1
            filename = f"{dir_name}_{part_num:03d}.mp3"
            output_path = novel_output / filename
            if output_path.exists() and output_path.stat().st_size > 10000:
                continue

            chars = len(body)
            print(f"  [补跑 {part_num:03d}] {label} ({chars:,}字)")

            if single_voice:
                ok = generate_single(body, single_voice, output_path)
            else:
                data_array, role_summary = analyze_and_build_json(body, voice_cfg)
                if data_array and len(data_array) > 0:
                    ok = generate_multirole(data_array, output_path)
                else:
                    fallback_voice = voice_cfg["roles"]["narrator"]["voice"]
                    ok = generate_single(body, fallback_voice, output_path)

            if ok and output_path.exists() and output_path.stat().st_size > 1000:
                size_mb = output_path.stat().st_size / 1024 / 1024
                print(f"    补跑成功: {filename} ({size_mb:.1f}MB)")
                success += 1
                failed -= 1
            else:
                if output_path.exists():
                    output_path.unlink()
                print(f"    补跑仍失败: {filename}")
                retry_failed.append(label)

        failed_parts = retry_failed

    final_status = "completed" if failed == 0 else "partial" if success > 0 else "failed"
    write_progress(novel_output, novel_name, total_segs, success, skipped, failed, final_status, failed_parts)

    return {
        "name": novel_name, "dir": str(novel_output),
        "total_segments": len(segments),
        "success": success, "skipped": skipped, "failed": failed,
        "failed_parts": failed_parts, "total_chars": total_chars,
    }


def main():
    parser = argparse.ArgumentParser(description="easyVoice 批量小说转音频 (多角色)")
    parser.add_argument("--single-voice", default=None,
                        help="单音色模式 (例: zh-CN-YunxiNeural)")
    parser.add_argument("--no-multirole", action="store_true",
                        help="禁用多角色，使用 narrator 单音色")
    parser.add_argument("--file", default=None,
                        help="只处理指定的 txt 文件名")
    args = parser.parse_args()

    voice_cfg = load_voice_config()

    single_voice = args.single_voice
    if args.no_multirole and not single_voice:
        single_voice = voice_cfg["roles"]["narrator"]["voice"]

    if not ensure_server():
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.file:
        target = TXT_DIR / args.file
        if not target.exists():
            # 也试试带扩展名
            candidates = list(TXT_DIR.glob(f"*{args.file}*"))
            if candidates:
                target = candidates[0]
            else:
                print(f"错误: 找不到 {args.file}")
                sys.exit(1)
        txt_files = [target]
    else:
        txt_files = sorted(TXT_DIR.glob("*.txt"))

    if not txt_files:
        print("没有找到 txt 文件")
        sys.exit(0)

    mode = f"单音色 ({single_voice})" if single_voice else "多角色自动配音"
    print(f"找到 {len(txt_files)} 个小说文件")
    print(f"模式: {mode}")
    print(f"输出: {OUTPUT_DIR}")

    results = []
    for txt_file in txt_files:
        try:
            result = process_novel(txt_file, voice_cfg, single_voice)
            results.append(result)
        except KeyboardInterrupt:
            print("\n用户中断")
            break
        except Exception as e:
            print(f"\n处理失败: {txt_file.name} - {e}")
            import traceback
            traceback.print_exc()
            results.append({"name": txt_file.stem, "error": str(e), "success": 0, "failed": 1})

    # ── 汇总 ──
    print(f"\n{'═' * 60}")
    print("  批量处理完成")
    print(f"{'═' * 60}")
    total_success, total_failed = 0, 0
    for r in results:
        s = r.get("success", 0)
        f = r.get("failed", 0)
        sk = r.get("skipped", 0)
        total_success += s + sk
        total_failed += f
        status = "成功" if f == 0 and not r.get("error") else "部分失败" if s > 0 else "失败"
        print(f"  {r['name'][:50]}")
        if r.get("error"):
            print(f"    错误: {r['error']}")
        else:
            print(f"    {status} | 成功:{s} 跳过:{sk} 失败:{f}")
            if r.get("failed_parts"):
                print(f"    失败段: {', '.join(r['failed_parts'][:5])}")
    print(f"{'─' * 60}")
    print(f"  总计: 成功 {total_success}, 失败 {total_failed}")
    print(f"  输出: {OUTPUT_DIR}")
    print(f"{'═' * 60}")


if __name__ == "__main__":
    main()
