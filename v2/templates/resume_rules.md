# 简历规则 (resume_rules.md) — 模板

最后更新: <日期>

> `resume-tailor` 每次运行第一步读本文件 + `all_technical_skills.md`。求职判断规则在 `rules.md`。
> 只在你明确要求改简历时才读本文件。

## 在哪里干活

`$ROOT = <你的系统目录绝对路径>`，读、改、编译、渲染全部用 Bash 在本机完成。
需要：`xelatex` / `latexmk`（TeX 发行版）；预览 PNG 用 macOS 自带 `sips`（Linux 换 `pdftoppm`）。
**文件内容一个字节都不经过模型输出**：模型只输出命令和锚点。

## 前置：你的简历基线

- `resume/Resume_Full.tex` —— **素材库**（可以 2 页，不投递）。所有投递版都是它的子集 + 重排。
- `resume/Resume_<版本名>.tex` × N —— 投递版，每版一个定位（如 SDE / MLE / AI_Eng……版本名自定，
  但要同步改 `bin/job.sh` 和 `bin/audit.sh` 顶部的 VER 枚举）。基线**只读**，改动写成新文件。
- **Full 里每条 bullet 上方加 claim-boundary 注释**：`% level: used|extended|built|co-built · mine: <哪部分是你的> · story: <背景一句>`。
  取 bullet 进投递版时，动词层级不得高于 level——这是防止「润色着润色着就造假」的机制边界。

## 三级改法（L1 / L2 / L3）

| | 动哪里 | 句子来源 | 谁触发 |
|---|---|---|---|
| **L1 技能行** | 只动 `\skill{}` 行 | `all_technical_skills.md`（会的词才能加） | 入口 skill 建议，你说改 |
| **L2 结构** | `\item` 的选择/顺序/替换、整块挪动 | **只能是 Full 或该版基线的原句，逐字**（脚本核对） | 入口 skill 建议，你说改 |
| **L3 customize** | L2 之上改措辞，可动 tagline | Full 的**事实**重写成新句 | **只有你主动说**；先出「读 JD」解读，你认可才动 |

- L2 不改一个字，改了字就是 L3，`tailor_check.sh` 会拦。
- L1 写不下时：先在同生态位里**替换** JD 没点名的词，再考虑砍；砍 bullet 必须问你。
- 验收：`LEVEL=<1|2|3> bash bin/tailor_check.sh <工作目录> <版本>` —— 1 页、无 overfull、
  改动位置在该级白名单内、L2 新句逐字出自 Full。**PASS 才落盘。**

## 硬约束

- **不编造。** 事实、数字、时间、公司名、职称一律不动。
- **单页。** 编译后必须 1 page 且无 overfull/underfull，否则回退。
- **只做锚点替换**（python `assert s.count(old)==1` 再 replace），绝不重打整份 `.tex`。
- 改了任何基线 → 必须重生成 `resume_glance.md` 对应段 + 更新 `SHA256SUMS`，否则缺口分析静默出错。
