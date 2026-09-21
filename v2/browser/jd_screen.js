// JD 压缩筛查 — 在浏览器端把 window.__jd_raw 里的全文 JD 映成 ~300 字符的证据行，
// 模型只看证据行做判死判断，全文不进 context。（2026-09-20，scout 专用）
// 用法：<粘贴本文件> 然后
//   JSON.stringify(window.linkedin.screenJDs(window.__jd_raw, jids.slice(0,40)))
// 一次 ≤40 行，防止输出截断；返回文本已去 URL，防 [BLOCKED] 过滤。
window.linkedin = window.linkedin || {};
window.linkedin.screenJDs = function (store, jids) {
  const KILL = /(U\.?S\.? citizen[^.\n]{0,60}|citizenship (is )?required|green card (holder|only|required)|security clearance|TS\/?SCI|\bITAR\b|export control|10 CFR|U\.?S\.? person)/i;
  const YRS  = /(\d+)\s*\+?\s*(?:or more\s+)?years?[^.\n]{0,50}experience/i;
  const SPON = /[^.\n]{0,100}(sponsorship|sponsor|work authoriz\w*|H-?1B|\bOPT\b|\bCPT\b)[^.\n]{0,100}/i;
  const GRAD = /[^.\n]{0,60}(graduat\w+|Bachelor|Master|PhD|class of 20\d\d|20\d\d start)[^.\n]{0,80}/i;
  const STACK= /\b(python|java(?!script)|javascript|typescript|c\+\+|c#|\.net|golang|rust|react|angular|vue|node\.?js|ios|swift|android|kotlin|salesforce|servicenow|sap|abap|php|ruby|unity|unreal|embedded|verilog|fpga|rtl|pytorch|tensorflow|machine learning|deep learning|llm|genai|generative ai|nlp|computer vision|recommendation|ranking|sql|spark|kafka|kubernetes|docker|aws|azure|gcp|terraform|etl|tableau)\b/gi;
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
    return { j, len: t.length, kill: g(KILL), yrs: g(YRS), spon: g(SPON), grad: g(GRAD), stack };
  });
};
