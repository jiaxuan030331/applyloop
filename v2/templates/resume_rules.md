# 简历规则 (resume_rules.md)

最后更新: <日期>（<一句话改了什么，出处 USER-日期>）

> `resume-tailor` 每次运行第一步读本文件 + `all_technical_skills.md`（选版本没定时再读 `resume_glance.md`）。
> 求职判断规则在 `rules.md`。本文件只在本人明确要求改简历时才读。

---

## 在哪里干活（决定了一切成本）

**本地 Claude Code（2026-09-20 起唯一运行环境）。** `$ROOT = <ROOT>`，读、改、编译、渲染全部用 Bash 工具在这台 Mac 完成。工具链实测（2026-09-20）：`xelatex` / `latexmk` 在 `/Library/TeX/texbin`；**没有 `pdftoppm`**，预览 PNG 用系统自带 `sips -s format png`。**文件内容一个字节都不经过模型输出**：只输出命令。

（此前的 Cowork device_bash 与 Drive 兜底两条路 2026-09-20 废弃；Drive `ng_application/` 只是历史备份，不再读写。）

**不碰的事**：不改 `resume/` 里的八份基线（只读）。

---

## 三级改法（L1 / L2 / L3）

| | L1 技能行 | L2 结构 | L3 customize |
|---|---|---|---|
| 动哪里 | 只动 `TECHNICAL SKILLS` 的 `\skill{}` 行 | `\item` 的**选择 / 顺序 / 替换**：加删项目或 bullet、重排、把某条换成 Full 里同一工作的另一视角；**整块挪动 / 删除项目或经历**（标题行 + itemize 随块走，`\firstentry`/`\entry` 可对调，标题文字不改；USER-2026-09-20） | 在 L2 之上**改措辞**：主语、动词、尾注指标、合并拆分；可动 `\tagline` |
| 句子来源 | `all_technical_skills.md` | **只能是 Full_v4 或该版基线里的原句，逐字**（脚本 ④ 核对） | Full 的**事实**（正文 + claim 注释里的 mine / story）重写成新句；本人新口述的经历先写进 Full 再用 |
| 谁触发 | 入口 skill 建议，本人说改 | 入口 skill 建议，本人说改 | 本人主动说「这个岗位做 L3」；或入口 skill 在组级信号具体（JD 写出具体系统/卡点/团队方向，非模板）**且** Full_v4 里有可点名的一条经历直接做过这件事、当前版本没放在前面时于卡片第 9 行提议、本人同意（USER-2026-10-04） |
| 前置产物 | 无 | 无 | **「读 JD」五行**（见下），本人认可后才动 .tex |
| 验收 | `LEVEL=1 tailor_check.sh` | `LEVEL=2` | `LEVEL=3`；真实性靠本人审 diff + 动词 ≤ claim level |

**L1 的两种豁免**（命中就别改，直说「不用改」）：JD 点名的词几乎已在技能行里；JD 是关键词罗列式、不指向具体系统。

**L1 写不下时：先替换，再考虑砍 bullet。**（USER-2026-09-17）技能行满了、单页塞不进新词时，优先在**同一行里替换掉 JD 没点名的词**，不要先去动 bullet。按这个顺序找被替换的词：

1. **同生态位优先。** 要加的词和某个现有词属于同一类（云厂商、容器编排、消息队列、测试框架、向量库、数据仓库…）时直接替换——类别覆盖不变，只是换成 JD 认的那个牌子。例：JD 只写 Azure 不写 AWS → `AWS` 换成 `Azure`；JD 写 `REST APIs` 不写 WebSocket → `REST/WebSocket` 换成 `REST APIs`。
2. **其次砍 JD 没点名、且同类里已有代表的词。** 如 Docker 与 Kubernetes 同属容器，JD 两个都不提时可只留一个。
3. **最后才砍 JD 没点名、同类里也没有代表的词。** 优先砍「默认假设」类（`Linux`、`Git` 这种谁都有、信息量低的），而不是有实质区分度的词。
4. 以上都不够 → 才回到 L2 砍 bullet，**且必须问本人砍哪条**，不自行决定。

替换只在**当次投递的那一份**里做，**不回写基线**——基线要保持对所有岗位的通用覆盖。替换后照常跑 `tailor_check.sh`（替换仍只动 `\skill{` 行，属 L1 白名单）。

**L2 是默认的「值得改」**：JD 指向的内容在该版排后面 / 没放 / Full 里有更对症的视角版本。做 L2 时不改任何一个字，改了就是 L3，脚本会拦。

**L3 的「读 JD」**（先出这个，等本人认可；写进 `applications/` 记录）：

1. 这个组做什么、产品什么阶段（从 about + responsibilities 推；标「推测」）
2. HM 最想看到证据的 2–3 件事——写成能力，不是关键词（「一个人能把训练 pipeline 从零跑起来并上线」而不是「PyTorch, Docker」）
3. 他们对新人的顾虑（只会调参不会上线 / 没碰过线上问题 / …）
4. 我这边的证据：Full 第几条 + 注释里哪句；这些证据在当前版本的位置（首条 / 没放 / 措辞方向不对）
5. 因此：tagline 往哪改、首两条换成什么、project 换哪个、措辞往哪拧
   **+ 一问**：「有没有 Full 里没写、但对这个组有用的经历？」本人答了 → 先按 claim 注释格式追加进 Full_v4（level / mine / TODO），重生成 `resume_glance.md` 素材段，再用。

