---
name: resume-tailor
description: "改简历，分三级：L1 补 technical skills 行；L2 只动 bullet 的选择/顺序/替换（原句取自 Full，不改字）；L3 customize 改措辞（本人主动触发，先出「读 JD」解读）。本机 VM 编译验收后落 resumes/。只在本人明确要求改简历时调用。"
---

# resume-tailor

**本质**：`f(版本, 级别 L1|L2|L3, 改动清单) → 本机 resumes/ 里一份 PDF + .tex + 对话里一段 diff + 回报 (文件名, BASE_SHA256)`；**被本人直接调用时还要补一份 `applications/` stub**（见第 3 步），否则这次改动没有任何人记录。被 `saved-jobs-triage` / `job-apply` 指出「该用哪版、建议 L1 还是 L2」之后，本人明确说「改」才调用；**L3 只由本人主动说「这个岗位做 L3 / customize」才走**。一次只改一份、对一个职位。

## 三级（定义以本机 `resume_rules.md`「三级改法」为准）

| | 动哪里 | 句子来源 | 谁触发 |
|---|---|---|---|
| **L1 技能行** | 只 `\skill{}` 行 | `all_technical_skills.md` | 入口建议，本人说改 |
| **L2 结构** | `\item` 的选择 / 顺序 / 替换（加删项目或 bullet、重排、换成 Full 里同一工作的另一视角） | **Full 或该版基线的原句，逐字**；脚本核对 | 入口建议，本人说改 |
| **L3 customize** | L2 之上改措辞（主语 / 动词 / 尾注指标 / 合并拆分），可动 `\tagline` | Full 的**事实**（正文 + claim 注释 mine / story）重写；本人新口述的经历先进 Full | **只有本人**；先出「读 JD」，认可后才动 .tex |

L2 不改一个字，改了字就是 L3，脚本会拦。入口 skill 只会在卡里标「组级信号」，不会替本人决定做 L3。

## 原则

- **不编造。** 事实、数字、时间、公司名、职称不动；L3 重写的每一句都要能对回 Full 的正文或 claim 注释，动词层级不高于注释里的 `level`（used→configured/tuned；extended→extended/adapted/wired；built→built/implemented；co-built→co-developed + 写清 mine）。
- **字节不经模型。** 读、改、编译、渲染全在本机（Bash 工具）；模型只输出命令和锚点。
- **锚点替换，`count==1`。** 不唯一就停下问，不换锚点硬试；绝不重打整份 `.tex`。重排时把整个 `\begin{itemize}…\end{itemize}` 块当一个锚点整体替换，每个 `\item` 独占一行。
- **单页硬约束。** L1/L2 改动 ≤ 3–4 条 bullet；L3 不限条数但逐条可溯源。验收由 `bin/tailor_check.sh` 按 LEVEL 判，不靠目测。
- **产物落本机，不进对话。** 对话只给 diff 和文件名；本人要看再 `open` PDF。

## 第 0 步：读规则（一次 Bash 调用；本会话已读过的文件不重读）

```bash
ROOT=<ROOT>
cat "$ROOT/resume_rules.md" "$ROOT/all_technical_skills.md"
```

调用方没传版本就再 `cat $ROOT/resume_glance.md`。L3 还要 `cat $ROOT/resume/Resume_Full.tex`（要读 claim 注释，这是唯一允许读 `.tex` 正文进模型的情况）。文件全在本地，没有 Drive 兜底。

**本地工具链（2026-09-20 实测）**：`xelatex` / `latexmk` 在 `/Library/TeX/texbin`（PATH 里有）；**没有 `pdftoppm`**——预览 PNG 用系统自带 `sips -s format png edited.pdf --out page-1.png`（只出第一页，低 DPI，够看排版）。工作目录用 `W=${TMPDIR:-/tmp}/rt/$NAME`（aux 不进仓库）。

## 第 1 步：定级

| 判定 | 级 |
|---|---|
| JD 点名的词几乎已在该版技能行 / JD 关键词罗列式 | **豁免**：说「不用改」，回报基线文件名 + `sha256sum`，结束 |
| 有会但没写的词（`all_technical_skills.md` 里有） | **L1** |
| JD 指向的内容在该版排后面 / 没放 / Full 里有更对症的视角版本 | **L2**（可同时做 L1） |
| 本人明确说「这个岗位做 L3」 | **L3**（含 L1/L2） |

本人提到清单里没有的技能 → 先追加到 `all_technical_skills.md`（只增不删、写出处），再用。不确定 L1 还是 L2 就问，不替本人定；**没被本人点名绝不升到 L3**。

## L3 专属：先「读 JD」，等认可

出五行（格式在 `resume_rules.md`），然后停：

1. 这个组做什么、产品什么阶段（标「推测」）
2. HM 最想看到证据的 2–3 件事——写成能力，不是关键词
3. 他们对新人的顾虑
4. 我这边的证据：Full 第几条 + 注释里哪句；在当前版本的位置
5. 因此：tagline 往哪改、首两条换成什么、project 换哪个、措辞往哪拧

