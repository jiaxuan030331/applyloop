#!/usr/bin/env bash
# 三方对账：resume 产物 ↔ applications/ ↔ ledger/jobs.tsv ↔ outreach/
# 由 bin/job.sh audit 调用。只读，不改任何文件；①②④ 是要处理的问题，③ 只是提示。
#
# 命名约定（对账全靠它）：
#   applications/YYYY-MM-DD_公司_岗位.md
#   outreach/    YYYY-MM-DD_公司_岗位.md
#   resumes/     YYYY-MM-DD_公司_岗位_<版本>[_L<级>].pdf   ← 去掉版本后缀即上面的 basename
# 公司名按「归一化前缀」或「首字母缩写」匹配台账（HPE ↔ Hewlett Packard Enterprise）。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
J="$ROOT/ledger/jobs.tsv"
VER='SDE_ng|SDE_MLE_ng|SDE_AI_ng|FDE_ng|MLE_ng|AI_Eng'
NOTAJOB='^(General-|ALL_)'          # 通用版简历 / 通用文案，不是岗位，不参与对账
n=0

norm(){ printf %s "$1" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9'; }

# 台账最后状态表（预归一化）：norm(company)\tinitials(company)\tstatus
LC=$(awk -F'\t' 'NR>1{last[$3]=$0} END{for(k in last){split(last[k],f,"\t")
  n=tolower(f[4]); gsub(/[^a-z0-9]/,"",n)
  m=split(f[4],w,/[^A-Za-z0-9]+/); i=""
  for(j=1;j<=m;j++) if(w[j]!="") i=i tolower(substr(w[j],1,1))
  print n"\t"i"\t"f[11]}}' "$J")

# 某个文件名里的公司 → 台账里所有命中行的状态（去重，空格分隔）：前缀或首字母缩写匹配
co_status(){
  awk -F'\t' -v co="$(norm "$1")" 'co!="" && $1!="" &&
    (index($1,co)==1 || index(co,$1)==1 || $2==co) {s[$3]=1}
    END{for(x in s) printf "%s ",x}' <<<"$LC"
}

echo "── ① resume 产物 ↔ applications/ ──"
for p in "$ROOT"/resumes/*.pdf; do
  [[ -e $p ]] || continue
  s=$(basename "$p" .pdf)
  [[ $s == Resume_* ]] && continue   # 基线副本，不算产物
  stem=$(printf %s "$s" | sed -E "s/_($VER)(_L[123])?$//")
  [[ $stem == "$s" ]] && { echo "BADNAME   $s  （文件名不含版本后缀，resume-tailor 的 NAME 规则要求 _<版本>_L<级>）"; n=$((n+1)); continue; }
  printf %s "${stem#*_}" | grep -qE "$NOTAJOB" && continue
  [[ -e "$ROOT/applications/$stem.md" ]] || { echo "ORPHAN    $s  → 缺 applications/$stem.md"; n=$((n+1)); }
done

echo "── ② applications/ ↔ 台账（该有 applied / applied-pending 行）──"
for f in "$ROOT"/applications/*.md; do
  [[ -e $f ]] || continue
  b=$(basename "$f" .md)
  printf %s "${b#*_}" | grep -qE "$NOTAJOB" && continue
  grep -q '确认未投' "$f" && continue   # 记录里已更正为未投，台账 outreach 是对的
  hit=$(co_status "$(cut -d_ -f2 <<<"$b")")
  [[ -z ${hit// /} ]] && { echo "NOROW     $b  → 台账里没有这家公司的行"; n=$((n+1)); continue; }
  grep -q 'applied' <<<"$hit" || { echo "NOTAPPL   $b  → 台账状态是: ${hit}（存档说在投，台账不认）"; n=$((n+1)); }
done

echo "── ③ 提示：outreach 文案提到投递，台账仍是 outreach（不计入待处理）──"
echo "   「先投 + 同时发消息」是**档位判定**，不是提交确认——下面这些可能只是还没投。真投了在「盘点」里说一声。"
for f in "$ROOT"/outreach/*.md; do
  [[ -e $f ]] || continue
  b=$(basename "$f" .md)
  printf %s "${b#*_}" | grep -qE "$NOTAJOB" && continue
  grep -q '先投\|已投\|同时发消息' "$f" || continue
  hit=$(co_status "$(cut -d_ -f2 <<<"$b")")
  grep -q 'applied' <<<"$hit" || echo "   ·  $b  （台账: ${hit:-无行}）"
done

echo "── ④ 台账自身：同 apply_url 不同 job_key ──"
dup=$(awk -F'\t' 'NR>1{last[$3]=$11; url[$3]=$7}
  END{for(j in last){u=url[j]; sub(/\?.*/,"",u)
    if(u=="" || u~/job_app$/ || last[j]=="dropped") continue
    k[u]=k[u]" "j; c[u]++}
  for(u in c) if(c[u]>1) print "DUP-URL  " u k[u]}' "$J")
[[ -n $dup ]] && { echo "$dup"; n=$((n+$(wc -l <<<"$dup"))); }

echo
echo "共 $n 处待处理。（ORPHAN=改了简历没写记录 · NOROW/NOTAPPL=存档与台账不符 · DUP-URL=重复入账；③ 只是提示）"
[[ $n == 0 ]]
