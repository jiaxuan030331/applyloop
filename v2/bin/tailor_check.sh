#!/usr/bin/env bash
# resume-tailor 验收：LEVEL=1|2|3 bin/tailor_check.sh <工作目录> <版本>   （LEVEL 缺省 2）
# 通用：① 1 页 ② 无 Overfull/Underfull
# L1：改动行只在 \skill{
# L2：改动行只在 \skill{ / \item / 整块挪动项目或经历（\firstentry|\entry 标题行 + itemize 边界，标题文字须逐字出自基线或 Full_v4（新增块），2026-09-29 本人定；此前 2026-09-20 仅基线）；新侧每条 \item 必须逐字存在于 Full_v4 或该版基线（只选/排/换，不改措辞）
# L3：改动行只在 \skill{ / \item / \tagline；措辞自由，只打印改动条数（真实性靠人审 diff + claim 注释）
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; W="$1"; V="$2"; L="${LEVEL:-2}"
BASE="$ROOT/resume/Resume_$V.tex"; FULL="$ROOT/resume/Resume_Full_v4.tex"; ok=1
grep -q "Output written.*(1 page" "$W/edited.log" && echo "① 1 page OK" || { echo "① FAIL: $(grep 'Output written' "$W/edited.log")"; ok=0; }
n=$(grep -cE "Overfull|Underfull" "$W/edited.log"); [[ $n == 0 ]] && echo "② 无 Overfull/Underfull OK" || { echo "② FAIL: $n 条"; grep -E "Overfull|Underfull" "$W/edited.log" | head -5; ok=0; }
case $L in 1) pat='^[+-][[:space:]]*\\skill\{';; 2) pat='^[+-][[:space:]]*(\\skill\{|\\item|\\firstentry\{|\\entry\{|\\begin\{itemize\}|\\end\{itemize\})';; 3) pat='^[+-][[:space:]]*(\\skill\{|\\item|\\tagline|\\firstentry\{|\\entry\{|\\begin\{itemize\}|\\end\{itemize\})';; *) echo "LEVEL 只能是 1/2/3"; exit 2;; esac
bad=$(diff -u "$BASE" "$W/edited.tex" | grep -E '^[+-]' | grep -vE '^(\+\+\+|---)' | grep -vE '^[+-][[:space:]]*$' | grep -vE "$pat")
[[ -z $bad ]] && echo "③ L$L 改动位置 OK" || { echo "③ FAIL，L$L 白名单外改动："; echo "$bad" | head -5; ok=0; }
if [[ $L == 2 ]]; then
  miss=$(diff "$BASE" "$W/edited.tex" | grep -E '^>[[:space:]]*\\item' | sed 's/^> //' | while IFS= read -r l; do grep -qxF -- "$l" "$FULL" "$BASE" 2>/dev/null || grep -qF -- "$(printf %s "$l" | sed 's/^[[:space:]]*//')" "$FULL" "$BASE" || echo "$l"; done)
  [[ -z $miss ]] && echo "④ L2 每条新 \\item 都出自 Full/基线 OK" || { echo "④ FAIL，L2 不许改措辞，这些 \\item 在 Full/基线里找不到原句："; echo "$miss" | cut -c1-120 | head -5; ok=0; }
fi
if [[ $L != 1 ]]; then
  hmiss=$(diff "$BASE" "$W/edited.tex" | grep -E '^>[[:space:]]*\\(firstentry|entry)\{' | sed -E 's/^>[[:space:]]*\\(firstentry|entry)//' | while IFS= read -r h; do grep -qF -- "$h" "$BASE" || grep -qF -- "$h" "$FULL" || echo "$h"; done)
  [[ -z $hmiss ]] && echo "⑤ 项目/经历块标题逐字出自基线/Full OK（整块挪动、\\firstentry/\\entry 对调允许）" || { echo "⑤ FAIL，块标题文字被改："; echo "$hmiss" | cut -c1-120 | head -3; ok=0; }
fi
nb=$(diff "$BASE" "$W/edited.tex" | grep -cE '^>[[:space:]]*\\item'); echo "   改动 \\item 行数（新侧）: $nb"
echo "BASE_SHA256 $(shasum -a 256 "$BASE" 2>/dev/null | cut -c1-64 || sha256sum "$BASE" | cut -c1-64)"
[[ $ok == 1 ]] && { echo PASS; exit 0; } || { echo FAIL; exit 1; }
