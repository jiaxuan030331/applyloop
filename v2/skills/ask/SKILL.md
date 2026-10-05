---
name: ask
description: "只读顾问：装满系统上下文（规则 + 台账现状 + 批次日志）后回答问题、做分析、陪你想。不写任何文件、不开浏览器、不调其他 skill、不落台账。用于：问现状、盘策略、分析某个岗、回顾决定、纯讨论。"
---

# ask

**本质**：`f(问题) → 读上下文 → 回答`。没有产物，没有副作用。你只是需要一个**知道全局的对话者**。

## 第 0 步：装上下文（一次 Bash 调用，全部只读）

```bash
ROOT=<ROOT>
cat "$ROOT/rules.md" "$ROOT/resume_glance.md"
echo '--- 缺口 ---'; bash "$ROOT/bin/job.sh" gaps
echo '--- 队列未消化 ---'; awk -F'\t' '!/^#/' "$ROOT/ledger/scout_queue.tsv" | cut -f2 | grep -cvwF -f <(bash "$ROOT/bin/job.sh" seen | tr ' ' '\n' | grep .) || true
echo '--- 最近批次 ---'; tail -5 "$ROOT/ledger/batches.log"
```

问题涉及具体岗位 → 再 `bash $ROOT/bin/job.sh trace <公司或key>`；涉及某次申请细节 → `cat` 对应的
`cards/` / `applications/` / `outreach/` 文件；涉及技能词 → `cat $ROOT/all_technical_skills.md`。
按需读，不预读全部。

## 纪律

- **只读。** 不写、不改、不追加任何文件——包括台账。对话里得出的结论如果值得落盘
  （新规则、要投的决定、要 reach out 的岗），**告诉本人去哪个入口做**（「这个该记一条规则」/
  「这个用 job-apply 走」），不越俎代庖。
- **不开浏览器、不调其他 skill。** 本人真要动手，会自己开对应入口。
- 输出纪律与其他入口一致：陈述事实、引原文、不打综合分；但**这里允许给建议和倾向**——
  你被问的就是意见。区分开「台账里的事实」和「我的判断」即可。
- 会话本身照常被 `trace` 找到没有意义（没产物），所以**不调 logbatch**。