JD 是大厂模板、读不出组级信息 → 直说「没信号」，退回 L2，不硬编解读。

**发现新技能**：本人说会某个清单里没有的词 → 先在本机追加到 `all_technical_skills.md`（对应分类末尾，`` `词` — USER-日期 ``，只增不删），再写进简历。

## 硬约束

- **不编造。** 事实、数字、时间、公司名、职称一律不动。
- **单页。** 编译后 `.log` 里必须是 1 page，且无 overfull / underfull；否则回退。
- **L1/L2 单次改动 ≤ 3–4 条 bullet；L3 不限条数，但每条改动都要在 diff 里能对回 Full 的事实。**
- **只做锚点替换。** Python 里 `assert s.count(old) == 1` 再 replace；不唯一就停下报错，不换锚点硬试。绝不凭上下文重打整份 `.tex`。
- **基线只读。** 所有改动写成新文件。

---

## 操作流程（本机）

一次 Bash 调用尽量做完一段；每次调用是新 shell，变量不延续，每个命令块自带 `ROOT=` 赋值。产物命名：`NAME=YYYY-MM-DD_公司_岗位_<版本>_L<1|2|3>`（版本用 SDE_ng / SDE_MLE_ng / SDE_AI_ng / FDE_ng / MLE_ng / AI_Eng / Speech_ng）。

```bash
ROOT=<ROOT>; NAME=$(date +%F)_公司_岗位_<版本>_L<1|2|3>
W=${TMPDIR:-/tmp}/rt/$NAME; mkdir -p $W          # 系统临时目录，aux 不进仓库
cp $ROOT/resume/Resume_<版本>.tex $W/edited.tex
```

改动用 python 读-改-写（LaTeX 转义：`%`→`\%`，`&`→`\&`，还有 `_ # $`）：

```bash
cd $W && python3 - <<'EOF'
s=open('edited.tex',encoding='utf-8').read()
for old,new in [(r'...', r'...')]:
    assert s.count(old)==1, f"anchor not unique: {s.count(old)}: {old[:60]}"
    s=s.replace(old,new)
open('edited.tex','w',encoding='utf-8').write(s)
EOF
diff -u $ROOT/resume/Resume_<版本>.tex edited.tex
```

编译 + 验收 + 落盘（一条命令）：

```bash
ROOT=<ROOT>; W=${TMPDIR:-/tmp}/rt/$NAME
cd $W && latexmk -xelatex -interaction=nonstopmode edited.tex >/dev/null 2>&1
LEVEL=<1|2|3> bash $ROOT/bin/tailor_check.sh $W <版本> && sips -s format png edited.pdf --out page-1.png >/dev/null && \
cp edited.pdf $ROOT/resumes/$NAME.pdf && cp edited.tex $ROOT/resumes/$NAME.tex && cp page-1.png $ROOT/resumes/_preview/$NAME.png && \
ls -la $ROOT/resumes/$NAME.pdf $ROOT/resumes/$NAME.tex
```

`tailor_check.sh` 按 `LEVEL` 验收，全过才打印 PASS：① `(1 page` ② 无 Overfull/Underfull ③ diff 改动行只在该级白名单内（L1 `\skill{`；L2 加 `\item`；L3 加 `\tagline`）④ L2 每条新 `\item` 逐字出自 Full 或基线；另打印改动 `\item` 行数（≤ 3–4 由本人/模型把关，脚本不拦）和 `BASE_SHA256`。FAIL → 少改一条重来，不落盘。最后的 `ls` 必须看到两个文件，否则不要回报「已落」。

写 `applications/` 记录（`resume-tailor` 第 3 步）：`resumes/$NAME.pdf` 文件名 + `BASE_SHA256`。PDF 丢了可以用 `resumes/$NAME.tex` 重编；`.tex` 也丢了，可以按 SHA 找回当时的基线再套 diff。

然后用 Read 工具读 `resumes/_preview/$NAME.png` 看一眼排版（一张图，低 DPI 够了）。

交付：对话里只给 `diff` 和一句「已落 `resumes/$NAME.pdf`」。本人要看就 `open` 那个 PDF。三级都这么落；记录由 `resume-tailor` 写进 `applications/`（版本 · 级别 · PDF · BASE_SHA256 · 改了什么），指向 `resumes/` 里的文件名。

`${TMPDIR:-/tmp}/rt/` 是系统临时目录，重启自动清。

---

## 改了基线之后

本人说「把这个改动存回基线」→ 用同样的锚点替换改 `resume/` 里那份，然后**必须**在本机重生成 `resume_glance.md` 对应段（观感 + 技能行），并更新 `resume/SHA256SUMS`，否则两个入口的缺口分析会静默出错。同时重编该版的 `resume/<版本>.pdf`（`latexmk -xelatex` 后 `cp` 回去）——这份 PDF 是本人不改简历时直接上传用的，agent 不读它。

---

## 待补充（本人填）

- 不想出现在简历上的内容：
- 必须保留、不许动的 bullet：
- 其他：