**并问一句**：「有没有 Full 里没写、但对这个组有用的经历？」本人答了 → 用 claim 注释格式追加进 Full（`% level: … · mine: … · TODO: …` + `\item`），重生成 `resume_glance.md` 素材段，更新 `SHA256SUMS`，再用。JD 是模板、读不出组级信息 → 直说「没信号」，建议退回 L2。

本人认可（或改过）解读后才进第 2 步。解读原文由 `job-apply` 写进 `applications/` 记录。

## 第 2 步：改 + 编译 + 验收 + 落盘（两次 Bash 调用）

**第一次**：`NAME=日期_公司_岗位_版本_L<级>`，在 `${TMPDIR:-/tmp}/rt/$NAME/` 里 `cp` 基线为 `edited.tex`，python 锚点替换（每个 `assert s.count(old)==1`），`diff -u` 打出来。

**第二次**（模板在 `resume_rules.md`「操作流程」）：

```bash
ROOT=<ROOT>; W=${TMPDIR:-/tmp}/rt/$NAME
cd $W && latexmk -xelatex -interaction=nonstopmode edited.tex >/dev/null 2>&1
LEVEL=<1|2|3> bash $ROOT/bin/tailor_check.sh $W <版本> && sips -s format png edited.pdf --out page-1.png >/dev/null && \
cp edited.pdf $ROOT/resumes/$NAME.pdf && cp edited.tex $ROOT/resumes/$NAME.tex && cp page-1.png $ROOT/resumes/_preview/$NAME.png && \
ls -la $ROOT/resumes/$NAME.pdf $ROOT/resumes/$NAME.tex
```

脚本打印 PASS 才落盘：① 1 页 ② 无 Overfull/Underfull ③ 改动位置符合该级白名单 ④ L2 每条新 `\item` 逐字出自 Full 或基线；并打印改动 `\item` 行数（≤ 3–4 由你把关，脚本不拦）和 `BASE_SHA256`。FAIL → 少改一条或降级重来。`ls` 看不到两个文件不回报「已落」。**`NAME` 必须带 `_L<级>` 后缀且 PDF/.tex 成对**——`job-apply` 写记录前会 `test -e` PDF。

## 第 3 步：看一眼 + 交付

用 Read 工具直接读 `resumes/_preview/$NAME.png` 看排版没坏。对话里只说「已落 `resumes/$NAME.pdf`（L<级>）」。**回报给调用方**：文件名 + `BASE_SHA256`（+ L3 的解读原文），`job-apply` 写记录要用。

**被 `job-apply` 调用**：到此为止，记录由它写（完整版，含申请表问答）。

**被本人直接调用**：`job-apply` 不在场，没人写记录——2026-09-20 对账发现 52 份简历产物没有对应记录，全是这条路来的。所以同一次 Bash 调用里补一份最小 stub（`STEM` = `NAME` 去掉 `_<版本>[_L<级>]` 后缀，与 `bin/audit.sh` 的对账规则一致；**已存在就不覆盖**，日后 `job-apply` 写完整记录时才覆盖它）：

```bash
STEM=$(printf %s "$NAME" | sed -E 's/_(SDE_ng|SDE_MLE_ng|SDE_AI_ng|FDE_ng|MLE_ng|AI_Eng)(_L[123])?$//')
test -e "$ROOT/applications/$STEM.md" || cat > "$ROOT/applications/$STEM.md" <<EOF
# <公司> · <岗位> — 简历已改，投递状态未知

- 来源：本人直接调用 resume-tailor（非 job-apply 流程），$(date +%F)
- 版本 / 级别：<版本> · L<级>
- PDF：\`resumes/$NAME.pdf\`（.tex 同名）
- BASE_SHA256：\`<基线校验和>\`
- 改了什么：<逐条，L2 注明取自 Full 哪条；L3 附「读 JD」解读>
- **台账：这条路不落 \`jobs.tsv\`，投了要自己补一行，或下次「盘点」时补。**
EOF
```

写完提醒一句：「这份是直接调用，台账没有对应行——投了记得说一声」。

## 不做的事

- 不代替本人提交申请。
- 不动 `resume/` 七份基线（Full + 六份投递版：SDE_ng / SDE_MLE_ng / SDE_AI_ng / FDE_ng / MLE_ng / AI_Eng），除本人说「存回基线」或 L3 追加口述经历进 Full（按 `resume_rules.md`「改了基线之后」：重生成 `resume_glance.md` + 更新 `SHA256SUMS` + 重编该版 `resume/*.pdf`）。
- 不主动删本机文件；本人要求删时先请求删除权限再删。
- 不在本人没要求时改简历；不在本人没点名时做 L3。

## 规则怎么改

本人说「记一条规则」：改简历方法 → `resume_rules.md`；新会的技术 → `all_technical_skills.md`；求职判断 → `rules.md`。本机 python 读-改-写原地改，更新顶部日期，复述改了什么。