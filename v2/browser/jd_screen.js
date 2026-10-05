// JD 压缩筛查 — 在浏览器端把 window.__jd_raw 里的全文 JD 映成 ~300 字符的证据行，
// 证据行不回传给模型：用 dump 落 ~/Downloads，交 bin/scout.py screen 处理。（2026-10-05 起）
// 用法：<粘贴本文件> 然后
//   window.linkedin.dump(window.linkedin.screenJDs(window.__jd_raw, window.__jids), 'scout_ev_<date>.jsonl')
window.linkedin = window.linkedin || {};
window.linkedin.screenJDs = function (store, jids) {
  const KILL = /(U\.?S\.? citizen[^.\n]{0,60}|citizenship (is )?required|green card (holder|only|required)|security clearance|TS\/?SCI|\bITAR\b|export control|10 CFR|U\.?S\.? person)/i;
  const YRS  = /(\d+)\s*\+?\s*(?:or more\s+)?years?[^.\n]{0,50}experience/i;
  const SPON = /[^.\n]{0,100}(sponsorship|sponsor|work authoriz\w*|H-?1B|\bOPT\b|\bCPT\b)[^.\n]{0,100}/i;
  const GRAD = /[^.\n]{0,60}(graduat\w+|Bachelor|Master|PhD|class of 20\d\d|20\d\d start)[^.\n]{0,80}/i;
  const STACK= /\b(python|java(?!script)|javascript|typescript|c\+\+|c#|\.net|golang|rust|react|angular|vue|node\.?js|ios|swift|android|kotlin|salesforce|servicenow|sap|abap|php|ruby|unity|unreal|embedded|verilog|fpga|rtl|pytorch|tensorflow|machine learning|deep learning|llm|genai|generative ai|nlp|computer vision|recommendation|ranking|sql|spark|kafka|kubernetes|docker|aws|azure|gcp|terraform|etl|tableau)\b/gi;
  const CONTRACT = /[^.\n]{0,60}(contract[- ]to[- ]hire|\bC2H\b|\bW-?2\b|contract (role|position|basis)|hourly rate|per hour|\/hr\b)[^.\n]{0,60}/i;
  const clean = (s) => (s || '').replace(/https?:\/\/\S+/g, '').replace(/[?&][\w]+=[\S]+/g, '').replace(/\s+/g, ' ').trim();
  return jids.map((j) => {
    const b = store[j];
    if (!b) return { j, miss: 1 };
    let t = '';
    try { t = (b.data && b.data.description && b.data.description.text) || ''; } catch (e) {}
    if (!t) { try { const d = (b.included || []).find((x) => x.description && x.description.text); t = d ? d.description.text : ''; } catch (e) {} }
    t = clean(t);
    const g = (re) => { const m = t.match(re); return m ? clean(m[0]).slice(0, 130) : ''; };
    const stack = [...new Set((t.match(STACK) || []).map((x) => x.toLowerCase()))].slice(0, 14).join(' ');
    // apply：完整外链申请 URL（进队列用）；Easy Apply / 无外链 → 'easyapply'
    let apply = 'easyapply';
    try { const am = (b.data && b.data.applyMethod) || {}; if (am.companyApplyUrl) apply = am.companyApplyUrl; } catch (e) {}
    // state/listed：关帖与老帖由 scout.py 确定性过滤（2026-09-24 回流：已关帖岗位混入过队列）
    let state = '', listed = null;
    try { state = (b.data && b.data.jobState) || ''; listed = (b.data && b.data.listedAt) || null; } catch (e) {}
    return { j, len: t.length, kill: g(KILL), yrs: g(YRS), spon: g(SPON), grad: g(GRAD), contract: g(CONTRACT), stack, apply, state, listed };
  });
};

// 通用落盘：数组 → JSONL blob 下载到 ~/Downloads（javascript_tool 返回值只有 ~1500 字符，大清单一律走这里）
window.linkedin.dump = window.linkedin.dump || function (arr, filename) {
  const jsonl = arr.map((x) => JSON.stringify(x)).join('\n');
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(new Blob([jsonl])), download: filename });
  document.body.appendChild(a); a.click(); setTimeout(() => a.remove(), 1500);
  return { count: arr.length, filename };
};
