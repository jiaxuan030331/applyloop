---
name: scout
description: "搜索并入队：voyager 搜过去 N 天的 new-grad 岗（参数如 1d/3d，默认 1d），去重和硬规则由 bin/scout.py 在本地做，扣分交并行 subagent 判；0 分自动入队、-1 列给本人挑、≤-2 丢，写 ledger/scout_queue.tsv 交给 saved-jobs-triage。不入台账、不出卡、不投。用于：今天有什么新岗、扫一遍最近的坑、把搜索加回来。"
---

# scout

**本质**：浏览器只负责**搜索和抓 JD**，结果 blob 落盘不进 context；`bin/scout.py` 做去重、黑名单、标题级和年限/关帖/老帖这些确定性规则；只有需要判断的扣分交给并行 subagent（每片 ≤30 条）；merge 校验每条都有判定。筛选规则本体在 `rules.md`「scout：筛选模型」，本文件只写流程。

## 红线

- voyager 只在自己新开的 linkedin.com tab 里跑，不碰本人已开的 tab；LinkedIn 上不点任何按钮。
- **voyager 返回 302/401 → 立刻停**，请本人刷新 LinkedIn 登录；不重试、不绕。429 → 停 60s 再续。
- 不写 `jobs.tsv`、不出卡、不写 `applications/`。

## 第 0 步：读规则（一次 Bash 调用）

```bash
ROOT=<ROOT>
cat "$ROOT/rules.md" "$ROOT/browser/README.md"
grep -v '^#' "$ROOT/config/scout_queries.txt"
cat "$ROOT/browser/voyager_search.js" "$ROOT/browser/voyager_jd_batch.js" "$ROOT/browser/jd_screen.js"
```

`$ARGUMENTS`：`1d` / `3d` / `7d` → timeRange `r86400` / `r259200` / `r604800`（默认 1d）。下文 `<D>` = 今天日期，`<T>` = 当前时分（文件名防重名）。

## 第 1 步：搜索 → 卡片落盘

`list_connected_browsers` → 问本人用哪个 → `tabs_create_mcp` → 导航 `linkedin.com/jobs/`（voyager 要同源 + 登录态）。注入 `voyager_search.js`，**一条 query 一次调用**（单条 3d 可跑 ~30s，两条必超 45s）：

```js
const out = await window.linkedin.scrapeQuery("<query>", {timeRange: "<rXXXX>"});
window.__cards = (window.__cards||[]).concat(out.cards);
out.kw+': '+out.fetched+' cards, stop='+out.stop
```

跑完：`window.linkedin.dump(window.__cards, 'scout_cards_<D>_<T>.jsonl')`。

## 第 2 步：本地预筛（Bash）

```bash
bash -c 'cd <ROOT> && python3 bin/scout.py prefilter "$(ls -t ~/Downloads/scout_cards_*.jsonl | head -1)"'
```

输出一行量（raw → new → T-drop → 待抓 JD）和 `SURVIVORS <jid …>`。把这串 jid 贴回浏览器：`window.__jids = '<jid …>'.split(' ')`。

## 第 3 步：抓 JD → 证据落盘

```js
window.__jd_raw = window.__jd_raw||{};
const r = await window.linkedin.fetchJDs(window.__jids.filter(j=>!window.__jd_raw[j]).slice(0,110), {store: window.__jd_raw});
JSON.stringify({...r, remaining: window.__jids.filter(j=>!window.__jd_raw[j]).length})
```

重复到 `remaining: 0`。某批「did not respond in time」不等于失败，同一调用重发即可（有续传）。然后注入 `jd_screen.js`：

```js
window.linkedin.dump(window.linkedin.screenJDs(window.__jd_raw, window.__jids), 'scout_ev_<D>_<T>.jsonl')
```

## 第 4 步：确定性筛 + 切片（Bash）

```bash
bash -c 'cd <ROOT> && python3 bin/scout.py screen "$(ls -t ~/Downloads/scout_ev_*.jsonl | head -1)"'
```

输出 `SHARDS <n> <shard 路径 …>`。

## 第 5 步：并行 subagent 判分

**一条消息里**为每个 shard 起一个 Agent（general-purpose），prompt：

> 你是 scout 的扣分判定员。先读 `<ROOT>/rules.md` 的「scout：筛选模型」一节，再读 `<shard 路径>`（TSV；kill / yrs / spon / grad / contract / stack 是从 JD 抽出的证据句）。逐行按硬丢 + 扣分判：硬丢或累计 ≤ -2 → `DROP`；累计 -1 → `-1`；0 → `0`。证据为空不等于命中；拿不准按有利方向判（照存）。把结果写到同目录同名 `.out` 文件：每行 `jid<TAB>判定<TAB>理由`，判定只能是 `0` / `-1` / `DROP`；理由 ≤60 字、引证据原文，0 分写 `-`；**每个 jid 恰好一行**。只用 Bash 读写这两个文件，不开浏览器、不读别的文件。最终只返回一行：`shard_NN: N 行 · 0=a · -1=b · DROP=c`。

## 第 6 步：合并 → 本人挑 -1

```bash
cd <ROOT> && python3 bin/scout.py merge
```

`MERGE FAIL` → 只重跑报错的那几片的 subagent，再 merge。成功后把输出原样给本人：0 分自动入队清单 + 编号的 -1 清单（公司 · title · 地点 · 扣分理由）。**停下等本人回编号**（如 `2,5,7-9` / `all` / `none`）。

## 第 7 步：入队 + 日报

```bash
cd <ROOT> && python3 bin/scout.py commit <本人的选择>
```

它把 0 分和选中的 -1 追加进 `ledger/scout_queue.tsv`（apply_url 存外链申请页，聚合/广告跳转已解开；Easy Apply 存 LinkedIn view 并标 `EASYAPPLY`），把所有评估过的 jid 追加进 `scout_seen.txt`（没挑中的 -1 也算，不再出现），写 `ledger/scout_reports/<D>.md`（J-drop 逐条带证据，可翻案）。

对话里复述：入队数 + 值得说的模式（没有就不说）。入队数持续 >25 → 提一句「规则可能松了，要校准吗」。结尾提示 `/saved-jobs-triage` 开始消化。

## 补充

- 中途断了：`ledger/scout_work/<D>/` 里有每一步的中间产物，从断的那步重跑即可；`commit` 有防重复标记。
- 3d 量级参考：raw ~2700 → new ~950；1d：raw ~1600 → new ~450。
