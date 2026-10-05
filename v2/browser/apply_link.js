// LinkedIn /jobs/view/ 页：解析 Apply 入口。返回 EASYAPPLY / NOBTN / LI:<url> / <外链>（查询串拆成 Q: 防 [BLOCKED]）
(()=>{const e=[...document.querySelectorAll('a,button')].find(x=>/^(easy apply|apply)$/i.test((x.innerText||'').trim()));
if(!e)return 'NOBTN';
if(/easy/i.test(e.innerText)||e.tagName==='BUTTON')return 'EASYAPPLY';
try{const u=new URL(e.href);const t=u.searchParams.get('url');
if(!t)return 'LI:'+u.origin+u.pathname;
const x=new URL(t);return x.origin+x.pathname+(x.search?' Q:'+x.search.replace(/[?&]/g,' '):'');}
catch(err){return 'ERR '+err.message}})()
