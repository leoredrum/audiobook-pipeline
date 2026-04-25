# Setup: 部署 easyVoice 后端

本 repo 的 `batch_easyvoice.py` 调用一个本地起的 easyVoice node 服务（默认 `http://localhost:3000`）做 TTS。easyVoice 是独立的 npm 项目，必须单独 clone + build。

## 上游

- **GitHub**: https://github.com/cosin2077/easyVoice
- **License**: MIT（见上游 repo）
- **后端**: Node + Express，调用 microsoft edge-tts

## 步骤

```bash
# 1. clone（位置默认在 $NOVEL_ROOT/easyVoice，也可以放别处用 EASYVOICE_DIR 指定）
cd "$NOVEL_ROOT"   # 默认 ~/Documents/novel
git clone https://github.com/cosin2077/easyVoice.git
cd easyVoice

# 2. 装依赖（用 pnpm，按上游 README）
pnpm install

# 3. build backend
cd packages/backend
pnpm build

# 4. 第一次跑可手动启起来确认
MODE=production node dist/server.js
# 看到 "server is running on port 3000" 即 OK，Ctrl-C 停掉

# 5. 后续 batch_easyvoice.py 会自己 nohup 拉起这个进程，不需要手动启
```

## 环境变量

| 变量 | 用途 | 默认 |
|---|---|---|
| `NOVEL_ROOT` | 数据目录根 | `~/Documents/novel` |
| `EASYVOICE_DIR` | easyVoice clone 位置 | `$NOVEL_ROOT/easyVoice` |
| `VOICE_CONFIG` | 多角色音色配置 | `<本 repo>/config/easyvoice_voices.json` |

## 音色配置

`config/easyvoice_voices.json` 把 8 个角色（narrator/male_main/male_side/male_extra/female_main/female_side/female_extra/unknown）映射到具体的 microsoft edge-tts 音色。`analyze_roles.py` 会扫文本里的角色对话，分配到这些角色 slot 上。想换嗓子直接改这个 json。

可用音色清单见 [edge-tts 官方文档](https://github.com/rany2/edge-tts) 或 `edge-tts --list-voices` 命令。
