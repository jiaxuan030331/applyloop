// LinkedIn voyager JD batch fetch — installs window.linkedin.fetchJDs
// Usage from Claude's javascript_tool:
//   <paste this file>
//   window.__jids = [...];              // installed elsewhere
//   window.__jd_raw = window.__jd_raw || {};
//   const r = await window.linkedin.fetchJDs(
//     window.__jids.filter(j => !window.__jd_raw[j]).slice(0, 120),
//     {store: window.__jd_raw}
//   );
//   JSON.stringify({...r, remaining: window.__jids.length - Object.keys(window.__jd_raw).length});
//
// Each fetched body is stored on `store[jid]` (default: a per-call {}).
// Tuned parameters (see agents/DAILY_SCRAPER.md §JD fetch): 4-way concurrent,
// 150ms pause between chunks, ~120 jids fits in one 45s javascript_tool call.

window.linkedin = window.linkedin || {};

window.linkedin.fetchJDs = async function (jids, opts = {}) {
  const {
    conc = 4,             // parallel in-flight fetches
    pauseMs = 150,        // pause between chunks
    store = {},           // where to stash successful bodies, keyed by jid
    decorationId = "com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65",
  } = opts;

  const csrf = (document.cookie.match(/JSESSIONID=(?:"?)([^;"]+)/) || [])[1] || "";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  async function fetchOne(jid) {
    try {
      const r = await fetch(
        `/voyager/api/jobs/jobPostings/${jid}?decorationId=${decorationId}`,
        {
          headers: {
            "csrf-token": csrf,
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "x-restli-protocol-version": "2.0.0",
            "x-li-lang": "en_US",
          },
        }
      );
      if (r.status === 200) {
        store[jid] = await r.json();
        return { ok: true, status: 200 };
      }
      return { ok: false, status: r.status };
    } catch (e) {
      return { ok: false, err: String(e).slice(0, 120) };
    }
  }

  const results = { ok: 0, fail: 0, statuses: {} };
  const t0 = performance.now();
  for (let i = 0; i < jids.length; i += conc) {
    const chunk = jids.slice(i, i + conc);
    const rs = await Promise.all(chunk.map(fetchOne));
    for (const r of rs) {
      const key = r.status || "err";
      results.statuses[key] = (results.statuses[key] || 0) + 1;
      if (r.ok) results.ok++;
      else results.fail++;
    }
    if (i + conc < jids.length) await sleep(pauseMs);
  }
  results.elapsed_ms = Math.round(performance.now() - t0);
  results.stored_total = Object.keys(store).length;
  return results;
};

// Convenience: dump the store to disk via blob download.
window.linkedin.dumpJDs = function (store, filename) {
  const entries = Object.entries(store).map(([jid, body]) =>
    JSON.stringify({ jid, body })
  );
  const jsonl = entries.join("\n");
  const blob = new Blob([jsonl], { type: "application/x-jsonlines" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 1500);
  return { count: entries.length, size_bytes: jsonl.length, filename };
};
