#!/usr/bin/env bash
# 求职台账工具。用法：
#   bin/job.sh seen                 已见 li id（空格分隔，给 triage 第 1 步的 DONE）
#   bin/job.sh lookup KEY [URL]     按 job_key 或 apply_url（去查询串）精确匹配；打印每个命中 key 的最后状态 + 卡片路径
#   bin/job.sh card KEY             该 key 的卡片路径
#   bin/job.sh gaps                 缺口累计>=3，已写进当前基线技能行的词自动剔除
#   bin/job.sh pending              盘点：最后状态为 triaged / applied-pending / outreach 的岗位
#   bin/job.sh stale                applied-pending 超过 3 天未更新的个数（0 则不提醒）
#   bin/job.sh check                台账列数与枚举值自检（含 version 列格式）
#   bin/job.sh audit                三方对账：resume 产物 / applications / outreach / 台账
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
  awk -F'\t' 'NR>1{n[$3"\t"$5"\t"$4]++} END{for(x in n) if(n[x]>=3) print n[x]"\t"x}' "$G" | sort -rn |
  while IFS=$'\t' read -r c v cls w; do
    tex="$ROOT/resume/Resume_$v.tex"
    # 词已在该版基线技能行 = 缺口已补，两个 class 都剔除（2026-09-20：原先只剔「会但该版没写」，
    # 导致「不会」的词存回基线后仍然长期霸榜，如 FDE_ng React）。按词边界匹配，避免 Go 撞 Google。
    esc=$(printf %s "$w" | sed 's/[][\.^$*+?(){}|/\\]/\\&/g')
    if [[ -e $tex ]] && grep '^\\skill' "$tex" | grep -qiE "(^|[^A-Za-z0-9+#.])${esc}([^A-Za-z0-9+#.]|$)"; then continue; fi
    printf '%s\t%s\t%s\t%s\n' "$c" "$v" "$cls" "$w"; done;;
pending) awk -F'\t' 'NR>1{last[$3]=$0; o[$3]=NR} END{for(k in last){split(last[k],f,"\t"); if(f[11]~/^(triaged|applied-pending|outreach)$/) print o[k]"\t"f[11]"\t"f[1]"\t"k"\t"f[4]" · "f[5]}}' "$J" | sort -n | cut -f2-;;
stale) awk -F'\t' -v c="$(date -d '-3 day' +%F 2>/dev/null || date -v-3d +%F)" 'NR>1{last[$3]=$11; d[$3]=$1} END{n=0; for(k in last) if(last[k]=="applied-pending" && d[k]<=c) n++; print n}' "$J";;
check)
  awk -F'\t' '{print NF}' "$J" | sort -u | tr '\n' ' '; echo "<- jobs.tsv 列数（应只有 11）"
  awk -F'\t' '{print NF}' "$G" | sort -u | tr '\n' ' '; echo "<- skill_gaps.tsv 列数（应只有 5）"
  awk -F'\t' 'NR>1 && !($2~/^(triage|apply)$/ && $6~/^(EASYAPPLY|ATS:[a-z]+|careers:[a-z0-9.-]+|non-ATS:[a-z-]+)( \(.*\))?$/ && $8~/^(N|Y:第[0-9]+条)$/ && $11~/^(triaged|applied-pending|applied|outreach|dropped)$/){print "BAD line " NR ": " $2" | "$6" | "$8" | "$11}' "$J"
  # version（第 9 列）：<版本>[ L1|L2|L3]，或 "-"（判死/未定）。不写 L 级 = 用基线没改。
  awk -F'\t' 'NR>1 && $9!="-" && $9!~/^(SDE_ng|SDE_MLE_ng|SDE_AI_ng|FDE_ng|MLE_ng|AI_Eng)( L[123])?$/{print "BAD version line " NR ": " $9}' "$J";;
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
