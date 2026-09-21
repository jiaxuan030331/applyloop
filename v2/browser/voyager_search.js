// LinkedIn voyager search — installs window.linkedin.scrapeQuery
// Usage from Claude's javascript_tool:
//   <paste this file>
//   const out = await window.linkedin.scrapeQuery("software engineer graduate",
//                                                 {timeRange: "r86400"});
//   JSON.stringify({n: out.cards.length, stop: out.stop});
//
// Requires the caller to already be authenticated to linkedin.com in the
// current tab. The CSRF token is read from the JSESSIONID cookie.

window.linkedin = window.linkedin || {};

window.linkedin.scrapeQuery = async function (kw, opts = {}) {
  const {
    // paging
    pageSize = 25,
    cap = Infinity,          // stop after this many cards (default: exhaust)
    interPageMs = 150,       // pause between paged fetches (be polite)
    // filters
    geoId = "103644278",     // United States
    timeRange = "r86400",    // r86400=24h, r259200=3d, r604800=7d, r2592000=30d
    experienceList = "2,3",  // LinkedIn levels: 1=Internship 2=Entry 3=Associate 4=Mid-Senior 5=Director
                             //   Pass "" to disable the experience filter (recovers posters who leave the field blank).
    sortBy = "DD",           // DD=date-descending, R=relevance
  } = opts;

  const csrf = (document.cookie.match(/JSESSIONID=(?:"?)([^;"]+)/) || [])[1] || "";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const filterParts = [`timePostedRange:List(${timeRange})`, `sortBy:List(${sortBy})`];
  if (experienceList) filterParts.push(`experience:List(${experienceList})`);
  const selectedFilters = filterParts.join(",");

  async function fetchPage(start) {
    const url =
      `/voyager/api/voyagerJobsDashJobCards` +
      `?decorationId=com.linkedin.voyager.dash.deco.jobs.search.JobSearchCardsCollection-224` +
      `&count=${pageSize}&q=jobSearch` +
      `&query=(origin:JOB_SEARCH_PAGE_JOB_FILTER,keywords:${encodeURIComponent(kw)},` +
      `locationUnion:(geoId:${geoId}),selectedFilters:(${selectedFilters}),` +
      `spellCorrectionEnabled:true)&start=${start}`;
    const r = await fetch(url, {
      headers: {
        "accept": "application/vnd.linkedin.normalized+json+2.1",
        "x-restli-protocol-version": "2.0.0",
        "x-li-lang": "en_US",
        "csrf-token": csrf,
      },
    });
    if (r.status !== 200) return { status: r.status, cards: [], total: 0 };
    const body = await r.json();
    const inc = body.included || [];
    const cards = inc
      .filter(
        (x) =>
          (x.$type || "").endsWith("JobPostingCard") &&
          (x.entityUrn || "").includes(",JOBS_SEARCH")
      )
      .map((c) => {
        const jid =
          (c.entityUrn || "").match(/urn:li:fsd_jobPostingCard:\(([^,]+),/)?.[1] || "";
        const dateItem = (c.footerItems || []).find((f) => f.type === "LISTED_DATE");
        return {
          jid,
          title: c.jobPostingTitle || "",
          company: c.primaryDescription?.text || "",
          location: c.secondaryDescription?.text || "",
          listed_at_ms: dateItem?.timeAt || null,
          url: jid ? `https://www.linkedin.com/jobs/view/${jid}` : "",
        };
      })
      .filter((x) => x.jid);
    return { status: 200, cards, total: body.data?.paging?.total || 0 };
  }

  const out = [];
  let start = 0;
  let stop = "exhausted";
  while (out.length < cap) {
    const { status, cards, total } = await fetchPage(start);
    if (status !== 200) { stop = "http-" + status; break; }
    if (!cards.length) { stop = "empty"; break; }
    for (const c of cards) {
      out.push({ ...c, source_query: kw });
      if (out.length >= cap) break;
    }
    if (start + pageSize >= (total || 9999)) { stop = "exhausted"; break; }
    start += pageSize;
    await sleep(interPageMs);
  }
  return { kw, fetched: out.length, stop, cards: out };
};
