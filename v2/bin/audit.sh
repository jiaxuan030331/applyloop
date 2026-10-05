#!/usr/bin/env bash
# 对账：resume 产物 ↔ applications/（改过简历必须有记录）＋ 台账同 apply_url 重复入账。
# 由 bin/job.sh audit 调用。只读。2026-10-05 起台账不记投递状态，原 ②③（存档↔台账状态）已删。
#
# 命名约定（对账全靠它）：
#   applications/YYYY-MM-DD_公司_岗位.md
#   outreach/    YYYY-MM-DD_公司_岗位.md
#   resumes/     YYYY-MM-DD_公司_岗位_<版本>[_L<级>].pdf   ← 去掉版本后缀即上面的 basename
# 公司名按「归一化前缀」或「首字母缩写」匹配台账（如 ACME ↔ Acme Computer Machines Enterprise）。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
J="$ROOT/ledger/jobs.tsv"
VER='SDE_ng|SDE_MLE_ng|SDE_AI_ng|FDE_ng|MLE_ng|AI_Eng|Speech_ng|CN'   # CN = 国内中文版（standalone_cn/）
NOTAJOB='^(General-|ALL_)'          # 通用版简历 / 通用文案，不是岗位，不参与对账
n=0

norm(){ printf %s "$1" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9'; }

echo "── ① resume 产物 ↔ applications/ ──"
for p in "$ROOT"/resumes/*.pdf; do
  [[ -e $p ]] || continue
  s=$(basename "$p" .pdf)
  [[ $s == Resume* || $s == "Your Name Resume"* ]] && continue   # 基线副本，不算产物
  stem=$(printf %s "$s" | sed -E "s/_($VER)(_L[123])?$//")
  [[ $stem == "$s" ]] && { echo "BADNAME   $s  （文件名不含版本后缀，resume-tailor 的 NAME 规则要求 _<版本>_L<级>）"; n=$((n+1)); continue; }
  printf %s "${stem#*_}" | grep -qE "$NOTAJOB" && continue
  [[ -e "$ROOT/applications/$stem.md" ]] || { echo "ORPHAN    $s  → 缺 applications/$stem.md"; n=$((n+1)); }
done

echo "── ④ 台账自身：同 apply_url 不同 job_key（2026-10-05 起）──"
# 只查 2026-10-05 起的行：此前的重复是历史，两个 li id 都要留在 seen 里防止重新冒出来，删不得
dup=$(awk -F'\t' 'NR>1 && $1>="2026-10-05"{last[$3]=$11; url[$3]=$7}
  END{for(j in last){u=url[j]; sub(/\?.*/,"",u)
    if(u=="" || u~/job_app$/ || last[j]=="dropped") continue
    k[u]=k[u]" "j; c[u]++}
  for(u in c) if(c[u]>1) print "DUP-URL  " u k[u]}' "$J")
[[ -n $dup ]] && { echo "$dup"; n=$((n+$(wc -l <<<"$dup"))); }

echo
echo "共 $n 处待处理。（ORPHAN=改了简历没写记录 · DUP-URL=重复入账）"
[[ $n == 0 ]]
