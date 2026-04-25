# audiobook-pipeline

把中文网文 txt 批量转成带 ID3 标签和封面的有声书 mp3，端到端流程：

```
txt 文件 ──▶ batch_easyvoice.py ──▶ output_easyvoice/<原始名>/*.mp3
                                                     │
                                                     ▼
                              rename_easyvoice.py（精简目录名 + mp3 改名 + padding）
                                                     │
                                                     ▼
                              tag_easyvoice.py（写 album/title/track/genre/artist）
                                                     │
                                                     ▼
                              embed_cover.py（嵌入封面图）
                                                     │
                                                     ▼
                              成品：可直接导入 iTunes / Plex / 任何 mp3 播放器
```

## 上游依赖：easyVoice

TTS 后端用的是开源项目 [cosin2077/easyVoice](https://github.com/cosin2077/easyVoice)（基于 microsoft edge-tts，本地起 node 服务，多角色配音）。本 repo 不 vendor 它，需要单独 clone + build，详见 [docs/setup.md](docs/setup.md)。

## 目录结构

```
audiobook-pipeline/
├── scripts/
│   ├── batch_easyvoice.py     # 主转换：txt → mp3（多角色，含 GB18030 自动 fallback）
│   ├── analyze_roles.py       # 给 batch_easyvoice 用的角色分析
│   ├── rename_easyvoice.py    # 后处理 1：精简目录名 + 重命名 mp3（按总数动态 padding）
│   ├── tag_easyvoice.py       # 后处理 2：批量打 ID3 tag（用 ffmpeg）
│   └── embed_cover.py         # 后处理 3：批量嵌入封面图（用 ffmpeg）
├── shell/
│   ├── easyvoice.sh           # easyVoice 服务启停封装
│   ├── audiobook.sh           # 单本转换包装
│   ├── audiobook_monitor.sh   # 转换监控
│   └── queue_all_novels.sh    # 批量队列
├── mac/                       # 双击启动器（macOS .command）
│   ├── EasyVoiceLauncher.command
│   ├── SelectNovelEasyVoice.command
│   ├── NovelEasyVoice.command
│   ├── QueueAllNovels.command
│   ├── CheckEasyVoiceProgress.command
│   └── CheckQueueProgress.command
├── config/
│   └── easyvoice_voices.json  # 多角色音色配置（旁白/男主/男配/女主/女配/...）
├── covers/                    # 封面图存放（被 .gitignore，本机自管）
├── docs/
│   └── setup.md               # easyVoice 部署步骤
└── README.md
```

## 用法

### 一次性环境配置

```bash
# 1. 装 ffmpeg（处理 ID3 / 封面）
brew install ffmpeg

# 2. clone + build easyVoice（详见 docs/setup.md）

# 3. 设置数据目录（默认 ~/Documents/novel；可自改）
export NOVEL_ROOT="$HOME/Documents/novel"
mkdir -p "$NOVEL_ROOT"/{txt,output_easyvoice,covers}

# 4. 复制书目配置模板，按你的实际书目填写
cp config/novels.example.json config/novels.json
# 编辑 config/novels.json：每本一条 {old_name, new_name, artist}
# 这个文件被 .gitignore，不会进 git
```

### 加一本新书的工作流

```bash
# 1. 把 txt 放进数据目录
cp 我的小说.txt "$NOVEL_ROOT/txt/"

# 2. 跑 TTS（自动启 easyVoice 服务）
python3 scripts/batch_easyvoice.py --file "我的小说.txt"
# 或单音色： --single-voice zh-CN-YunxiNeural
# 或不开多角色：--no-multirole

# 3. 在 config/novels.json 里加这本：
#    {"old_name": "<output_easyvoice 下的目录名>", "new_name": "<想显示的书名>", "artist": "..."}

# 4. 后处理三步走：先 dry-run 看映射，再 --apply
python3 scripts/rename_easyvoice.py            # dry-run
python3 scripts/rename_easyvoice.py --apply    # 真正改名

python3 scripts/tag_easyvoice.py --only "<new_name>"          # dry-run 单本
python3 scripts/tag_easyvoice.py --only "<new_name>" --apply

# 5. 把封面图放到 covers/（按 new_name 命名）
cp 我的封面.jpg "$NOVEL_ROOT/covers/<new_name>.jpg"

python3 scripts/embed_cover.py --only "<new_name>"          # dry-run
python3 scripts/embed_cover.py --only "<new_name>" --apply
```

### 设计要点

- **NOVEL_ROOT 环境变量**：所有 Python 脚本默认读 `~/Documents/novel`，可以用 `NOVEL_ROOT=/path/to/data python3 scripts/...py` 切到任何位置。
- **GB18030 fallback**：`batch_easyvoice.py` 自动识别源 txt 编码（搜书吧等站常给 GBK），失败再 fallback。
- **动态 padding**：`rename_easyvoice.py` 根据 mp3 总数决定 padding 位数（21 个 → `_01`-`_21`，878 个 → `_001`-`_878`）。
- **不重新编码**：tag / cover 都用 `ffmpeg -c copy`，stream-copy 速度 ~0.2s/文件。
- **Tag / cover 互不冲突**：先打 tag、再嵌入封面，互不覆盖（cover 嵌入用 `-map_metadata 0` 保留已有 tag）。

## 来源标注

- **easyVoice**（本 repo TTS 引擎依赖）：https://github.com/cosin2077/easyVoice
- 本 repo 是 [@leoredrum](https://github.com/leoredrum) 自己维护的批量 + 后处理流程，与 easyVoice 上游无关联。
