# 浏览器操作要点（triage / job-apply / scout 共用）

工具：Claude in Chrome（`mcp__claude-in-chrome__*`），登录态在本人的 Chrome 里。

- **新域名首次 navigate / javascript_tool 单独调用**（触发本人的授权弹窗），塞进 `browser_batch` 会连锁失败；常投的 ATS 域名请本人选「始终允许」。
- **返回值含 URL 查询串会整段 `[BLOCKED]`**：返回前 `.replace(/https?:\/\/\S+/g,'[url]')` 或 `.split('?')[0]`；仍被拦就换 `get_page_text` 或缩小选择器。返回值上限约 1500 字符，大清单用 blob 落 `~/Downloads`（`window.linkedin.dump`）。
- **一次 javascript_tool ≤45s**（CDP 超时，超时后 tab 内状态可能全丢）。
- `navigate` 的 back/forward 不可靠，用重导航；`failed in the extension` → 先 `tabs_context_mcp` 确认 tab 还在，不盲目重试。
- Ashby / Workday / Greenhouse / LinkedIn 是 SPA，WebFetch 无效。
- LinkedIn job view 的「… more」离 Apply 很近，误点会让岗位移出 Saved：用 `innerText` 读，不点。
- 已知抓不到：`careers.tiktokusds.com` 对 CDP 空渲染（TT/字节本来也在黑名单）。

**抓全判定**（出卡前提）：有公司介绍一句 + responsibilities / qualifications 两段 + `corner_scan.js` 跑过。不满足 → ① 等 3s 再 `get_page_text`；② 仍短 → `document.body.innerText` 按锚点分段 slice（单次约 1000 字符）；③ 请本人贴 JD。不瞎猜，不出卡。

片段：`apply_link.js`（LinkedIn 页解析 Apply 外链）、`corner_scan.js`（角落扫描）、`voyager_search.js` / `voyager_jd_batch.js` / `jd_screen.js`（scout）。
