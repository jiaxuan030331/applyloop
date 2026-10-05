#!/usr/bin/env bash
# 求职台账工具。用法：
#   bin/job.sh seen                 已见 li id（空格分隔，给 triage 第 1 步的 DONE）
#   bin/job.sh lookup KEY [URL]     按 job_key 或 apply_url（去查询串）精确匹配；打印每个命中 key 的最后状态 + 卡片路径
#   bin/job.sh card KEY             该 key 的卡片路径
#   bin/job.sh gaps [all]          技能行缺口：按当前 all_technical_skills.md 重判会不会 + 剔除已进基线的词，只报过阈值的（all=全表）
#   bin/job.sh check                台账列数与枚举值自检（含 version 列格式；2026-10-05 起新行只能是 triaged）
#   bin/job.sh audit                对账：改过的简历都有 applications 记录 + 台账同 apply_url 重复入账
#   bin/job.sh logbatch KEY...      记 session↔岗位映射到 batches.log（自动取当前会话 id）
#   bin/job.sh trace 关键词          公司/key → 状态流水 + 卡片 + 存档 + 会话恢复命令
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; J="$ROOT/ledger/jobs.tsv"; G="$ROOT/ledger/skill_gaps.tsv"
card(){ local k="$1"; if [[ $k == li:* ]]; then echo "cards/li_${k#li:}.md"; else echo "cards/url_$(printf %s "${k#url:}" | shasum 2>/dev/null | cut -c1-12 || printf %s "${k#url:}" | sha1sum | cut -c1-12).md"; fi; }
case "${1:-}" in
seen) awk -F'\t' 'NR>1 && $3~/^li:/{sub(/^li:/,"",$3); if(!s[$3]++) printf "%s ", $3} END{print ""}' "$J";;
lookup)
  K="${2:-}"; U="${3:-}"; U="${U%%\?*}"
  # 匹配三条路：job_key 精确 / apply_url 去查询串精确 / URL 里的长数字 id（>=10 位）相同——
  # 同一岗位在 lifeattiktok 等站有 /search/<id> 与 /campus/position/<id> 两种形态（2026-09-20 试跑发现）。
  awk -F'\t' -v k="$K" -v u="$U" '
    function longid(x,  m){ m=""; while(match(x,/[0-9]{10,}/)){ if(RLENGTH>length(m)) m=substr(x,RSTART,RLENGTH); x=substr(x,RSTART+RLENGTH) } return m }
    NR>1{url=$7; sub(/\?.*/,"",url)
      if($3==k || (u!="" && url==u) || (u!="" && longid(u)!="" && longid(u)==longid(url))){last[$3]=$0; hit=1}}
    END{if(!hit){print "NEW"; exit} for(x in last){split(last[x],f,"\t"); print "SEEN\t" x "\t" f[4] " · " f[5] "\tstatus=" f[11] "\tversion=" f[9] "\tdate=" f[1]}}' "$J" |
  while IFS= read -r line; do if [[ $line == SEEN* ]]; then k=$(cut -f2 <<<"$line"); c=$(card "$k"); [[ -e $ROOT/$c ]] && echo "$line	card=$c" || echo "$line	card=无"; else echo "$line"; fi; done;;
card) card "$2";;
gaps)
  # 报告按**当前** all_technical_skills.md 重新判「会不会」——台账里的 class 列是写入当天的
  # 快照，会过期（2026-10-04 查出 28 个词被两种 class 记过，如 React 在 09-20 入清单后旧行仍记「不会」）。
  # 同时剔除已写进该版基线 \skill 行的词，并只报过阈值的，避免 144 行等于没报。
  # `gaps all` 打印完整表（旧行为）。
  MODE="${2:-top}" python3 - "$ROOT" <<'PYGAP'
import os,re,sys,collections
root=sys.argv[1]; mode=os.environ.get('MODE','top')
sk=open(f'{root}/all_technical_skills.md').read()
h=sk.find('已确认**不会**'); s0=sk.find('## 语言')     # s0 之前是说明段（含双反引号模板，会把正则配对带偏）
known=set()
for ln in sk[s0:h].split('\n'):
    if ln.lstrip().startswith('- '):
        known |= {t.strip().lower() for t in re.findall(r'`([^`]+)`', ln)}
notknown=set()
for ln in sk[h:].split('\n'):
    if ' · ' in ln and not ln.lstrip().startswith('（'):
        notknown={x.strip().lower() for x in ln.split('·') if x.strip()}; break
known-=notknown
def cls(w):
    l=w.lower()
    if l in notknown: return '不会'
    if l in known: return '会'
    for k in known:                      # `OAuth 2.0 / OIDC / Auth0` 这类合并条目
        if l in [x.strip() for x in k.split('/')]: return '会'
    return '未知'
base={}
def inbase(v,w):
    if v not in base:
        t=f'{root}/resume/Resume_{v}.tex'
        base[v]=' '.join(l for l in open(t).read().split('\n') if l.startswith('\\skill')) if os.path.exists(t) else ''
    return re.search(r'(?<![A-Za-z0-9+#.])'+re.escape(w)+r'(?![A-Za-z0-9+#.])', base[v], re.I) is not None
n=collections.Counter()
for i,ln in enumerate(open(f'{root}/ledger/skill_gaps.tsv')):
    if i==0: continue
    f=ln.rstrip('\n').split('\t')
    if len(f)>=5: n[(f[2],f[3])]+=1
skip=set()
sp=f'{root}/config/gaps_skip.tsv'          # 刻意没存回基线的词（放不下单页 / 会折孤行）
if os.path.exists(sp):
    skip={tuple(l.rstrip('\n').split('\t')[:2]) for l in open(sp) if l.strip() and not l.startswith('#')}
