# Agent 接棒协议

> 此文件面向 **任何** 接手本 repo 工作的 AI (Claude / Kimi / 智谱 / GPT Codex / MiniMax / 其他)。
> 本 repo 的主人不想每换个 AI / 换台电脑 / 开个新窗口, 就重新讲一遍项目在干什么。
> 规则很简单: **读 3 个文件 → 跟用户确认 → 干活 → 收工前更新进度**。

---

## 接棒时必读的 3 个文件 (按顺序)

1. **`docs/handoff.md`** — 最关键。上一位 AI 收工前写的"我做到哪了 / 卡在哪 / 下一步该做什么"。你读完这个就知道该接着干什么。
2. **`docs/spec.md`** — 项目整体计划书。目标 / 设计决策 / 里程碑 / 已否决的方案。handoff.md 是当下, spec.md 是全局。
3. **`README.md`** — 项目怎么跑。运行环境 / 部署命令 / 目录结构 / 凭证管理。

## 接棒开场动作

```
1. git pull                       # 拿最新
2. 读 docs/handoff.md             # 懂当下
3. 读 docs/spec.md                # 懂全局
4. 读 README.md                   # 懂怎么跑
5. 扫一眼 git log --oneline -10   # 了解近期势头
6. 跟用户打招呼, 用一两句话复述你理解的 "现状 + 下一步", 让用户确认你抓对了
7. 开始干活
```

---

## 工作单元约定

一次 commit = 一个**完整的语义单元**:
- ✅ 修好一个 bug / 加完一个 feature / 完成一次部署验收 / 用户说 OK
- ❌ **不要**每 edit 都 commit
- ❌ **不要**堆一天才 commit

每完成一个单元, 按这个顺序:

```
1. 更新 docs/handoff.md   (必须! 不然下一位 AI 接不上)
2. git add -A
3. git commit -m "<type>: <中文描述>"
4. git push
```

## handoff.md 更新规范

每次收工前 (或完成一个重要单元时) 在 handoff.md 里:
- ✅ **已完成** 区加一行, 带 commit hash
- 🚧 **正在做** 更新到你实际停下的位置 (文件:行, 为什么停的)
- 🔜 **下一步** 更新成你判断接棒 AI 应该接着做的事
- ⚠️ **已知坑** 加你刚踩过的坑 + 绕开方法
- ❓ **待用户决策** 加你卡着等用户确认的问题

handoff.md 的精神: **让下一位 AI 即使完全不懂这个项目, 读完 10 分钟也能无缝接手**。

## commit message 风格

Conventional commits + 中文 body:

```
feat: <功能描述>           # 新功能
fix: <bug 描述>             # bug 修
refactor: <重构描述>        # 重构不改行为
docs: <文档描述>            # 文档
chore: <杂务>               # 依赖 / CI / 构建
test: <测试>                # 测试
perf: <优化>                # 性能优化
```

带 scope 更清晰: `feat(baidu): 百度盘队列按钮化`

多行 body 用 HEREDOC 避免 shell 转义乱套:
```bash
git commit -m "$(cat <<'EOF'
feat(xxx): 一行标题

- 细节 1
- 细节 2
EOF
)"
```

---

## 通用禁忌

- ❌ 不 `git push --force` 到 `main` (分支可以, main 不行)
- ❌ 不跳过 hook (`--no-verify` / `--no-gpg-sign`)
- ❌ 不 commit secrets (`.env` / `secrets.yaml` / `*.key` / `*.pem` / token 明文)
  → commit 前 `git diff --cached` 扫一遍 staged 内容, 看见敏感字符串 unstage
- ❌ 不在 handoff.md / spec.md 里记 secrets, 就算是"临时 debug" 也不行
- ❌ 不随便删别人的 feature branch / tag / stash
- ❌ 遇到不熟悉的文件/配置先**问用户**, 不要当成 drift 清掉

---

## 对特定平台的小提示

- **Claude Code / Claude haha (MiniMax)**: 按自身 skill 规则走. 若有 superpowers skill 适用 (brainstorming / planning / TDD) 照用.
- **Cursor / Windsurf**: 可能自带 `.cursorrules`, 以本文件为主, .cursorrules 为辅.
- **Kimi / 智谱 / Codex**: 主要按本文件 + handoff.md. 不熟悉的工具链优先问用户.
- **任何新 AI**: 你是新面孔, 不要假装熟. 跟用户打个招呼说明你是谁, 问清模糊的地方再干活.

---

## 如果 handoff.md 跟代码对不上

说明上一位 AI 没按规范收工 (或中途崩掉了). 你的责任:

1. 先 `git log --oneline -20` + `git status` 把实际进度看清楚
2. 跟用户对齐 "我看到代码停在 X, handoff 说 Y, 以哪个为准"
3. 修正 handoff.md 反映实际状态, commit 一个 `docs(handoff): 补回 <AI 名>/<日期> 漏掉的进度`
4. 再继续推进

**handoff 是契约, 契约失效要当场修, 不要带着错的 handoff 继续堆新工作。**
