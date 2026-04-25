# audiobook-pipeline — 计划书

> 长期计划书. 目标 / 设计决策 / 里程碑 / 已否决方案.
> 当下进度在 `handoff.md`, 此文件是全局视图.

## 目标 (Why)

把网文 txt 批量转成带 ID3 标签和封面的有声书 mp3 (基于 cosin2077/easyVoice)

**更详细**:

- 要解决的问题: txt 小说没法直接听; 现有 TTS 工具只产 mp3 文件名, 没 ID3 / 封面 / 排序信息, 进 iTunes/Plex/手机播放器后看不到书名集数, 体验差.
- 谁用: leoredrum (任何想把网文做成有声书的人均可 fork 自用)
- 成功长什么样: 一个 txt 进, 一个带正确专辑/集数/作者/封面、能被任意 mp3 播放器正确识别和分组的有声书目录出.

## 范围

### 在范围内

- 单本 txt → mp3 (调 easyVoice 后端做 TTS)
- 章节切分 + 段长度合并 (在 `batch_easyvoice.py`)
- 多角色音色自动分配 (旁白/男主/男配/女主/女配/...)
- 编码自动识别 (UTF-8 失败 fallback GB18030, 兼容搜书吧等 GBK 来源)
- 后处理: 目录精简重命名 + mp3 序号 padding + ID3 tag (album/title/track/genre/artist) + 封面嵌入
- 配置驱动: 加新书只改 `config/novels.json`, 不改代码
- macOS 双击启动器 (.command)

### 不在范围内 (刻意不做)

- TTS 引擎本身: 用上游 [cosin2077/easyVoice](https://github.com/cosin2077/easyVoice), 本 repo 不 fork 不维护
- Web/GUI 界面: CLI 够用
- 自动找/购买正版封面: 用户自备 (放 covers/<new_name>.{jpg,png,webp})
- 自动作者识别: 作者笔名手填到 `config/novels.json`
- 已成品的版权 / 法律授权问题: 用户自行负责

## 架构 / 设计决策

### 决策 1: 用 ffmpeg 而不是 mutagen 处理 ID3 / 封面

- **选择**: ffmpeg `-c copy` stream-copy + `-map_metadata`
- **Why**: macOS 默认有 ffmpeg (brew install), 而 mutagen 受 PEP 668 限制装不上 system Python; ffmpeg 一份命令同时打 tag + 嵌封面, 不重新编码, 速度 ~0.2s/文件
- **考虑过的 alternatives**:
  - mutagen: 纯 Python 操作 ID3, 更快, 但 PEP 668 + 用户不想 venv
  - eyed3: 同 mutagen 问题
  - id3v2 CLI: 不能嵌封面

### 决策 2: 数据驱动配置 (`config/novels.json`)

- **选择**: list-of-dict JSON, 每本一条 `{old_name, new_name, artist}`, 文件被 `.gitignore`
- **Why**: 用户的具体收藏 (含书名/作者) 不应进 git history; 但流程本身要可被任何人复用 → 模板 `novels.example.json` 进 git, 实际 `novels.json` 不进
- **考虑过的 alternatives**:
  - 硬编码 dict (初版): 把 14 本 + 6 个作者笔名硬编码进 .py, 推 GitHub 等于公开收藏列表, 否决
  - TOML: 表达力相同, 但 Python 写入麻烦 (无标准库 writer); JSON 简单且通用
  - sqlite: 过度工程

### 决策 3: `NOVEL_ROOT` 环境变量分离工具与数据

- **选择**: 所有脚本读 `os.environ.get("NOVEL_ROOT", "~/Documents/novel")`
- **Why**: 工具 repo (代码) 和数据目录 (txt/mp3/封面) 应独立; clone 到任何位置 + 任何数据路径都能跑
- **考虑过的 alternatives**:
  - 把工具脚本放在数据目录里 (像旧 `~/Documents/novel/scripts/`): 工具升级要逐个 cp, 多机器同步麻烦
  - 命令行 `--root` 参数: 每次都要写, 烦; 环境变量 export 一次到 ~/.zshrc 永久

### 决策 4: 动态 mp3 序号 padding

- **选择**: `pad = len(str(total_mp3))`. 21 个 → `_01`-`_21`, 878 个 → `_001`-`_878`, 1500 个 → `_0001`-`_1500`
- **Why**: 字典序排序时不会出现 `_1.mp3, _10.mp3, _2.mp3` 这种乱序; 又不会浪费多余 0
- **考虑过的 alternatives**:
  - 全部用固定 3 位 padding: < 100 时多 1 位 0, 强迫症不爽
  - 4 位 padding: 同上, 浪费

## 里程碑

- [x] M1 — 流程跑通: txt → mp3 + 后处理三步
- [x] M2 — 通用化: 数据外置到 `config/novels.json`, 推上 GitHub
- [ ] M3 — 进一步打磨: 写单元测试 / CI / 错误处理细化 (按需)
- [ ] M4 — `pipeline.py` 一键端到端入口 (一条命令跑完 TTS + rename + tag + cover, 按需)

## 未解决问题

- Q1: easyVoice 后端服务的稳定性 — 长本 (1000+ 章) 跑十几小时, 偶尔遇到 TTS 段失败. 当前靠脚本里 5 次指数退避补救. 还需观察.

## 变更历史

- 2026-04-26 — 项目初始化, 通用化清理, 切 public
