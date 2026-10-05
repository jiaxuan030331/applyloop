---
name: job-apply
description: "入口 B：对单个具体职位（已打开的页面，或一个 URL：内推链接 / 公司官网 / 朋友转发）抓全 JD、出事实卡、落台账（只记 triage 过），然后按本人要求：改简历（调 resume-tailor）、帮答申请表、reach out（判找 HM 还是要 ref link → 找人 → 写消息）。用于：投简历、申请这个岗位、看看这个 JD、要不要投、reach out、找内推。"
---

# job-apply

**本质**：`f(一个职位页) → 一张事实卡（7 天内见过就复用）→ 台账一行 triaged → 停，按本人要求做后续`。一次一个职位。判死清单、卡片格式、台账 schema、reach out 规则都在 `rules.md`，本文件只写流程。

## 第 0 步：读规则（一次 Bash 调用；本会话读过的不重读）

```bash
ROOT=<ROOT>
cat "$ROOT/rules.md" "$ROOT/resume_glance.md" "$ROOT/all_technical_skills.md" "$ROOT/browser/README.md" "$ROOT/browser/apply_link.js" "$ROOT/browser/corner_scan.js"
```

Shell 是 zsh，每次调用是新 shell：每个命令块自带 `ROOT=`，直接写 `bash $ROOT/bin/job.sh <verb>`。

## 第 1 步：定位页面 + 查台账

- 本人开着页面 → `tabs_context_mcp` 确认是哪个 tab，用它。给的是 URL → `tabs_create_mcp` + 导航（wait 5s）。
- LinkedIn `/jobs/view/` → 跑 `apply_link.js`：有外链就导航过去停在 ATS；Easy Apply 留在 LinkedIn；非 ATS 入口不导航。
- `job_key`：LinkedIn 页 `li:<id>`，其它 `url:<去查询串的申请 URL>`。`bash $ROOT/bin/job.sh lookup <job_key> <apply_url>`：
  - `NEW` → 第 2 步。
  - `SEEN` → 说一句「见过：`key` · 日期」。`card=` 有文件且 ≤7 天 → `cat` 复用，跳过 JD 抓取，只在申请页跑一次 `corner_scan.js` 补申请表问题；否则照常抓。`job_key` 沿用台账里那个。

## 第 2 步：拿全 JD（复用卡片时跳过）

同一 tab：`get_page_text` + `corner_scan.js`，按 `browser/README.md` 的「抓全判定」检查；抓不全不出卡。

## 第 3 步：出卡 → 落盘 → 停

按 `rules.md` 过判死清单（命中缩成一行），其余按「事实卡」9 行出。

**出卡后立刻一次 Bash 调用**（会话随时可能断）：
- `NEW` → `jobs.tsv` 追加一行 `source=apply`、`status=triaged`（判死 `kill=Y:第N条`）；`skill_gaps.tsv` 每个缺口词一行。`SEEN` → 不写台账、不重复写 gaps。
- 新抓的卡写到 `$(bash $ROOT/bin/job.sh card <job_key>)`。
- `bash $ROOT/bin/job.sh logbatch <job_key>`；`bash $ROOT/bin/job.sh check`。

然后**停下**，等本人说要做什么。

## 第 4 步：按本人要求做

**改简历**：调 `resume-tailor`，传版本 + 级别（卡里的 L1/L2 建议；本人点名 L3、或同意卡片第 9 行的 L3 提议才传 L3）。`resume-tailor` 自己写 `applications/` 记录，拿回 PDF 文件名告诉本人。本人说「不改」就用基线，不写任何记录。

**帮答申请表**：申请页 tab 用 `read_page`（filter interactive）/ `get_page_text` 列出所有问题和选项；多步表单读不到后面时请本人翻页或贴。答案只基于简历、`rules.md`「身份」和本人说过的事实，开放题按「输出纪律」写；不确定的标「待本人定」并说明原因。**本人说「帮我填」才代填**：`form_input` 填文本 / 下拉 / 单选；不上传文件、不勾自愿人口统计题、不点提交或 Next 以外的按钮。填完请本人核对。

**reach out**（按 `rules.md`「reach out」，判路 → 找人 → 写消息一口气做完，最后一起给本人看）：
1. 判路：找 HM 还是要 ref link，引卡片第 9 行与 JD 原文；JD 明写不 sponsor 先说一句。
2. 找人：新开 tab 用 LinkedIn 人员搜索（`linkedin.com/search/results/people/?keywords=<公司> <组级信号里的系统/团队名>`；要 ref link 就搜 `<公司> <相近职能>` 并留意你学校的校友），`get_page_text` 读结果，列出姓名 · 职位 · 主页链接。**不点 Connect / Message / Follow。** 找 HM 找不到具体的人 → 降为要 ref link，并说明。
3. 投递时机：一句话说明先拿 link 还是先投、为什么。
4. 写消息：每人一版，默认「还没投」措辞（本人说投过才写已投版）。存 `$ROOT/outreach/YYYY-MM-DD_公司_岗位.md`：收件人 · 渠道 · 正文；同一岗位多人写在同一个文件里。
5. 一次性给本人：判路结论 + 找到的人 + 投递时机 + 消息。发不发、什么时候发由本人定，不再追踪。

**问一下 X**：只写那一个问题的消息（收件人按问题定：签证 / 毕业窗口问 recruiter），存 `outreach/`，不带内推。

## 规则怎么改

见 `rules.md`「规则怎么改」。