rows=[(c,v,w,cls(w)) for (v,w),c in n.items() if not inbase(v,w) and (v,w) not in skip]
if mode=='all':
    for c,v,w,k in sorted(rows,reverse=True): print(f'{c}\t{v}\t{k}\t{w}')
    raise SystemExit
hid=0
byv=collections.defaultdict(list)
for c,v,w,k in rows:
    if k!='会': continue
    if c>=5: byv[v].append((c,w))
    else: hid+=1
print('── 该存回基线（会、但该版 \\skill 行没有；该版 ≥5 次）──')
for v in sorted(byv): print(f'  {v:<12}'+' '.join(f'{w}({c})' for c,w in sorted(byv[v],reverse=True)[:8]))
if not byv: print('  无')
def agg(kind,thr,label):
    global hid
    t=collections.Counter()
    for c,v,w,k in rows:
        if k==kind: t[w]+=c
    hid+=sum(1 for w,c in t.items() if c<thr)
    out=sorted(((c,w) for w,c in t.items() if c>=thr),reverse=True)[:12]
    print(label); print('  '+(' '.join(f'{w}({c})' for c,w in out) or '无'))
agg('不会',8,'── 该学（清单里标「已确认不会」；跨版本合计 ≥8）──')
agg('未知',5,'── 清单里没有，需本人定会不会（合计 ≥5）──')
print(f'── 另有 {hid} 个词未过阈值未列（`job.sh gaps all` 看全表）')
PYGAP
  ;;
check)
  awk -F'\t' '{print NF}' "$J" | sort -u | tr '\n' ' '; echo "<- jobs.tsv 列数（应只有 11）"
  awk -F'\t' '{print NF}' "$G" | sort -u | tr '\n' ' '; echo "<- skill_gaps.tsv 列数（应只有 5）"
  awk -F'\t' 'NR>1 && !($2~/^(triage|apply)$/ && $6~/^(EASYAPPLY|ATS:[a-z]+|careers:[a-z0-9.-]+|non-ATS:[a-z-]+)( \(.*\))?$/ && $8~/^(N|Y:第[0-9]+条)$/ && $11~/^(triaged|applied-pending|applied|outreach|dropped)$/){print "BAD line " NR ": " $2" | "$6" | "$8" | "$11}' "$J"
  # version（第 9 列）：<版本>[ L1|L2|L3]，或 "-"（判死/未定）。不写 L 级 = 用基线没改。
  # 2026-10-05 起台账只记「triage 过没有」：新行 status 只能是 triaged（旧的多状态行是历史）
  awk -F'\t' 'NR>1 && $1>="2026-10-05" && $11!="triaged"{print "BAD status line " NR ": " $11 "（10-05 起只写 triaged）"}' "$J"
  awk -F'\t' 'NR>1 && $9!="-" && $9!~/^(SDE_ng|SDE_MLE_ng|SDE_AI_ng|FDE_ng|MLE_ng|AI_Eng|Speech_ng)( L[123])?$/{print "BAD version line " NR ": " $9}' "$J";;
audit) exec bash "$ROOT/bin/audit.sh";;
logbatch)
  # 当前会话 id = ~/.claude/projects 下最新在写的 transcript 文件名。
  # 已知局限：两个会话同时活跃时可能取到另一个的 id（triage 一次只跑一个，可接受）。
  shift; SID=$(basename "$(ls -t "$HOME"/.claude/projects/*/*.jsonl 2>/dev/null | head -1)" .jsonl)
  items=""
  for k in "$@"; do
    row=$(awk -F'\t' -v k="$k" '$3==k{l=$0} END{print l}' "$J")
    if [[ -n $row ]]; then
      items+="$k=$(cut -f4 <<<"$row")·$(cut -f9 <<<"$row")·$(cut -f11 <<<"$row") | "
    else items+="$k=不在台账 | "; fi
  done
  printf '%s\t%s\t%s\n' "$(date +%F)" "${SID:-unknown}" "${items% | }" >> "$ROOT/ledger/batches.log"
  tail -1 "$ROOT/ledger/batches.log";;
trace)
  Q="${2:?用法: trace 关键词}"
  echo "── 台账状态流水 ──"
  KEYS=$(awk -F'\t' -v q="$Q" 'NR>1 && (tolower($3) ~ tolower(q) || tolower($4) ~ tolower(q)){print $3}' "$J" | sort -u)
  [[ -z $KEYS ]] && { echo "台账无匹配：$Q"; exit 1; }
  for k in $KEYS; do
    awk -F'\t' -v k="$k" '$3==k{printf "  %s  %-10s %-16s %s · %s（%s）\n",$1,$2,$11,$4,substr($5,1,45),$9}' "$J"
    c=$(card "$k"); [[ -e $ROOT/$c ]] && echo "  卡片: $c"
  done
  echo "── 存档 ──"
  ls "$ROOT"/applications "$ROOT"/outreach 2>/dev/null | grep -i -- "$Q" | sed 's/^/  /' || echo "  无"
  echo "── 会话（batches.log）──"
  hit=0
  while IFS=$'\t' read -r d sid rest; do
    for k in $KEYS; do case "$rest" in *"$k="*) echo "  $d  $rest" | cut -c1-140; echo "  恢复现场: claude --resume $sid"; hit=1; break;; esac; done
  done < <(grep -v '^#' "$ROOT/ledger/batches.log" 2>/dev/null)
  if [[ $hit == 0 ]]; then echo "  无记录（logbatch 是 2026-09-20 加的，之前的批次没有映射）"; fi;;
*) sed -n '2,10p' "$0"; exit 1;;
esac
