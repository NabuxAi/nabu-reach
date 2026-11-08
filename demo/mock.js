/* Nabu Reach public demo: strictly browser-memory simulation, zero network messaging. */
(() => {
  'use strict';
  let nextAccount = 4, nextDraft = 3;
  const accountRows = [
    {id:1,label:'Nabu Sandbox',provider:'mock',status:'mock_ready'},
    {id:2,label:'Cloud API example',provider:'meta_cloud',status:'setup_needed'},
    {id:3,label:'Partner workspace',provider:'evolution',status:'setup_needed'}
  ];
  const seedNames = ['Amira','Omar','Leila','Noor','Hana','Rayan','Maya','Sara','Yousef','Salim','Alya','Karim'];
  let contacts = seedNames.map((name,i) => ({
    phone:'+1555010'+String(100+i).padStart(4,'0'), name:name+' (demo)',
    consent_source:'sample_signup',consent_at:'2026-10-01T12:00:00Z',
    consent_status:i<10?'opt_in':'opt_out'
  }));
  const drafts = [
    {id:1,name:'Welcome message · draft',account_label:'Nabu Sandbox'},
    {id:2,name:'November product update · draft',account_label:'Nabu Sandbox'}
  ];
  const error = message => { throw new Error(message); };
  const approved = () => contacts.filter(c=>c.consent_status==='opt_in');
  const parseBody = data => { try {return JSON.parse(data||'{}')} catch(e) {return error('Invalid JSON')} };
  const validatePhone = p => /^\+[1-9]\d{7,14}$/.test(p||'');
  // RFC 4180-style fields: commas, escaped quotes and embedded newlines.
  const parseCsv = input => {
    const rows = [];
    let cells = [], value = '', quoted = false, closed = false, atStart = true;
    let line = 1, rowLine = 1;
    const text = input.replace(/^\uFEFF/, '');
    const finish = () => {
      cells.push(value);
      if (cells.some(cell => cell !== '')) rows.push({cells, line: rowLine});
      cells = []; value = ''; closed = false; atStart = true;
      rowLine = line + 1;
    };
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"') {
          if (text[i + 1] === '"') { value += '"'; i++; }
          else { quoted = false; closed = true; }
        } else if (ch === '\r') {
          if (text[i + 1] === '\n') i++;
          value += '\n'; line++;
        } else {
          value += ch;
          if (ch === '\n') line++;
        }
      } else if (ch === ',') {
        cells.push(value); value = ''; closed = false; atStart = true;
      } else if (ch === '\r' || ch === '\n') {
        if (ch === '\r' && text[i + 1] === '\n') i++;
        finish(); line++;
      } else if (ch === '"' && atStart) {
        quoted = true; atStart = false;
      } else if (ch === '"' || closed) {
        return error('Malformed CSV quote');
      } else {
        value += ch; atStart = false;
      }
    }
    if (quoted) return error('Unclosed CSV quote');
    if (value !== '' || cells.length || closed) {
      cells.push(value);
      if (cells.some(cell => cell !== '')) rows.push({cells, line: rowLine});
    }
    return rows;
  };
  window.reachDemoApi = async (route, options={}) => {
    const method=(options.method||'GET').toUpperCase();
    if(method==='GET') {
      if(route==='/api/summary')return {
        accounts:accountRows.length,contacts:contacts.length,
        opted_in:approved().length,
        opted_out:contacts.filter(c=>c.consent_status==='opt_out').length,
        drafts:drafts.length
      };
      if(route==='/api/accounts')return [...accountRows];
      if(route==='/api/contacts')return [...contacts];
      if(route==='/api/campaigns')return [...drafts];
      return error('Demo resource unavailable');
    }
    if(method!=='POST')return error('Unsupported demo request');
    if(route==='/api/contacts/import') {
      const input=typeof options.body==='string'?options.body:new TextDecoder().decode(options.body);
      if(input.length>512*1024)return error('Demo CSV too large (512 KiB maximum)');
      const rows=parseCsv(input);
      if(rows.length<2 || rows.length>1001)return error('Provide 1 to 1000 CSV contacts');
      const columns=rows.shift().cells.map(x=>x.trim().toLowerCase());
      if(new Set(columns).size!==columns.length)return error('Duplicate CSV columns');
      for(const column of ['phone','name','consent','consent_source','consent_at'])
        if(!columns.includes(column))return error('Missing column: '+column);
      let imported=0;const errors=[];
      rows.forEach(({cells,line})=>{
        if(cells.length!==columns.length){
          errors.push({row:line,reason:'Incorrect column count'});return;
        }
        const c=Object.fromEntries(columns.map((key,j)=>[key,(cells[j]||'').trim()]));
        const optIn=['yes','true','1','opt_in'].includes((c.consent||'').toLowerCase());
        const optOut=['no','false','0','opt_out'].includes((c.consent||'').toLowerCase());
        if(!validatePhone(c.phone)||(!optIn&&!optOut)) {
          errors.push({row:line,reason:'Invalid phone or consent value'});return;
        }
        if(optIn&&(!c.consent_source||!c.consent_at||
          !/(?:Z|[+-]\d{2}:\d{2})$/i.test(c.consent_at)||
          !Number.isFinite(Date.parse(c.consent_at))||Date.parse(c.consent_at)>Date.now())) {
          errors.push({row:line,reason:'Missing or invalid consent evidence'});return;
        }
        const prev=contacts.find(x=>x.phone===c.phone);
        if(prev&&prev.consent_status==='opt_out'&&optIn){
          errors.push({row:line,reason:'Existing opt-out cannot be reversed'});return;
        }
        const entry={phone:c.phone,name:c.name,consent_source:c.consent_source||'opt_out',
          consent_at:c.consent_at||new Date().toISOString(),
          consent_status:optIn?'opt_in':'opt_out'};
        if(prev)Object.assign(prev,entry);else contacts.push(entry);
        imported++;
      });
      return {imported,skipped:errors.length,errors};
    }
    const data=parseBody(options.body);
    if(route==='/api/accounts') {
      if(!String(data.label||'').trim())return error('Account name required');
      if(!['mock','meta_cloud','gowa','evolution'].includes(data.provider))return error('Invalid provider');
      const row={id:nextAccount++,label:String(data.label).slice(0,80),provider:data.provider,
        status:data.provider==='mock'?'mock_ready':'setup_needed'};
      accountRows.push(row);return row;
    }
    if(route==='/api/contacts/opt-out') {
      if(!validatePhone(data.phone))return error('Valid E.164 phone required');
      const row=contacts.find(c=>c.phone===data.phone);
      if(row)row.consent_status='opt_out';
      else contacts.push({phone:data.phone,name:'',consent_source:'unsubscribe',
        consent_at:new Date().toISOString(),consent_status:'opt_out'});
      return {status:'opt_out'};
    }
    if(route==='/api/campaigns/preview') {
      const text=String(data.message||'');
      if(!text.trim()||text.length>2048)return error('Enter a message up to 2048 chars');
      if(/\{\{(?!name\}\}|phone\}\})/.test(text))return error('Only {{name}} and {{phone}} are supported');
      const people=approved();
      return {eligible:people.length,within_draft_limit:Math.min(50,people.length),
        examples:people.slice(0,5).map(c=>({
          phone:c.phone,message:text.replace(/\{\{(name|phone)\}\}/g,(_,k)=>c[k]||'')
        }))};
    }
    if(route==='/api/campaigns') {
      const account=accountRows.find(a=>a.id===Number(data.account_id));
      if(!account||!String(data.name||'').trim()||!String(data.message||'').trim())
        return error('Select an account, name and message');
      const row={id:nextDraft++,name:String(data.name).slice(0,120),account_label:account.label};
      drafts.push(row);return row;
    }
    return error('Demo action not available');
  };
})();
