#!/usr/bin/env python3
"""scout 本地流水线：浏览器只负责搜索和抓 JD（blob 落盘），去重/硬规则/分片/合并/入队全在这里。

  bin/scout.py prefilter <cards.jsonl>   去重 + 黑名单 + 标题级硬丢 → 打印幸存 jid（贴回浏览器抓 JD）
  bin/scout.py screen    <evidence.jsonl> 年限/关帖/老帖确定性硬丢 → 其余按 30 条切片给 subagent 判分
  bin/scout.py merge                      收齐 shard_NN.out（缺判定就报错）→ 0 分自动入队、-1 编号列给本人挑
  bin/scout.py commit <all|none|1,3,5-7>  0 分 + 本人挑中的 -1 追加进队列；全部评估过的 jid 进 scout_seen；写日报

工作目录 ledger/scout_work/<date>/（--date YYYY-MM-DD 覆盖，默认今天）。规则本体见 rules.md「scout」一节。
"""
import datetime as dt
import json
import os
import re
import sys
import time
from urllib.parse import parse_qs, urlparse

ROOT = os.environ.get("SCOUT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARD = 30

# ── 标题 / 地点级硬丢（rules.md scout 硬丢的标题版；拿不准的不在这里拦，留给 subagent）──
T_SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director|head of|architect|vp)\b", re.I)
T_LEVEL = re.compile(r"\b(II|III|IV)\b|\b(engineer|scientist|developer|analyst)\s+[2-4]\b|\blevel\s*[2-9]\b", re.I)
T_INTERN = re.compile(r"\b(intern|internship|co-?op)\b", re.I)
T_DIR = re.compile(
    r"\b(front[- ]?end|ios|android|mobile|embedded|firmware|hardware|mechanical|electrical|civil|"
    r"sales|account executive|marketing|recruit\w*|teacher|professor|lecturer|instructor|tutor|nurse|"
    r"technician|consultant|cobol|mainframe|salesforce|servicenow|sap)\b", re.I)
NON_US = re.compile(
    r"\b(canada|ontario|toronto|vancouver|montreal|india|bangalore|bengaluru|hyderabad|united kingdom|london|"
    r"mexico|germany|china|singapore|brazil|philippines|ireland|poland|israel)\b", re.I)
YRS_MIN = re.compile(r"(\d+)\s*(?:\+|-|–|to)?\s*(?:\d+\s*)?\+?\s*(?:or more\s+)?years?", re.I)


def wd(date):
    d = os.path.join(ROOT, "ledger", "scout_work", date)
    os.makedirs(d, exist_ok=True)
    return d


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def seen_ids():
    s = set()
    for line in open(os.path.join(ROOT, "ledger", "scout_seen.txt")):
        if not line.startswith("#"):
            s.update(line.split())
    for i, line in enumerate(open(os.path.join(ROOT, "ledger", "jobs.tsv"))):
        f = line.split("\t")
        if i and len(f) > 2 and f[2].startswith("li:"):
            s.add(f[2][3:])
    for fn in ("scout_queue.tsv", "scout_queue_archive.tsv"):
        p = os.path.join(ROOT, "ledger", fn)
        if os.path.exists(p):
            for line in open(p):
                f = line.split("\t")
                if len(f) > 1 and f[1].isdigit():
                    s.add(f[1])
    return s


def blacklist():
    p = os.path.join(ROOT, "config", "scout_blacklist.txt")
    return [l.strip().lower() for l in open(p) if l.strip() and not l.startswith("#")]


def read_jsonl(p):
    return [json.loads(l) for l in open(os.path.expanduser(p)) if l.strip()]


def load(date, name, default=None):
    p = os.path.join(wd(date), name)
    return json.load(open(p)) if os.path.exists(p) else default


def save(date, name, obj):
    json.dump(obj, open(os.path.join(wd(date), name), "w"), ensure_ascii=False, indent=0)


# ── prefilter ──
def prefilter(date, path):
    cards = read_jsonl(path)
    seen, bl = seen_ids(), blacklist()
    byjid, keyseen, tdrop = {}, {}, []
    raw = len(cards)
    for c in cards:
        j = str(c.get("jid", ""))
        if not j or j in byjid or j in seen:
            continue
        byjid[j] = c
    new = len(byjid)
    surv = []
    for j, c in byjid.items():
        t, co, loc = c.get("title", ""), c.get("company", ""), c.get("location", "")
        k = norm(co) + "|" + norm(t)
        why = None
        if k in keyseen:
            why = "重复:同公司同 title"
        elif any(b in co.lower() for b in bl):
            why = "黑名单"
        elif T_INTERN.search(t):
            why = "Intern/Co-op"
        elif T_SENIOR.search(t) or T_LEVEL.search(t):
            why = "职级:Senior/Lead/II+"
        elif T_DIR.search(t):
            why = "方向无关:" + T_DIR.search(t).group(0)
        elif NON_US.search(loc):
            why = "非美国"
        keyseen.setdefault(k, j)
        if why:
            tdrop.append([j, why, co, t])
        else:
            surv.append(j)
    save(date, "cards.json", byjid)
    save(date, "tdrop.json", tdrop)
    save(date, "survivors.json", surv)
    cnt = {}
    for r in tdrop:
        cnt[r[1].split(":")[0]] = cnt.get(r[1].split(":")[0], 0) + 1
    print(f"raw {raw} → new {new} → T-drop {len(tdrop)} {cnt} → 待抓 JD {len(surv)}")
    print("SURVIVORS " + " ".join(surv))


