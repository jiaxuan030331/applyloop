#!/usr/bin/env python3
"""邮箱回流：合并 subagent 判出的信号 → ledger/email_signals.tsv，出周报。规则见 rules.md「邮箱回流」。

  bin/inbox.py cursor              上次读到的最晚收信时间（周跑的 after: 起点）+ 已记线程数
  bin/inbox.py merge <run 目录>     收 run 目录下 w_*.tsv（缺列/错信号报错）→ 去重追加 signals；未匹配的真 MF 进 email_todo.md
  bin/inbox.py interviews          列 interview 信号与面试文件夹（mock_interview/actual_interviews）是否已开
  bin/inbox.py report [--since D]  统计：信号计数、按简历版本/来源的推进、带原因的拒信、待办 → 打印并写 inbox_reports/<今天>.md

signals 列：received_at · thread_id · company · title · job_key · signal(rej|screen-rej|oa|oa-auto|interview) · reason · applied_at · evidence · channel(经过，自由文本)
"""
import collections
import datetime as dt
import glob
import os
import sys

ROOT = os.environ.get("INBOX_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIG = os.path.join(ROOT, "ledger", "email_signals.tsv")
TODO = os.path.join(ROOT, "ledger", "email_todo.md")
COLS = ["received_at", "thread_id", "company", "title", "job_key", "signal", "reason", "applied_at", "evidence", "channel"]
KINDS = ("rej", "screen-rej", "oa", "oa-auto", "interview")


def rows():
    if not os.path.exists(SIG):
        return []
    return [dict(zip(COLS, l.rstrip("\n").split("\t"))) for l in open(SIG) if l.strip() and not l.startswith(("#", "received_at"))]


def cursor():
    r = rows()
    print(f"已记 {len(r)} 行 / {len({x['thread_id'] for x in r})} 个线程")
    print("LAST " + (max(x["received_at"] for x in r)[:10] if r else "2026-09-10"))


def merge(run):
    have = {(x["thread_id"], x["signal"], x["title"]) for x in rows()}   # 同一线程可能装多个岗位（NVIDIA 两岗一封）
    new, bad = [], []
    for f in sorted(glob.glob(os.path.join(run, "w_*.tsv"))):
        for i, l in enumerate(open(f), 1):
            if not l.strip() or l.startswith(("#", "received_at")):
                continue
            p = l.rstrip("\n").split("\t")
            if len(p) != len(COLS) or p[5] not in KINDS:
                bad.append(f"{os.path.basename(f)}:{i} 列数 {len(p)} / 信号 {p[5] if len(p) > 5 else '?'}")
                continue
            if (p[1], p[5], p[3]) not in have:
                have.add((p[1], p[5], p[3]))
                new.append(p)
    if bad:
        sys.exit("MERGE FAIL——这些行格式不对，修好或重跑对应窗口：\n  " + "\n  ".join(bad[:20]))
    first = not os.path.exists(SIG)
    with open(SIG, "a") as fh:
        if first:
            fh.write("\t".join(COLS) + "\n")
        for p in sorted(new):
            fh.write("\t".join(x.replace("\t", " ") for x in p) + "\n")
    todo = [p for p in new if p[4] in ("", "-") and p[5] in ("oa", "interview")]
    if todo:
        with open(TODO, "a") as fh:
            if os.path.getsize(TODO) == 0:
                fh.write("# 邮箱里真 move forward、但台账查不到的岗位——本人补 JD 后走 /job-apply 出卡\n\n")
            for p in todo:
                fh.write(f"- [ ] {p[0][:10]} · {p[2]} · {p[3] or '岗位未知'} · {p[5]} — {p[8][:80]}\n")
    c = collections.Counter(p[5] for p in new)
    print(f"新增 {len(new)} 行 {dict(c)} · 进待办 {len(todo)}")


# 方向：按岗位名归类（顺序即优先级）。用来看「什么方向有推进 / 慢拒集中在哪」，不是精确分类。
DIRS = [("quant", r"quant|trader|trading|market making"),
        ("FDE / solutions", r"forward deployed|\bfde\b|solutions?|implementation|customer"),
        ("research", r"research"),
        ("DS", r"data scien|analytics|\banalyst"),
        ("AI / LLM", r"\bai\b|llm|genai|agent|applied ai"),
        ("ML", r"machine learning|\bml\b|\bmle\b|deep learning|vision|nlp|算法"),
        ("SWE", r".")]


def direction(title):
    import re
    for name, pat in DIRS:
        if re.search(pat, title or "", re.I):
            return name
    return "SWE"


def first_seen():
    d = {}
    for i, l in enumerate(open(os.path.join(ROOT, "ledger", "jobs.tsv"))):
        f = l.rstrip("\n").split("\t")
        if i and len(f) > 2:
            d.setdefault(f[2], f[0])
    return d


def report(since):
    r = [x for x in rows() if x["received_at"][:10] >= since]
    fs = first_seen()

    def lag(x):  # 收信距申请的天数：确认信时间优先，否则台账首行日期（按天）
        a = x["applied_at"][:10] if x["applied_at"] not in ("", "-") else fs.get(x["job_key"])
        if not a:
            return None
        return (dt.date.fromisoformat(x["received_at"][:10]) - dt.date.fromisoformat(a)).days

    out = [f"# 邮箱回流 {dt.date.today()}（收信 ≥ {since}）", ""]
    c = collections.Counter(x["signal"] for x in r)
    mf = c["oa"] + c["interview"]
    out += [f"推进 **{mf}**（真 OA {c['oa']} · 面试 {c['interview']}）· 过筛被拒 {c['screen-rej']} · 拒信 {c['rej']} · 自动 OA {c['oa-auto']}", ""]

    out += ["## 正面（逐条，保留经过）", ""]
    pos = [x for x in r if x["signal"] in ("oa", "interview", "screen-rej")]
    for x in sorted(pos, key=lambda x: x["received_at"]):
        stage = {"oa": "OA", "interview": "面试 / 约聊", "screen-rej": "过了简历筛、被硬条件拒"}[x["signal"]]
        extra = "；".join(t for t in (x["reason"], x.get("channel", "")) if t not in ("", "-"))
        out.append(f"- {x['received_at'][:10]} · **{x['company']}** · {x['title'] or '?'} · 方向 {direction(x['title'])} · {stage}" + (f" —— {extra}" if extra else ""))
    if not pos:
        out.append("- 无")

    # 每岗取最好一档，按方向统计；拒信拆快（≤2 天，多为自动筛）/ 慢（>2 天）/ 不知道申请时间
    rank = {"interview": 4, "oa": 3, "screen-rej": 2, "oa-auto": 1, "rej": 0}
    best = {}
    for x in r:
        k = x["job_key"] if x["job_key"] not in ("", "-") else "?" + x["company"] + "|" + x["title"]
        if k not in best or rank[x["signal"]] > rank[best[k]["signal"]]:
            best[k] = x
    g = collections.defaultdict(collections.Counter)
    for x in best.values():
        d = direction(x["title"])
        if x["signal"] == "rej":
            L = lag(x)
            g[d]["快拒" if L is not None and L <= 2 else "慢拒" if L is not None else "拒(时间未知)"] += 1
        else:
            g[d][x["signal"]] += 1
    out += ["", "## 按方向（每岗取最好一档；快拒 = 申请后 ≤2 天，多为自动筛，不说明方向）", "",
            "| 方向 | 有回音 | 推进 | 过筛被拒 | 慢拒 | 快拒 | 拒(时间未知) | 自动OA |", "|---|---|---|---|---|---|---|---|"]
    for d, cc in sorted(g.items(), key=lambda t: -sum(t[1].values())):
        out.append(f"| {d} | {sum(cc.values())} | {cc['oa'] + cc['interview']} | {cc['screen-rej']} | {cc['慢拒']} | {cc['快拒']} | {cc['拒(时间未知)']} | {cc['oa-auto']} |")

    rs = [x for x in r if x["signal"] in ("rej", "screen-rej") and x["reason"] not in ("", "-")]
    out += ["", "## 有内容的拒信", ""] + ([f"- {x['company']} · {x['title'] or '?'} · 方向 {direction(x['title'])} — {x['reason']}" for x in rs] or ["- 无"])
    if os.path.exists(TODO):
        open_todo = [l.rstrip() for l in open(TODO) if l.startswith("- [ ]")]
        out += ["", f"## 待办（{len(open_todo)} 条）", ""] + (open_todo or ["- 无"])
    text = "\n".join(out) + "\n"
    d = os.path.join(ROOT, "ledger", "inbox_reports")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, f"{dt.date.today()}.md"), "w").write(text)
    print(text)


MOCK = os.path.join(os.environ.get("INTERVIEW_HUB") or os.path.join(os.path.dirname(ROOT), "mock_interview"), "actual_interviews")


def interviews():
    import re
    have = os.listdir(MOCK) if os.path.isdir(MOCK) else []
    norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
    seen = set()
    for x in rows():
        if x["signal"] != "interview" or (x["company"], x["title"]) in seen:
            continue
        seen.add((x["company"], x["title"]))
        hit = [d for d in have if norm(x["company"])[:6] in norm(d)]
        print(f"{'有' if hit else '无'}\t{x['received_at'][:10]}\t{x['company']}\t{x['title']}\t{x['job_key']}\t{x['thread_id']}\t{hit[0] if hit else '-'}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "cursor":
        cursor()
    elif a[0] == "interviews":
        interviews()
    elif a[0] == "merge":
        merge(a[1])
    elif a[0] == "report":
        report(a[a.index("--since") + 1] if "--since" in a else "2026-09-10")
    else:
        sys.exit(__doc__)
