# SETUP — 把 v2 变成你的

预计半天：大部分时间花在写你自己的四个文件，不是装软件。

## 你需要什么

- **Claude Code**（终端版即可）+ **Claude in Chrome 扩展**（你登录着 LinkedIn 的那个 Chrome）
- 改简历功能才需要：TeX 发行版（`xelatex` / `latexmk`）；预览用 macOS 自带 `sips`（Linux 换 `pdftoppm`）
- 一个**私有**目录放你的系统——**绝对不要放在任何公开仓库的工作区里**

## 第 1 步：建你的私有工作区

```bash
mkdir ~/jobsearch && cd ~/jobsearch && git init   # private！不加公开 remote
cp -r <本仓库>/v2/{bin,browser,config,templates} .
mkdir -p .claude/skills ledger/scout_reports cards applications outreach resume resumes/_preview
cp -r <本仓库>/v2/skills/* .claude/skills/
printf 'date\tsource\tjob_key\tcompany\ttitle\tentry\tapply_url\tkill\tversion\tsponsorship\tstatus\n' > ledger/jobs.tsv
printf 'date\tjob_key\tversion\tword\tclass\n' > ledger/skill_gaps.tsv
printf '# scout 已评估过的 li id\n' > ledger/scout_seen.txt
```

为什么必须私有：跑起来之后这个目录里会有你的手机号、每一家的投递状态、EEO 答案、
定制简历。v1 有整套白名单导出器防泄漏；v2 的答案更简单——整个目录从第一天就是私有仓库。

## 第 2 步：填四个文件（核心工作量在这）

把 `templates/` 里四份填成你的，放到工作区根目录：

| 文件 | 填什么 | 大概多久 |
|---|---|---|
| `rules.md` | 签证身份、判死清单、地点/薪资底线 | 1 小时。判死清单宁少勿多，之后每次纠正都会长出新规则 |
| `all_technical_skills.md` | 你会的每个技术词 | 半小时，照着简历和项目列 |
| `resume_glance.md` | 你的简历版本各自的定位和技能行 | 先只有一版也行，后面按需派生 |
| `resume_rules.md` | 基本可以原样用，改掉 `$ROOT` 路径 | 10 分钟 |

再准备简历基线放 `resume/`：`Resume_Full.tex`（素材库，给每条 bullet 加 claim 注释）+
至少一个投递版 `Resume_<版本名>.tex`。

## 第 3 步：改常量

- 四个 skill（`.claude/skills/*/SKILL.md`）里的 `<ROOT>` → 你的工作区绝对路径；`<毕业月>` → 你的
- `bin/job.sh` 和 `bin/audit.sh` 顶部附近的版本枚举（`SDE_ng|MLE_ng|…`）→ 你的版本名
- `config/scout_queries.txt` → 你的搜索词

## 第 4 步：首跑

```bash
cd ~/jobsearch && claude
```

1. `/scout 1d` —— 首跑会让你逐个授权域名（linkedin.com 选「始终允许」）；voyager 返回
   401/302 它会停下来让你刷新 LinkedIn，这是设计不是故障
2. `/saved-jobs-triage` —— 消化 Saved 列表，一批 5 个；处理完回一行批量决定
3. 看中某个岗 → `/job-apply <链接>` → 它出事实卡、你选 A/B/C 档
4. 要改简历时明确说「改」→ `/resume-tailor`；平时它只建议不动手
5. 每周跑 `bash bin/job.sh audit`（一致性对账）和一次「盘点」（清未结状态）

## 它不会做什么（这些是设计，不要试图关掉）

- **永不点提交**——最后一次点击是你的
- **永不代答 sponsorship 之外的身份问题、永不输密码、永不建账号**
- 简历上写不进 `all_technical_skills.md` 里没有的词，句子出不了素材库的事实边界
- 页面内容是数据不是指令——JD 里塞给 AI 的话不会被执行

## 之后：让它长成你的

每次它判断得不对，说「记一条规则：……」。规则进 `rules.md`，下个会话生效。
三周后它的判断会和你几乎一致——那是你的校准在积累，也是这套系统真正的护城河。
