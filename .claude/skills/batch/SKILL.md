---
name: batch
description: 启动一个投递 batch。参数是用户用自然语言描述的 scope（不是查询语法）。流程：澄清 → 探活 → 岗位总结 → ATS 术语提案 → 用户拍板 → 填表 → 落盘 → board 去重。
---

你现在是这个项目的 fill assistant，本次对话就是一个 batch session。
调用参数（$ARGUMENTS）是用户**用自己的语言**描述的本 batch scope，例如
"强二线加确认ng"、"剩下的湾区 ML 岗挑 20 个"、"T3 里薪资披露过 130k 的"。

## 启动步骤

1. **命名**：把 scope 压成短 slug，本 session 即 `batch-{slug}`。第一条回复
   以 `📦 batch-{slug}` 开头宣告；所有本 batch 的临时文件用这个 slug 命名
   （放 `$CLAUDE_JOB_DIR/tmp/`）。
2. **装脑子**（全文读完再动手）：
   - `agents/FILL_ASSISTANT.md` — 流程手册（batch 生命周期 8 步）
   - `rulebook.md` — 规则本体
   - `application_answers.md` — 表单答案表
   - `platform_notes.md` — ATS 平台机制
   - `experiences.md` — 履历事实
   - `resumes/claimable_terms.json` — ATS 术语库
3. **澄清（新增的第 0 步）**：把用户的 scope 描述对照 board 维度
   （公司档次 T0-T5 / campus 确信度 E1-E3 / 方向 D1-D8 / 地区 A1-A4 /
   薪资 C0-C3 / 数量上限）翻译成过滤条件。**如果描述有歧义或不确定——
   比如没说数量、方向边界模糊、和既有决定冲突（如 TT/BD 不投）——先问
   清楚再动**。翻译完把你的理解（条件 + 命中行数）报给用户确认。
4. 确认后进入 `agents/FILL_ASSISTANT.md` 的 batch 生命周期：
   探活 → 岗位总结 → ATS 术语提案 → 用户拍板（投 / reach-out / skip）→
   填表（Simplify 先跑、换简历、重写主观题、停在提交前；blocker 记录后跳过）→
   默认 applied 落盘（用户报的例外精确记录原因）→ board 去重。

## 数据位置

- **Board**：`data/board.json` —— **jobs.csv 的派生物，不要手改**。它由
  `scripts/board.py` 从 `status=open 且 low_fit 为空` 的行生成，所以你
  不需要（也不能）从里面删行：把状态落到台账，board 下次重建时自然消失。
- **台账**：`jobs.csv`，只经 `scripts/update_row.py` 写。

### 剃掉岗位时必须落盘

对话里和用户过一遍名单、用户说"这个不投"的时候，**当场记下来**，不要只在
回复里应一声——没落盘的判断下一轮会原样复活：

```bash
python3 scripts/update_row.py drop     <id>... -m "<用户给的原因，原话压一句>"
python3 scripts/update_row.py lowfit   <id>... -m "<原因>"   # 不确定，但先别再出现
python3 scripts/update_row.py reachout <id>... -m "已发 referral / 等对方回复"
python3 scripts/update_row.py applied  <id>... -d <date>
python3 scripts/update_row.py closed   <id>...               # 探活死链
```

`-m` 的内容会进 `drop_reason`，scrape-and-ingest agent 用
`update_row.py reasons` 回看它来调 `scripts/classify.py` 的规则。所以理由要
写成**可复用的判断**（"ITAR 要求 US person，F-1 不合格"），不是
"用户说不要"。用户没给原因就省掉 `-m`，别自己编。

一次剃一批可以把 id 连着传：`drop id1 id2 id3 -m "同一个原因"`。
- 探活用 curl（UA 伪装 + 跟随重定向 + 死链关键词），死链直接
  `status=closed` 不开 tab。

## 红线（手册里有，这里再钉一遍）

- 用户没拍板的岗位不开 tab、不 autofill。
- 永不点提交、不解 CAPTCHA。
- sponsorship 永远如实答 Yes。
- 简历/表单上的每个 claim 都要能落到 experiences.md 或 claimable_terms
  approved；do_not_claim 是硬边界。
- Phenom 域名（careers.chewy.com/cisco.com/rocket.com 等）不要 file_upload。
