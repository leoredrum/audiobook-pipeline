# 当前进度 (handoff)

> 每次收工时最后一位 AI 更新本文件。接棒 AI 先读这个。

**最近更新**: 2026-04-26 by Claude Opus 4.7

---

## ✅ 已完成

- 项目初始化 (5 个 Python 脚本 + 4 个 shell + 6 个 macOS .command + voice config + README + setup 文档)
- 编码 fallback: `batch_easyvoice.py` 自动识别 UTF-8 / GB18030 (搜书吧来源常给 GBK)
- 后处理三件套: rename / tag / embed_cover, 全部用 ffmpeg `-c copy` 流式拷贝, 速度 ~0.2s/文件
- 通用化: 把书目数据 (RENAMES / ARTIST) 从硬编码移到 `config/novels.json`, 实际配置文件被 `.gitignore`, 仅留 `novels.example.json` 模板
- GitHub repo 创建 + 切 public

## 🚧 正在做

(无, 流程已成型. 用户的本机数据继续在 `~/Documents/novel/` 下跑)

## 🔜 下一步

- 看 spec.md 的 M3/M4 (单元测试 + 一键入口), 按需做
- 用户当前还有一本超长小说 (1160 章) 在 TTS, 完成后跑后处理三步把它收尾

## ⚠️ 已知坑

- easyVoice 长本会偶尔遇到段失败, 当前靠 5 次指数退避兜底; 长跑多看几次 progress.json
- `tag_easyvoice.py` 写 ID3 时如果 ffmpeg 临时输出文件不带 `.mp3` 后缀, ffmpeg 会报 `Unable to choose an output format` (老版本写过 `.mp3.tmp` 踩了, 现已修为 `.__tag_tmp__.mp3`)
- `embed_cover.py` 必须在 tag 之后跑, 顺序反过来会让封面流被丢

## ❓ 待用户决策

(暂无)

---

## 接棒说明

你好, 我是接班的 AI。按 `AGENTS.md` 的协议:
1. 读过 `docs/spec.md` 了吗?
2. 读过 `README.md` + `docs/setup.md` 了吗? (后者讲 easyVoice 后端怎么部署)
3. 跟用户打个招呼, 一句话复述你理解的"现状 + 下一步", 让用户确认
4. 开工。每完成一个工作单元, 更新本文件 + commit + push