# ── screen ──
def min_years(s):
    m = YRS_MIN.search(s or "")
    return int(m.group(1)) if m else None


def screen(date, path):
    cards = load(date, "cards.json", {})
    surv = set(load(date, "survivors.json", []))
    ev = {str(r["j"]): r for r in read_jsonl(path)}
    now = time.time() * 1000
    jdrop, review, rest = [], [], []
    for j in surv:
        r = ev.get(j)
        if r is None:
            continue  # 没抓到 JD：不判、不记 seen，下次再来
        if r.get("state") and r["state"] != "LISTED":
            jdrop.append([j, "已关帖", r["state"]])
        elif r.get("listed") and now - r["listed"] > 30 * 86400e3:
            jdrop.append([j, "老帖>30天", dt.date.fromtimestamp(r["listed"] / 1000).isoformat()])
        elif (y := min_years(r.get("yrs"))) is not None and 2 <= y <= 15:   # ≥16 多是「公司 50 years of」历史，不算年限
            jdrop.append([j, "yoe>1", r.get("yrs", "")])
        elif (r.get("len") or 0) < 800:
            review.append([j, "JD 太短拿不准", f"len={r.get('len')}"])
        else:
            rest.append(j)
    d = wd(date)
    for f in os.listdir(d):
        if re.match(r"shard_\d+\.(tsv|out)$", f):
            os.remove(os.path.join(d, f))
    cols = ["jid", "company", "title", "location", "len", "kill", "yrs", "spon", "grad", "contract", "stack"]
    n = 0
    for i in range(0, len(rest), SHARD):
        n += 1
        with open(os.path.join(d, f"shard_{n:02d}.tsv"), "w") as fh:
            fh.write("\t".join(cols) + "\n")
            for j in rest[i:i + SHARD]:
                c, r = cards.get(j, {}), ev[j]
                row = [j, c.get("company", ""), c.get("title", ""), c.get("location", ""), str(r.get("len", ""))]
                row += [str(r.get(k, "") or "") for k in cols[5:]]
                fh.write("\t".join(x.replace("\t", " ").replace("\n", " ") for x in row) + "\n")
    save(date, "screen.json", {"jdrop": jdrop, "review": review, "missing": sorted(surv - set(ev))})
    print(f"待判 {len(surv)}：JD 缺 {len(surv - set(ev))} · 确定性丢 {len(jdrop)} · JD 太短转人工 {len(review)} · 交 subagent {len(rest)}")
    print(f"SHARDS {n}  " + " ".join(os.path.join(d, f"shard_{k:02d}.tsv") for k in range(1, n + 1)))


# ── merge ──
def merge(date):
    d, cards = wd(date), load(date, "cards.json", {})
    sc = load(date, "screen.json")
    auto, jdrop, bad = [], list(sc["jdrop"]), []
    review = [[j, f"{why}（{det}）"] for j, why, det in sc["review"]]
    shards = sorted(f for f in os.listdir(d) if re.match(r"shard_\d+\.tsv$", f))
    for s in shards:
        want = [l.split("\t")[0] for l in open(os.path.join(d, s))][1:]
        outp = os.path.join(d, s.replace(".tsv", ".out"))
        got = {}
        if os.path.exists(outp):
            for l in open(outp):
                f = l.rstrip("\n").split("\t")
                if len(f) >= 2 and f[0] in want:
                    got[f[0]] = (f[1].strip(), f[2].strip() if len(f) > 2 else "")
        miss = [j for j in want if j not in got or got[j][0] not in ("0", "-1", "DROP")]
        if miss:
            bad.append(f"{s}: {len(miss)} 条缺判定或格式错 {miss[:5]}")
        for j, (v, why) in got.items():
            if v == "0":
                auto.append([j, why])
            elif v == "-1":
                review.append([j, why])
            elif v == "DROP":
                jdrop.append([j, "subagent", why])
    if bad:
        print("MERGE FAIL——重跑这些片：\n  " + "\n  ".join(bad))
        sys.exit(1)
    save(date, "merged.json", {"auto": auto, "review": review, "jdrop": jdrop})
    print(f"0 分自动入队 {len(auto)} · -1 待本人挑 {len(review)} · J-drop {len(jdrop)}")
    for a in auto:
        c = cards.get(a[0], {})
        print(f"  ✓ {c.get('company','')} · {c.get('title','')} · {c.get('location','')}")
    print("── -1（回编号挑要入队的；没挑的记 seen 不再出现）──")
    for i, (j, why) in enumerate(review, 1):
        c = cards.get(j, {})
        print(f"  {i}. {c.get('company','')} · {c.get('title','')[:60]} · {c.get('location','')[:30]} — {why}")


