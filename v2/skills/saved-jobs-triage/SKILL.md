---
name: saved-jobs-triage
description: "入口 A（参数：日期标记如 1005 可读性用；`local`/`linkedin` 选来源，默认 local 队列有货用 local、空了用 linkedin）：从 scout 本地队列 ledger/scout_queue.tsv 或 LinkedIn Saved 列表取台账里没见过的前 5 个，每个开一个 tab 停在官方申请页，出事实卡并落台账（只记 triage 过）。自动预取下一批，未看的最多挂 2 批。用于：批量看 saved 岗位、一次开五个、triage saved jobs。"
---

# saved-jobs-triage

**本质**：`f(队列或 Saved 里台账没见过的前 5 个) → 5 张事实卡 + 5 个停在申请页的 tab + 台账各一行 triaged`。摆桌子，不评估。判死清单、卡片格式、台账 schema、输出纪律都在 `rules.md`，本文件只写流程。

## 编排：主会话是调度台，每批一个 subagent

- **每批起一个 subagent**（Agent，general-purpose），prompt：「读 `<ROOT>/.claude/skills/saved-jobs-triage/SKILL.md`，按第 0–3 步跑一批（来源：<local|linkedin>），写完台账和 cards/ 后把 5 张卡原文作为最终返回，不要多余叙述。」JD 原文和浏览器往返都留在 subagent 里。
- **主会话只做**：起 subagent → 收卡展示给本人 → `bash $ROOT/bin/job.sh logbatch <本批 job_key…>` → 预取。
- **预取**：本人没看的批次 < 2 就立刻起下一批。本人开始看某批、或说「下一批」= 那批消化掉。本人说「停」→ 不再预取，已开的 tab 留着。
- subagent 出卡当下就写台账，下一批读台账游标，天然不重复。subagent 拿到独立的 tab 组；**triage subagent 严禁 `tabs_close_mcp`**（tab 留给本人投）。
- 本人看卡后对某个岗位说「改简历 / 帮我填 / reach out」→ 主会话对那个岗位走 `job-apply`（复用 `cards/`，不重抓 JD）。

## 第 0 步：读规则 + 游标（一次 Bash 调用；本会话读过的不重读）

```bash
ROOT=<ROOT>
cat "$ROOT/rules.md" "$ROOT/resume_glance.md" "$ROOT/all_technical_skills.md" "$ROOT/browser/README.md" "$ROOT/browser/apply_link.js" "$ROOT/browser/corner_scan.js"
echo '--- 已见 li id ---'; bash $ROOT/bin/job.sh seen
```

Shell 是 zsh，每次调用是新 shell：每个命令块自带 `ROOT=`，直接写 `bash $ROOT/bin/job.sh <verb>`，不要用变量当命令。

## 第 1 步：取台账没见过的前 5 个

**来源**：参数说了 `local` / `linkedin` 就听参数；没说 → 队列里有未见项用 local，没有用 linkedin。两个来源的游标都只看台账。

- **local**：一次 Bash 取 `ledger/scout_queue.tsv` 里 jid 不在 `job.sh seen` 的前 5 行（note 列的扣分标注抄进卡）。apply_url 已是外链申请页：先 `job.sh lookup li:<jid> <apply_url 去查询串>` 去重，然后每岗 `tabs_create_mcp` **直接导航 apply_url**，跳过第 2 步的 LinkedIn 解析。note 带 `EASYAPPLY` 或 JD 抓不全时才开 LinkedIn job view 补。
- **linkedin**：在 `linkedin.com/jobs-tracker/`（Saved 标签）跑，`DONE` 填 `seen` 的输出；new 不足 5 就 `scroll` 再跑（懒加载一屏约 10 条）：

```js
const DONE=new Set('/* seen 输出原样粘贴 */'.trim().split(/\s+/));
const seen=new Set(),out=[];
for(const a of document.querySelectorAll('a[href*="/jobs/view/"]')){const m=a.href.match(/\/jobs\/view\/(\d+)/);if(!m||seen.has(m[1]))continue;seen.add(m[1]);if(DONE.has(m[1]))continue;
out.push(m[1]+'|'+(a.innerText||'').replace(/\s+/g,' ').trim().replace(/(Posted|Reposted).*/,'').slice(0,70));}
seen.size+' on page, '+out.length+' new\n'+out.slice(0,5).join('\n')
```

## 第 2 步：每个职位一个 tab，停在申请页

linkedin 来源：每岗 `tabs_create_mcp` → `browser_batch`（导航 job view → wait 3s → 跑 `apply_link.js`）。拿到外链先 `job.sh lookup li:<id> <外链去查询串>`：返回 `SEEN`（重复发帖）→ 只出一行「重复：同 `li:X` · tab 号」，不导航、不出卡、不补位，台账照写一行让游标跳过。

| `apply_link.js` 返回 | tab 停哪 |
|---|---|
| `EASYAPPLY` / `NOBTN` | 留在 LinkedIn 页 |
| ATS / careers 外链 | 导航外链（查询参数带上）→ wait 5s |
| Google 表单 / 邮箱等非 ATS | 不导航，地址写进卡 |

每个 tab：`get_page_text` + `corner_scan.js`，按 `browser/README.md` 的「抓全判定」检查；抓不全不出卡。

## 第 3 步：出卡 + 落盘

按 `rules.md` 先过判死清单（命中缩成一行 + tab 号），其余按「事实卡」10 行出（第 10 行 = 申请页 tab 号 + 站点）。

5 张卡出完后**一次 Bash 调用**落盘（字段用真 tab）：
- `jobs.tsv` 每岗一行，`source=triage`、`status=triaged`，判死 `kill=Y:第N条`。
- `skill_gaps.tsv` 每个缺口词一行（判死和重复岗位不写）。
- 每张非判死卡写到 `$(bash $ROOT/bin/job.sh card <job_key>)`：卡片原文 + 抓取日期 + 申请页 URL + tab 号。
- `bash $ROOT/bin/job.sh check`：无 BAD 行。

不改简历、不写 `applications/`、不关 tab。
