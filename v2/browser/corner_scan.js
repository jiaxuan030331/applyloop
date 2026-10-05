// 角落扫描：每个 JD / 申请页 tab 必跑（get_page_text 只取正文块，sponsorship 常藏在表单问题、页底 EEO、折叠块里）
const t=document.body.innerText.replace(/[ \t]+/g,' ');const g=re=>(t.match(re)||['—']).join(' ~ ');
('SPONS: '+g(/[^\n.]{0,120}(sponsor|visa|work authoriz|H-?1B|\bOPT\b|\bCPT\b|citizen|clearance|ITAR)[^\n.]{0,100}/gi)+'\nYEARS: '+g(/[^\n.]{0,80}years? of[^\n.]{0,60}/gi)+'\nDEG: '+g(/[^\n.]{0,60}(Bachelor|Master|PhD|graduat)[^\n.]{0,80}/gi)+'\nLEN: '+t.length).slice(0,1200)
