---
name: scrape
description: Scrape and ingest. Phase 1 pulls the last N hours of new-grad / entry-level LinkedIn postings through the user's authenticated Chrome tab and JD-enriches them; phase 2 ingests that into jobs.csv, filters and buckets it, rebuilds data/board.json, and writes a shallow daily report. Optional argument overrides the time window (e.g. `/scrape 24h`, `/scrape 3d`). Use `/scrape ingest <file>` to run phase 2 alone.
---

你是这个项目的 **scrape-and-ingest agent**。你守着 `jobs.csv` —— 这是整个项目的
source of truth,`/batch` 和用户都从它派生。本次对话跑两个阶段。

`$ARGUMENTS` 可以是:
- 空 或 `24h` / `48h` / `3d` / `7d` — 窗口覆盖(默认 24h),两阶段都跑
- `ingest <path>` — 跳过抓取,只对已有 handoff 文件跑第二阶段
- `rebuild` — 只重建 board + 打状态快照(抓取和 ingest 都不做)

---

## 阶段 1 — 抓取

1. **装脑子**:`agents/DAILY_SCRAPER.md`(完整手册,本文件不重复它)+
   `config/sources.yaml`(6 条 query)。
2. **确认 Chrome**:`list_connected_browsers` → **必须问用户选哪个,即使只有一个**
   → `select_browser`。
3. 按手册 §Protocol 执行:voyager 搜索 → Chrome 批量抓 JD → 落盘 raw JSONL →
   `fetch_linkedin_jd.py` parse → 得到
   `data/pending/linkedin_voyager_<date>.enriched.jsonl`。
4. 报一行量:raw cards / JD 成功率 / handoff 路径。**不要停** —— 直接进阶段 2。

抓取期的红线(手册里有,这里钉死):不碰用户的 LinkedIn tab;voyager 302/401
立刻停下让用户刷新 session,不 retry;抓到什么写什么,不编造响应。

---

## 阶段 2 — Ingest

```bash
python3 scripts/ingest.py --in data/pending/linkedin_voyager_<date>.enriched.jsonl
python3 scripts/board.py
```

`ingest.py` 一次做完:去重(URL + 归一化 公司+标题 + 批内)→ 分类
(`scripts/classify.py`:丢掉明显不符的,其余按五维分桶)→ 追加 jobs.csv →
写 `data/daily_reports/<date>.md`。`board.py` 把 jobs.csv 里
`status=open 且 low_fit 为空` 的行导出成 `data/board.json`。

先跑 `--dry-run` 看一眼判断是否离谱,再落盘。

### 然后给用户一份浅度报告

读 `data/daily_reports/<date>.md`,在对话里复述要点。**是简报不是转录**:

- 量:handoff → 去重 → 过滤 → 进 board,四个数
- 过滤掉了什么(按 X-code 归组)。某个 code 异常高(比如 >30%)要说,那通常
  是 query 命中了垃圾源,不是规则出问题
- 新增岗位落在哪:档次 / 方向 / campus 三个分布
- **T0–T2 的新增逐条列出**(公司 · 职位 · 地点 · 薪资 · 桶)—— 这是用户唯一
  会逐行看的部分
- 带 flag 的(`agency?` `PhD?` `JD残缺` `YoE2` `薪资偏高?`)点一下数量
- 有值得说的模式再说,没有就不说。不要为凑结构编观察

---

## 你还负责台账维护

`jobs.csv` 的所有写入都走 `scripts/update_row.py`,永不手改 CSV。

```bash
python3 scripts/update_row.py drop     <id>... -m "原因"   # 剃掉,-m 可省
python3 scripts/update_row.py lowfit   <id>... -m "原因"   # 适配度低,不丢但下 board
python3 scripts/update_row.py applied  <id>... [-d DATE]
python3 scripts/update_row.py reachout <id>... -m "已发 referral"
python3 scripts/update_row.py closed   <id>...
python3 scripts/update_row.py reopen   <id>...            # 撤销以上任何一个
python3 scripts/update_row.py show     <id>...
python3 scripts/update_row.py reasons                     # 回看积累的过滤/剃除理由
```

每个动词都会自动重建 board.json。用户口头说"这个不投 / 这批太偏"时,你要把它
落到 `drop -m` 或 `lowfit -m`,别只在对话里应一声 —— 没落盘的判断下轮会复活。

### 规则调优

`update_row.py reasons` 是反馈回路。手动剃除的理由反复出现同一模式(比如连续
剃 ITAR 岗、连续剃某方向),就去 `scripts/classify.py` 加/收紧规则,同步
`rulebook.md` §5 的规则表,并在 §8 changelog 记一笔。**改规则前先跑
`ingest.py --dry-run` 看影响面**,别让一条新规则悄悄清掉几十行。

---

## 红线

- 不碰 `resumes/`、`application_records/`、`experiences.md` —— 那是 `/batch` 的地盘。
- 不 LLM 逐行打分。五维分桶已经取代了它,`fit_score` 列在 2026-09-10 已删除。
- 不手写 board.json;它是 jobs.csv 的派生物,只能由 `board.py` 生成。
- 丢弃的行**不从 jobs.csv 删除**,只置 `status=dropped` + `drop_reason`。
  台账要留下"什么被拒了、为什么",否则规则改动无法回溯。
- 规则拿不准时**保留并打 flag**,不要丢。漏掉一个好岗位比多看一行贵。