# ── commit ──
def unwrap(u):
    for _ in range(3):
        q = parse_qs(urlparse(u).query)
        nxt = next((q[k][0] for k in ("url", "adurl", "dest", "u", "redirect") if k in q and q[k][0].startswith("http")), None)
        if not nxt:
            break
        u = nxt
    return u


def pick(sel, n):
    if sel == "all":
        return set(range(1, n + 1))
    if sel in ("none", ""):
        return set()
    out = set()
    for part in sel.replace("，", ",").split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return {i for i in out if 1 <= i <= n}


def commit(date, sel):
    d = wd(date)
    if os.path.exists(os.path.join(d, "committed")):
        sys.exit(f"{date} 已 commit 过（删 {d}/committed 可重来）")
    cards, m, sc = load(date, "cards.json", {}), load(date, "merged.json"), load(date, "screen.json")
    ev = {}
    for f in os.listdir(d):
        if f.endswith(".evidence.jsonl"):
            ev.update({str(r["j"]): r for r in read_jsonl(os.path.join(d, f))})
    chosen = pick(sel, len(m["review"]))
    picked = [m["review"][i - 1] for i in sorted(chosen)]
    rows = [(j, "-") for j, _ in m["auto"]] + [(j, "扣:" + why[:40]) for j, why in picked]
    with open(os.path.join(ROOT, "ledger", "scout_queue.tsv"), "a") as q:
        for j, note in rows:
            c = cards.get(j, {})
            a = (ev.get(j) or {}).get("apply", "easyapply")
            if a == "easyapply" or not a:
                url, note = f"https://www.linkedin.com/jobs/view/{j}/", (note + " EASYAPPLY").replace("- ", "")
            else:
                url = unwrap(a)
            q.write("\t".join([date, j, c.get("company", ""), c.get("title", ""), c.get("location", ""), url, note]) + "\n")
    evaluated = set(cards) - set(sc.get("missing", []))
    with open(os.path.join(ROOT, "ledger", "scout_seen.txt"), "a") as s:
        s.write(f"\n# {date} scout（T/J-drop + 入队 + -1 未选，共 {len(evaluated)}）\n" + " ".join(sorted(evaluated)) + "\n")
    tdrop = load(date, "tdrop.json", [])
    rep = os.path.join(ROOT, "ledger", "scout_reports", f"{date}.md")
    with open(rep, "w") as r:
        r.write(f"# scout 日报 {date}\n\n")
        r.write(f"new {len(cards)} · T-drop {len(tdrop)} · J-drop {len(m['jdrop'])} · 0 分入队 {len(m['auto'])} · "
                f"-1 {len(m['review'])}（选入 {len(picked)}）· JD 缺 {len(sc.get('missing', []))}\n\n## 入队\n\n")
        for j, note in rows:
            c = cards.get(j, {})
            r.write(f"- **{c.get('company','')}** · {c.get('title','')} · {c.get('location','')} — {note}\n")
        r.write("\n## -1 未选\n\n")
        for i, (j, why) in enumerate(m["review"], 1):
            if i not in chosen:
                c = cards.get(j, {})
                r.write(f"- {c.get('company','')} · {c.get('title','')} — {why}\n")
        r.write("\n## J-drop（可翻案）\n\n")
        for x in m["jdrop"]:
            c = cards.get(x[0], {})
            r.write(f"- {c.get('company','')} · {c.get('title','')} — {x[1]}：{x[2] if len(x) > 2 else ''}\n")
        tc = {}
        for x in tdrop:
            tc[x[1].split(":")[0]] = tc.get(x[1].split(":")[0], 0) + 1
        r.write("\n## T-drop 计数\n\n" + " · ".join(f"{k} {v}" for k, v in tc.items()) + "\n")
    open(os.path.join(d, "committed"), "w").write(dt.datetime.now().isoformat())
    print(f"入队 {len(rows)}（0 分 {len(m['auto'])} + 选入 -1 {len(picked)}）· seen +{len(evaluated)} · 日报 {rep}")


if __name__ == "__main__":
    a = sys.argv[1:]
    date = dt.date.today().isoformat()
    if "--date" in a:
        i = a.index("--date")
        date = a[i + 1]
        del a[i:i + 2]
    if not a:
        sys.exit(__doc__)
    cmd = a[0]
    if cmd == "prefilter":
        prefilter(date, a[1])
    elif cmd == "screen":
        import shutil
        shutil.copy(os.path.expanduser(a[1]), os.path.join(wd(date), os.path.basename(a[1]).replace(".jsonl", "") + ".evidence.jsonl"))
        screen(date, a[1])
    elif cmd == "merge":
        merge(date)
    elif cmd == "commit":
        commit(date, a[1] if len(a) > 1 else "none")
    else:
        sys.exit(__doc__)
